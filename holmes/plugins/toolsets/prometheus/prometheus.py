import os
import re
import logging
import random
import string
import time

from typing import Any, Dict, List, Union, Optional

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

from holmes.plugins.toolsets.utils import (
    get_param_or_raise,
    process_timestamps_to_rfc3339,
)
from holmes.utils.cache import TTLCache

PROMETHEUS_RULES_CACHE_KEY = "cached_prometheus_rules"


class PrometheusConfig(BaseModel):
    prometheus_url: Union[str, None]
    # Setting to None will remove the time window from the request for labels
    metrics_labels_time_window_hrs: Union[int, None] = 48
    # Setting to None will disable the cache
    metrics_labels_cache_duration_hrs: Union[int, None] = 12
    fetch_labels_with_labels_api: bool = False
    fetch_metadata_with_series_api: bool = False
    tool_calls_return_data: bool = False
    headers: Dict = {}
    rules_cache_duration_seconds: Union[int, None] = 1800  # 30 minutes


class BasePrometheusTool(Tool):
    toolset: "PrometheusToolset"


def generate_random_key():
    return "".join(random.choices(string.ascii_letters + string.digits, k=4))


def filter_metrics_by_type(metrics: Dict, expected_type: str):
    return {
        metric_name: metric_data
        for metric_name, metric_data in metrics.items()
        if expected_type in metric_data.get("type", "")
        or metric_data.get("type", "") == "?"
    }


def filter_metrics_by_name(metrics: Dict, pattern: str) -> Dict:
    regex = re.compile(pattern)
    return {
        metric_name: metric_data
        for metric_name, metric_data in metrics.items()
        if regex.search(metric_name)
    }


METRICS_SUFFIXES_TO_STRIP = ["_bucket", "_count", "_sum"]


def fetch_metadata(prometheus_url: str, headers: Optional[Dict]) -> Dict:
    metadata_url = urljoin(prometheus_url, "api/v1/metadata")
    metadata_response = requests.get(
        metadata_url, headers=headers, timeout=60, verify=True
    )

    metadata_response.raise_for_status()

    metadata = metadata_response.json()["data"]

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

    return metrics


def fetch_metadata_with_series_api(
    prometheus_url: str, metric_name: str, headers: Dict
) -> Dict:
    url = urljoin(prometheus_url, "api/v1/series")
    params: Dict = {
        "match[]": f'{{__name__=~".*{metric_name}.*"}}',
    }
    response = requests.get(
        url, headers=headers, timeout=60, params=params, verify=True
    )
    response.raise_for_status()
    metrics = response.json()["data"]

    metadata = {}
    for metric_data in metrics:
        metric_name = metric_data.get("__name__")
        if not metric_name:
            continue

        metric = metadata.get(metric_name)
        if not metric:
            metric = {"description": "?", "type": "?", "labels": set()}
            metadata[metric_name] = metric

        labels = {k for k in metric_data.keys() if k != "__name__"}
        metric["labels"].update(labels)

    return metadata


def result_has_data(result: Dict) -> bool:
    data = result.get("data", {})
    if len(data.get("result", [])) > 0:
        return True
    return False


def add_prometheus_auth(prometheus_auth_header: Optional[str]) -> Dict[str, Any]:
    results = {}
    if prometheus_auth_header:
        results["Authorization"] = prometheus_auth_header
    return results


def fetch_metrics_labels_with_series_api(
    prometheus_url: str,
    headers: Dict[str, str],
    cache: Optional[TTLCache],
    metrics_labels_time_window_hrs: Union[int, None],
    metric_name: str,
) -> dict:
    """This is a slow query. Takes 5+ seconds to run"""
    cache_key = f"metrics_labels_series_api:{metric_name}"
    if cache:
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

    series_url = urljoin(prometheus_url, "api/v1/series")
    params: dict = {
        "match[]": f'{{__name__=~".*{metric_name}.*"}}',
    }
    if metrics_labels_time_window_hrs is not None:
        params["end_time"] = int(time.time())
        params["start_time"] = params["end_time"] - (
            metrics_labels_time_window_hrs * 60 * 60
        )

    series_response = requests.get(
        url=series_url, headers=headers, params=params, timeout=60, verify=True
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


def fetch_metrics_labels_with_labels_api(
    prometheus_url: str,
    cache: Optional[TTLCache],
    metrics_labels_time_window_hrs: Union[int, None],
    metric_names: List[str],
    headers: Dict,
) -> dict:
    metrics_labels = {}

    for metric_name in metric_names:
        cache_key = f"metrics_labels_labels_api:{metric_name}"
        if cache:
            cached_result = cache.get(cache_key)
            if cached_result:
                metrics_labels[metric_name] = cached_result

        url = urljoin(prometheus_url, "api/v1/labels")
        params: dict = {
            "match[]": f'{{__name__="{metric_name}"}}',
        }
        if metrics_labels_time_window_hrs is not None:
            params["end_time"] = int(time.time())
            params["start_time"] = params["end_time"] - (
                metrics_labels_time_window_hrs * 60 * 60
            )

        response = requests.get(
            url=url, headers=headers, params=params, timeout=60, verify=True
        )
        response.raise_for_status()
        labels = response.json()["data"]
        filtered_labels = {label for label in labels if label != "__name__"}
        metrics_labels[metric_name] = filtered_labels

        if cache:
            cache.set(cache_key, filtered_labels)

    return metrics_labels


def fetch_metrics(
    prometheus_url: str,
    cache: Optional[TTLCache],
    metrics_labels_time_window_hrs: Union[int, None],
    metric_name: str,
    should_fetch_labels_with_labels_api: bool,
    should_fetch_metadata_with_series_api: bool,
    headers: Dict,
) -> dict:
    metrics = None
    should_fetch_labels = True
    if should_fetch_metadata_with_series_api:
        metrics = fetch_metadata_with_series_api(
            prometheus_url=prometheus_url, metric_name=metric_name, headers=headers
        )
        should_fetch_labels = False  # series API returns the labels
    else:
        metrics = fetch_metadata(prometheus_url=prometheus_url, headers=headers)
        metrics = filter_metrics_by_name(metrics, metric_name)

    if should_fetch_labels:
        metrics_labels = {}
        if not should_fetch_labels_with_labels_api:
            metrics_labels = fetch_metrics_labels_with_series_api(
                prometheus_url=prometheus_url,
                cache=cache,
                metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
                metric_name=metric_name,
                headers=headers,
            )
        else:
            metrics_labels = fetch_metrics_labels_with_labels_api(
                prometheus_url=prometheus_url,
                cache=cache,
                metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
                metric_names=list(metrics.keys()),
                headers=headers,
            )

        for metric_name in metrics:
            if metric_name in metrics_labels:
                metrics[metric_name]["labels"] = metrics_labels[metric_name]

    return metrics


class ListPrometheusRules(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="list_prometheus_rules",
            description="List all defined prometheus rules. Will show the prometheus rules description, expression and annotations",
            parameters={},
            toolset=toolset,
        )
        self._cache = None

    def _invoke(self, params: Any) -> str:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return "Prometheus is not configured. Prometheus URL is missing"
        if not self._cache and self.toolset.config.rules_cache_duration_seconds:
            self._cache = TTLCache(self.toolset.config.rules_cache_duration_seconds)
        try:
            cached_rules = self._cache.get(PROMETHEUS_RULES_CACHE_KEY)
            if cached_rules:
                logging.debug("rules returned from cache")
                return cached_rules

            prometheus_url = self.toolset.config.prometheus_url

            rules_url = urljoin(prometheus_url, "/api/v1/rules")

            rules_response = requests.get(
                url=rules_url,
                params=params,
                timeout=180,
                verify=True,
                headers=self.toolset.config.headers,
            )
            rules_response.raise_for_status()
            response = json.dumps(rules_response.json()["data"])
            self._cache.set(PROMETHEUS_RULES_CACHE_KEY, response)
            return response
        except requests.Timeout:
            logging.warn("Timeout while fetching prometheus rules", exc_info=True)
            return "Request timed out while fetching rules"
        except RequestException as e:
            logging.warn("Failed to fetch prometheus rules", exc_info=True)
            return f"Network error while fetching rules: {str(e)}"
        except Exception as e:
            logging.warn("Failed to process prometheus rules", exc_info=True)
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return "list available prometheus rules"


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

            name_filter = params.get("name_filter")
            if not name_filter:
                return "Error: cannot run tool 'list_available_metrics'. The param 'name_filter' is required but is missing."

            metrics = fetch_metrics(
                prometheus_url=prometheus_url,
                cache=self._cache,
                metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
                metric_name=name_filter,
                should_fetch_labels_with_labels_api=self.toolset.config.fetch_labels_with_labels_api,
                should_fetch_metadata_with_series_api=self.toolset.config.fetch_metadata_with_series_api,
                headers=self.toolset.config.headers,
            )

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

            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query")

            payload = {"query": query}

            response = requests.post(
                url=url, headers=self.toolset.config.headers, data=payload, timeout=60
            )

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

                if self.toolset.config.tool_calls_return_data:
                    response_data["data"] = data.get("data")

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
                    description="Start datetime, inclusive. Should be formatted in rfc3339. If negative integer, the number of seconds relative to end. Defaults to negative one hour (-3600)",
                    type="string",
                    required=False,
                ),
                "end": ToolParameter(
                    description="End datetime, inclusive. Should be formatted in rfc3339. Defaults to NOW",
                    type="string",
                    required=False,
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
            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query_range")

            query = get_param_or_raise(params, "query")
            (start, end) = process_timestamps_to_rfc3339(
                params.get("start"), params.get("end")
            )
            step = params.get("step", "")
            description = params.get("description", "")

            payload = {
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            }

            response = requests.post(
                url=url, headers=self.toolset.config.headers, data=payload, timeout=120
            )

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

                if self.toolset.config.tool_calls_return_data:
                    response_data["data"] = data.get("data")
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
                ListPrometheusRules(toolset=self),
                ListAvailableMetrics(toolset=self),
                ExecuteInstantQuery(toolset=self),
                ExecuteRangeQuery(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
        )
        self._load_llm_instructions(
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "prometheus_instructions.jinja2"
                )
            )
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config and not os.environ.get("PROMETHEUS_URL", None):
            return False
        elif not config and os.environ.get("PROMETHEUS_URL", None):
            self.config = PrometheusConfig(
                prometheus_url=os.environ.get("PROMETHEUS_URL"),
                headers=add_prometheus_auth(
                    os.environ.get("PROMETHEUS_AUTH_HEADER", None)
                ),
            )

            return True
        else:
            self.config = PrometheusConfig(**config)
            return True
