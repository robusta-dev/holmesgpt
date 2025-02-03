import os
import re
import logging
import random
import string

from typing import Any, Optional, Union

import requests
from pydantic import BaseModel
from holmes.core.tools import CallablePrerequisite, StaticPrerequisite, Tool, ToolParameter, Toolset, ToolsetTag
import json
from requests import RequestException

from urllib.parse import urljoin
# https://prometheus.io/docs/prometheus/latest/querying/api/#http-api
# http://localhost:9090/api/v1/series?match[]=container_network_receive_bytes_total{namespace="default"}

# Imagine you're a PromQL expert. If it's relevant to the investigation, attempt to build
# a PromQL query to visualize the issue using ONLY available PromQL metrics and not the
# others. When constructing the query, ensure it's functional by verifying its correctness.
# Respond strictly in the following format and nothing else:: << { type: "graph",
# promQL: "PROMQL_HERE", description: "DESCRIPTION_HERE" } >>(Note: do NOT include any
# explanations, comments, titles, headers or additional text, related to this query,
# outside this format)

class PrometheusConfig(BaseModel):
    url: Union[str, None]

def generate_random_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=4))

def filter_metrics_by_type(metrics: dict, expected_type: str):
    return {
        metric_name: metric_data
        for metric_name, metric_data in metrics.items()
        if metric_data.get('type') == expected_type
    }

def filter_metrics_by_name(metrics: dict, pattern: str) -> dict:
    regex = re.compile(pattern)
    return {
        metric_name: metric_data
        for metric_name, metric_data in metrics.items()
        if regex.search(metric_name)
    }

def fetch_metadata(url: str) -> dict:

    metadata_url = urljoin(url, '/api/v1/metadata')
    metadata_response = requests.get(
        metadata_url,
        timeout=60,
        verify=True
    )

    # TODO: Raise if not success

    metadata = metadata_response.json()['data']
    return metadata

def fetch_series(url: str) -> dict:
    series_url = urljoin(url, '/api/v1/series')
    series_response = requests.get(
        f"{series_url}?match[]={{__name__!=\"\"}}",
        timeout=60,
        verify=True
    )

    # TODO: Raise if not success

    series = series_response.json()['data']
    return series

def fetch_metrics(url:str) -> dict:

    metadata = fetch_metadata(url)
    series = fetch_series(url)

    metrics = {}
    for metric_name, meta_list in metadata.items():
        if meta_list:
            metric_type = meta_list[0].get('type', 'unknown')
            metrics[metric_name] = {
                'type': metric_type,
                'labels': set()
            }

    for serie in series:
        metric_name = serie['__name__']
        if metric_name in metrics:
            # Add all labels except __name__
            labels = {k for k in serie.keys() if k != '__name__'}
            metrics[metric_name]['labels'].update(labels)

    return metrics

class ListAvailableMetrics(Tool):
    def __init__(self, toolset: PrometheusToolset):
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
                    description="Optional regular expression to only return matching metric names",
                    type="string",
                    required=False,
                ),
            },
        )
        self._config = toolset.config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"
        try:

            prometheus_url = self._config.url

            if not prometheus_url:
                return "Prometheus is not configured. Prometheus URL is missing"

            metrics = fetch_metrics(prometheus_url)

            if params.get("name_filter"):
                metrics = filter_metrics_by_name(metrics, params.get("name_filter"))

            if params.get("type_filter"):
                metrics = filter_metrics_by_type(metrics, params.get("type_filter"))

            logging.info(f"Using prometheus URL {self._config.url}")

            output = ["Metric | Type | Labels"]
            output.append("-" * 100)  # Separator line

            for metric, info in sorted(metrics.items()):
                labels_str = ", ".join(sorted(info['labels'])) if info['labels'] else "none"
                output.append(f"{metric} | {info['type']} | {labels_str}")

            return "\n".join(output)

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


class ExecuteQuery(Tool):
    def __init__(self, config:PrometheusConfig):
        super().__init__(
            name="execute_prometheus_query",
            description="Execute a PromQL query",
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
                )
            },
        )
        self._config = config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"

        try:
            query = params.get("query", "")
            description = params.get("description", "")

            url = urljoin(self._config.url, "/api/v1/query")

            payload = {
                "query": query
            }

            response = requests.post(
                url=url,
                data=payload,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                data["random_key"] = generate_random_key()
                data["tool_name"] = self.name
                data["description"] = description
                data["query"] = query
                data_str = json.dumps(data, indent=2)
                return data_str

            # Handle known Prometheus error status codes
            error_msg = "Unknown error occurred"
            if response.status_code in [400, 429]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_data.get("message", str(response.content)))
                except json.JSONDecodeError:
                    pass
                return f"Query execution failed. HTTP {response.status_code}: {error_msg}"

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
        return f'Prometheus query. query={query}, description={description}'


class ExecuteRangeQuery(Tool):
    def __init__(self, config:PrometheusConfig):
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
                )
            },
        )
        self._config = config

    def invoke(self, params: Any) -> str:
        if not self._config.url:
            return "Prometheus is not configured. Prometheus URL is missing"

        try:
            url = urljoin(self._config.url, "/api/v1/query_range")

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

            response = requests.post(
                url=url,
                data=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()

                data["random_key"] = generate_random_key()
                data["tool_name"] = self.name
                data["description"] = description
                data["query"] = query
                data["start"] = start
                data["end"] = end
                data["step"] = step
                data_str = json.dumps(data, indent=2)
                return data_str


            error_msg = "Unknown error occurred"
            if response.status_code in [400, 429]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_data.get("message", str(response.content)))
                except json.JSONDecodeError:
                    pass
                return f"Query execution failed. HTTP {response.status_code}: {error_msg}"

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
        return f'Prometheus query_range. query={query}, start={start}, end={end}, step={step}, description={description}'

class PrometheusToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="prometheus",
            description="Prometheus integration to fetch metadata and execute PromQL queries",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/3/38/Prometheus_software_logo.svg",
            prerequisites=[
                CallablePrerequisite(callable=self.prerequisites_callable)
            ],
            tools=[
                ListAvailableMetrics(self),
                ExecuteQuery(self),
                ExecuteRangeQuery(self)
            ],
            tags=[ToolsetTag.CORE,]
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
            if not config:
                return False

            self._config = PrometheusConfig(**config)
            return True
