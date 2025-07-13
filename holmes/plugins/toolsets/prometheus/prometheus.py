import json
import logging
import os
import random
import re
import string
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import requests  # type: ignore
from pydantic import BaseModel, field_validator
from requests import RequestException

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION
from holmes.plugins.toolsets.service_discovery import PrometheusDiscovery
from holmes.plugins.toolsets.utils import (
    get_param_or_raise,
    process_timestamps_to_rfc3339,
    standard_start_datetime_tool_param_description,
)
from holmes.utils.cache import TTLCache

PROMETHEUS_RULES_CACHE_KEY = "cached_prometheus_rules"
DEFAULT_TIME_SPAN_SECONDS = 3600


class PrometheusConfig(BaseModel):
    # URL is optional because it can be set with an env var
    prometheus_url: Optional[str]
    healthcheck: str = "-/healthy"
    # Setting to None will remove the time window from the request for labels
    metrics_labels_time_window_hrs: Union[int, None] = 48
    # Setting to None will disable the cache
    metrics_labels_cache_duration_hrs: Union[int, None] = 12
    fetch_labels_with_labels_api: bool = False
    fetch_metadata_with_series_api: bool = False
    tool_calls_return_data: bool = True
    headers: Dict = {}
    rules_cache_duration_seconds: Union[int, None] = 1800  # 30 minutes
    additional_labels: Optional[Dict[str, str]] = None

    @field_validator("prometheus_url")
    def ensure_trailing_slash(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.endswith("/"):
            return v + "/"
        return v


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
    params: Dict = {"match[]": f'{{__name__=~".*{metric_name}.*"}}', "limit": "10000"}

    response = requests.get(
        url, headers=headers, timeout=60, params=params, verify=True
    )
    response.raise_for_status()
    metrics = response.json()["data"]

    metadata: Dict = {}
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
    params: dict = {"match[]": f'{{__name__=~".*{metric_name}.*"}}', "limit": "10000"}

    if metrics_labels_time_window_hrs is not None:
        params["end"] = int(time.time())
        params["start"] = params["end"] - (metrics_labels_time_window_hrs * 60 * 60)

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
            params["end"] = int(time.time())
            params["start"] = params["end"] - (metrics_labels_time_window_hrs * 60 * 60)

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
        if should_fetch_labels_with_labels_api:
            metrics_labels = fetch_metrics_labels_with_labels_api(
                prometheus_url=prometheus_url,
                cache=cache,
                metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
                metric_names=list(metrics.keys()),
                headers=headers,
            )
        else:
            metrics_labels = fetch_metrics_labels_with_series_api(
                prometheus_url=prometheus_url,
                cache=cache,
                metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
                metric_name=metric_name,
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

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Prometheus is not configured. Prometheus URL is missing",
                params=params,
            )
        if not self._cache and self.toolset.config.rules_cache_duration_seconds:
            self._cache = TTLCache(self.toolset.config.rules_cache_duration_seconds)  # type: ignore
        try:
            if self._cache:
                cached_rules = self._cache.get(PROMETHEUS_RULES_CACHE_KEY)
                if cached_rules:
                    logging.debug("rules returned from cache")

                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS,
                        data=cached_rules,
                        params=params,
                    )

            prometheus_url = self.toolset.config.prometheus_url

            rules_url = urljoin(prometheus_url, "api/v1/rules")

            rules_response = requests.get(
                url=rules_url,
                params=params,
                timeout=180,
                verify=True,
                headers=self.toolset.config.headers,
            )
            rules_response.raise_for_status()
            data = rules_response.json()["data"]

            if self._cache:
                self._cache.set(PROMETHEUS_RULES_CACHE_KEY, data)
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=data,
                params=params,
            )
        except requests.Timeout:
            logging.warning("Timeout while fetching prometheus rules", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Request timed out while fetching rules",
                params=params,
            )
        except RequestException as e:
            logging.warning("Failed to fetch prometheus rules", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Network error while fetching rules: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.warning("Failed to process prometheus rules", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error: {str(e)}",
                params=params,
            )

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

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Prometheus is not configured. Prometheus URL is missing",
                params=params,
            )
        if not self._cache and self.toolset.config.metrics_labels_cache_duration_hrs:
            self._cache = TTLCache(
                self.toolset.config.metrics_labels_cache_duration_hrs * 3600  # type: ignore
            )
        try:
            prometheus_url = self.toolset.config.prometheus_url
            metrics_labels_time_window_hrs = (
                self.toolset.config.metrics_labels_time_window_hrs
            )

            name_filter = params.get("name_filter")
            if not name_filter:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Error: cannot run tool 'list_available_metrics'. The param 'name_filter' is required but is missing.",
                    params=params,
                )

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
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=table_output,
                params=params,
            )

        except requests.Timeout:
            logging.warn("Timeout while fetching prometheus metrics", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Request timed out while fetching metrics",
                params=params,
            )
        except RequestException as e:
            logging.warn("Failed to fetch prometheus metrics", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Network error while fetching metrics: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.warn("Failed to process prometheus metrics", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        return f'Search Available Prometheus Metrics: name_filter="{params.get("name_filter", "<no filter>")}", type_filter="{params.get("type_filter", "<no filter>")}"'


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

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Prometheus is not configured. Prometheus URL is missing",
                params=params,
            )
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
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=data_str,
                    params=params,
                )

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
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Query execution failed. HTTP {response.status_code}: {error_msg}",
                    params=params,
                )

            # For other status codes, just return the status code and content
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Query execution failed with unexpected status code: {response.status_code}. Response: {response.content}",
                params=params,
            )

        except RequestException as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Connection error to Prometheus: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error executing query: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        query = params.get("query")
        description = params.get("description")
        return f"Execute Prometheus Query (instant): promql='{query}', description='{description}'"


class ExecuteRangeQuery(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="execute_prometheus_range_query",
            description="Generates a graph and Execute a PromQL range query",
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
                    description=standard_start_datetime_tool_param_description(
                        DEFAULT_TIME_SPAN_SECONDS
                    ),
                    type="string",
                    required=False,
                ),
                "end": ToolParameter(
                    description=STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
                    type="string",
                    required=False,
                ),
                "step": ToolParameter(
                    description="Query resolution step width in duration format or float number of seconds",
                    type="number",
                    required=True,
                ),
                "output_type": ToolParameter(
                    description="Specifies how to interpret the Prometheus result. Use 'Plain' for raw values, 'Bytes' to format byte values, 'Percentage' to scale 0–1 values into 0–100%, or 'CPUUsage' to convert values to cores (e.g., 500 becomes 500m, 2000 becomes 2).",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Prometheus is not configured. Prometheus URL is missing",
                params=params,
            )

        try:
            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query_range")

            query = get_param_or_raise(params, "query")
            (start, end) = process_timestamps_to_rfc3339(
                start_timestamp=params.get("start"),
                end_timestamp=params.get("end"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )
            step = params.get("step", "")
            description = params.get("description", "")
            output_type = params.get("output_type", "Plain")
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
                    "output_type": output_type,
                }

                if self.toolset.config.tool_calls_return_data:
                    response_data["data"] = data.get("data")
                data_str = json.dumps(response_data, indent=2)
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=data_str,
                    params=params,
                )

            error_msg = "Unknown error occurred"
            if response.status_code in [400, 429]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error", error_data.get("message", str(response.content))
                    )
                except json.JSONDecodeError:
                    pass
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Query execution failed. HTTP {response.status_code}: {error_msg}",
                    params=params,
                )

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Query execution failed with unexpected status code: {response.status_code}. Response: {response.content}",
                params=params,
            )

        except RequestException as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Connection error to Prometheus: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error executing query: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        query = params.get("query")
        start = params.get("start")
        end = params.get("end")
        step = params.get("step")
        description = params.get("description")
        return f"Execute Prometheus Query (range): promql='{query}', start={start}, end={end}, step={step}, description='{description}'"


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
        self._reload_llm_instructions()

    def _reload_llm_instructions(self):
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "prometheus_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if config:
            self.config = PrometheusConfig(**config)
            self._reload_llm_instructions()
            return self._is_healthy()

        prometheus_url = os.environ.get("PROMETHEUS_URL")
        if not prometheus_url:
            prometheus_url = self.auto_detect_prometheus_url()
            if not prometheus_url:
                return (
                    False,
                    "Unable to auto-detect prometheus. Define prometheus_url in the configuration for tool prometheus/metrics",
                )

        self.config = PrometheusConfig(
            prometheus_url=prometheus_url,
            headers=add_prometheus_auth(os.environ.get("PROMETHEUS_AUTH_HEADER")),
        )
        logging.info(f"Prometheus auto discovered at url {prometheus_url}")
        self._reload_llm_instructions()
        return self._is_healthy()

    def auto_detect_prometheus_url(self) -> Optional[str]:
        url: Optional[str] = PrometheusDiscovery.find_prometheus_url()
        if not url:
            url = PrometheusDiscovery.find_vm_url()

        return url

    def _is_healthy(self) -> Tuple[bool, str]:
        if (
            not hasattr(self, "config")
            or not self.config
            or not self.config.prometheus_url
        ):
            return (
                False,
                f"Toolset {self.name} failed to initialize because prometheus is not configured correctly",
            )

        url = urljoin(self.config.prometheus_url, self.config.healthcheck)
        try:
            response = requests.get(
                url=url, headers=self.config.headers, timeout=10, verify=True
            )

            if response.status_code == 200:
                return True, ""
            else:
                return (
                    False,
                    f"Failed to connect to Prometheus at {url}: HTTP {response.status_code}",
                )

        except RequestException:
            return (
                False,
                f"Failed to initialize using url={url}",
            )
        except Exception as e:
            return (
                False,
                f"Failed to initialize using url={url}. Unexpected error: {str(e)}",
            )

    def get_example_config(self):
        example_config = PrometheusConfig(
            prometheus_url="http://robusta-kube-prometheus-st-prometheus:9090"
        )
        return example_config.model_dump()
