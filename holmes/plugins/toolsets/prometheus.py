import os
import re
import logging
import random
import string
import time

from typing import Any, Union, Optional

import requests
from pydantic import BaseModel
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
import json
from requests import RequestException

from urllib.parse import urljoin

from holmes.utils.cache import TTLCache


class PrometheusConfig(BaseModel):
    prometheus_url: Union[str, None]
    # Setting to None will remove the time window from the request for labels
    metrics_labels_time_window_hrs: Union[int, None] = 48
    # Setting to None will disable the cache
    metrics_labels_cache_duration_hrs: Union[int, None] = 12


class BasePrometheusTool(Tool):
    toolset: "PrometheusToolset"


def generate_random_key():
    return "".join(random.choices(string.ascii_letters + string.digits, k=4))


def filter_metrics_by_type(metrics: dict, expected_type: str):
    return {
        metric_name: metric_data
        for metric_name, metric_data in metrics.items()
        if metric_data.get("type") == expected_type
    }


def filter_metrics_by_name(metrics: dict, pattern: str) -> dict:
    regex = re.compile(pattern)
    return {
        metric_name: metric_data
        for metric_name, metric_data in metrics.items()
        if regex.search(metric_name)
    }


def fetch_metadata(url: str) -> dict:
    metadata_url = urljoin(url, "/api/v1/metadata")
    metadata_response = requests.get(metadata_url, timeout=60, verify=True)

    metadata_response.raise_for_status()

    metadata = metadata_response.json()["data"]
    return metadata


def result_has_data(result: dict) -> bool:
    data = result.get("data", {})
    if len(data.get("result", [])) > 0:
        return True
    return False


def fetch_metrics_labels(
    prometheus_url: str,
    cache: Optional[TTLCache],
    metrics_labels_time_window_hrs: Union[int, None],
    metric_name: str,
) -> dict:
    """This is a slow query. Takes 5+ seconds to run"""
    cache_key = f"metrics_labels:{metric_name}"
    if cache:
        cached_result = cache.get(cache_key)
        if cached_result:
            logging.info("fetch_metrics_labels() result retrieved from cache")
            return cached_result

    series_url = urljoin(prometheus_url, "/api/v1/series")
    params: dict = {
        "match[]": f'{{__name__=~".*{metric_name}.*"}}',
    }
    # params: dict = {
    #     "match[]": '{__name__!=""}',
    # }
    if metrics_labels_time_window_hrs is not None:
        params["end_time"] = int(time.time())
        params["start_time"] = params["end_time"] - (
            metrics_labels_time_window_hrs * 60 * 60
        )

    series_response = requests.get(
        url=series_url, params=params, timeout=60, verify=True
    )
    series_response.raise_for_status()
    series = series_response.json()["data"]

    metrics_labels: dict = {}
    for serie in series:
        metric_name = serie["__name__"]
        # Add all labels except __name__
        labels = {k for k in serie.keys() if k != "__name__"}
        if metric_name in metrics_labels:
            metrics_labels[metric_name].update(labels)
        else:
            metrics_labels[metric_name] = labels
    if cache:
        cache.set(cache_key, metrics_labels)

    return metrics_labels


def fetch_metrics(
    url: str,
    cache: Optional[TTLCache],
    metrics_labels_time_window_hrs: Union[int, None],
    metric_name: str,
) -> dict:
    metadata = fetch_metadata(url)
    metrics_labels = fetch_metrics_labels(
        prometheus_url=url,
        cache=cache,
        metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
        metric_name=metric_name,
    )

    metrics = {}
    for metric_name, meta_list in metadata.items():
        if meta_list:
            metric_type = meta_list[0].get("type", "unknown")
            metric_description = meta_list[0].get("help", "unknown")
            metrics[metric_name] = {
                "type": metric_type,
                "description": metric_description,
                "labels": set(),
            }

    for metric_name in metrics:
        if metric_name in metrics_labels:
            metrics[metric_name]["labels"] = metrics_labels[metric_name]

    return metrics


class ListAvailableMetrics(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="list_available_metrics",
            description="List all the available metrics to query from prometheus, including their types (counter, gauge, histogram, summary) and available labels.",
            parameters={
                "type_filter": ToolParameter(
                    description="Optional filter to only return a specific metric type. Can be one of counter, gauge, histogram, summary",
                    type="string",
                    required=False,
                ),
                "name_filter": ToolParameter(
                    description="Only the metrics partially or fully matching this name will be returned",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )
        self._cache = None

    def _invoke(self, params: Any) -> str:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return "Prometheus is not configured. Prometheus URL is missing"
        if not self._cache and self.toolset.config.metrics_labels_cache_duration_hrs:
            self._cache = TTLCache(
                self.toolset.config.metrics_labels_cache_duration_hrs * 3600
            )
        try:
            prometheus_url = self.toolset.config.prometheus_url
            metrics_labels_time_window_hrs = (
                self.toolset.config.metrics_labels_time_window_hrs
            )
            if not prometheus_url:
                return "Prometheus is not configured. Prometheus URL is missing"

            name_filter = params.get("name_filter")
            if not name_filter:
                return "Error: cannot run tool 'list_available_metrics'. The param 'name_filter' is required but is missing."

            metrics = fetch_metrics(
                prometheus_url, self._cache, metrics_labels_time_window_hrs, name_filter
            )

            metrics = filter_metrics_by_name(metrics, name_filter)

            if params.get("type_filter"):
                metrics = filter_metrics_by_type(metrics, params.get("type_filter"))

            output = ["Metric | Description | Type | Labels"]
            output.append("-" * 100)

            for metric, info in sorted(metrics.items()):
                labels_str = (
                    ", ".join(sorted(info["labels"])) if info["labels"] else "none"
                )
                output.append(
                    f"{metric} | {info['description']} | {info['type']} | {labels_str}"
                )

            table_output = "\n".join(output)
            return table_output

        except requests.Timeout:
            logging.warn("Timeout while fetching prometheus metrics", exc_info=True)
            return "Request timed out while fetching metrics"
        except RequestException as e:
            logging.warn("Failed to fetch prometheus metrics", exc_info=True)
            return f"Network error while fetching metrics: {str(e)}"
        except Exception as e:
            logging.warn("Failed to process prometheus metrics", exc_info=True)
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f'list available prometheus metrics: name_filter="{params.get("name_filter", "<no filter>")}", type_filter="{params.get("type_filter", "<no filter>")}"'


class ExecuteInstantQuery(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="execute_prometheus_instant_query",
            description="Execute an instant PromQL query",
            parameters={
                "query": ToolParameter(
                    description="The PromQL query",
                    type="string",
                    required=True,
                ),
                "description": ToolParameter(
                    description="Describes the query",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return "Prometheus is not configured. Prometheus URL is missing"
        try:
            query = params.get("query", "")
            description = params.get("description", "")

            url = urljoin(self.toolset.config.prometheus_url, "/api/v1/query")

            payload = {"query": query}

            response = requests.post(url=url, data=payload, timeout=60)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                error_message = None
                if status == "success" and not result_has_data(data):
                    status = "Failed"
                    error_message = (
                        "The prometheus query returned no result. Is the query correct?"
                    )
                response_data = {
                    "status": status,
                    "error_message": error_message,
                    "random_key": generate_random_key(),
                    "tool_name": self.name,
                    "description": description,
                    "query": query,
                }
                data_str = json.dumps(response_data, indent=2)
                return data_str

            # Handle known Prometheus error status codes
            error_msg = "Unknown error occurred"
            if response.status_code in [400, 429]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error", error_data.get("message", str(response.content))
                    )
                except json.JSONDecodeError:
                    pass
                return (
                    f"Query execution failed. HTTP {response.status_code}: {error_msg}"
                )

            # For other status codes, just return the status code and content
            return f"Query execution failed with unexpected status code: {response.status_code}. Response: {response.content}"

        except RequestException as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return f"Connection error to Prometheus: {str(e)}"
        except Exception as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return f"Unexpected error executing query: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        query = params.get("query")
        description = params.get("description")
        return f"Prometheus query. query={query}, description={description}"


class ExecuteRangeQuery(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="execute_prometheus_range_query",
            description="Execute a PromQL range query",
            parameters={
                "query": ToolParameter(
                    description="The PromQL query",
                    type="string",
                    required=True,
                ),
                "description": ToolParameter(
                    description="Describes the query",
                    type="string",
                    required=True,
                ),
                "start": ToolParameter(
                    description="Start timestamp, inclusive. rfc3339 or unix_timestamp",
                    type="string",
                    required=True,
                ),
                "end": ToolParameter(
                    description="End timestamp, inclusive. rfc3339 or unix_timestamp",
                    type="string",
                    required=True,
                ),
                "step": ToolParameter(
                    description="Query resolution step width in duration format or float number of seconds",
                    type="number",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return "Prometheus is not configured. Prometheus URL is missing"

        try:
            url = urljoin(self.toolset.config.prometheus_url, "/api/v1/query_range")

            query = params.get("query", "")
            start = params.get("start", "")
            end = params.get("end", "")
            step = params.get("step", "")
            description = params.get("description", "")

            payload = {
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            }

            response = requests.post(url=url, data=payload, timeout=120)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                error_message = None
                if status == "success" and not result_has_data(data):
                    status = "Failed"
                    error_message = (
                        "The prometheus query returned no result. Is the query correct?"
                    )
                response_data = {
                    "status": status,
                    "error_message": error_message,
                    "random_key": generate_random_key(),
                    "tool_name": self.name,
                    "description": description,
                    "query": query,
                    "start": start,
                    "end": end,
                    "step": step,
                }
                data_str = json.dumps(response_data, indent=2)
                return data_str

            error_msg = "Unknown error occurred"
            if response.status_code in [400, 429]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error", error_data.get("message", str(response.content))
                    )
                except json.JSONDecodeError:
                    pass
                return (
                    f"Query execution failed. HTTP {response.status_code}: {error_msg}"
                )

            return f"Query execution failed with unexpected status code: {response.status_code}. Response: {response.content}"

        except RequestException as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return f"Connection error to Prometheus: {str(e)}"
        except Exception as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return f"Unexpected error executing query: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        query = params.get("query")
        start = params.get("start")
        end = params.get("end")
        step = params.get("step")
        description = params.get("description")
        return f"Prometheus query_range. query={query}, start={start}, end={end}, step={step}, description={description}"


class PrometheusToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="prometheus/metrics",
            description="Prometheus integration to fetch metadata and execute PromQL queries",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/prometheus.html",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/3/38/Prometheus_software_logo.svg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                ListAvailableMetrics(toolset=self),
                ExecuteInstantQuery(toolset=self),
                ExecuteRangeQuery(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config and not os.environ.get("PROMETHEUS_URL", None):
            return False
        elif not config and os.environ.get("PROMETHEUS_URL", None):
            self.config = PrometheusConfig(
                prometheus_url=os.environ.get("PROMETHEUS_URL")
            )
            return True
        else:
            self.config = PrometheusConfig(**config)
            return True
