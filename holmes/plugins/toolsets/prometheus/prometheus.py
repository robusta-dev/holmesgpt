import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from urllib.parse import urljoin

import requests  # type: ignore
from pydantic import BaseModel, field_validator, Field, model_validator
from requests import RequestException
from requests_aws4auth import AWS4Auth

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
    toolset_name_for_one_liner,
)
from holmes.utils.cache import TTLCache
from holmes.common.env_vars import IS_OPENSHIFT
from holmes.common.openshift import load_openshift_token
from holmes.plugins.toolsets.logging_utils.logging_api import (
    DEFAULT_TIME_SPAN_SECONDS,
)
from holmes.utils.keygen_utils import generate_random_key

PROMETHEUS_RULES_CACHE_KEY = "cached_prometheus_rules"


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
    headers: Dict = Field(default_factory=dict)
    rules_cache_duration_seconds: Union[int, None] = 1800  # 30 minutes
    additional_labels: Optional[Dict[str, str]] = None
    prometheus_ssl_enabled: bool = True

    @field_validator("prometheus_url")
    def ensure_trailing_slash(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.endswith("/"):
            return v + "/"
        return v

    @model_validator(mode="after")
    def validate_prom_config(self):
        # If openshift is enabled, and the user didn't configure auth headers, we will try to load the token from the service account.
        if IS_OPENSHIFT:
            if self.healthcheck == "-/healthy":
                self.healthcheck = "api/v1/query?query=up"

            if self.headers.get("Authorization"):
                return self

            openshift_token = load_openshift_token()
            if openshift_token:
                logging.info("Using openshift token for prometheus toolset auth")
                self.headers["Authorization"] = f"Bearer {openshift_token}"

        return self

    def is_amp(self) -> bool:
        return False

    def get_auth(self) -> Any:
        return None


class AMPConfig(PrometheusConfig):
    aws_access_key: str
    aws_secret_access_key: str
    aws_region: str
    aws_service_name: str = "aps"
    healthcheck: str = "api/v1/query?query=up"  # Override for AMP
    prometheus_ssl_enabled: bool = False

    def is_amp(self) -> bool:
        return True

    def get_auth(self):
        return AWS4Auth(
            self.aws_access_key,  # type: ignore
            self.aws_secret_access_key,  # type: ignore
            self.aws_region,  # type: ignore
            self.aws_service_name,  # type: ignore
        )


class BasePrometheusTool(Tool):
    toolset: "PrometheusToolset"


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


def fetch_metadata(
    prometheus_url: str,
    headers: Optional[Dict],
    auth=None,
    verify_ssl: bool = True,
) -> Dict:
    metadata_url = urljoin(prometheus_url, "api/v1/metadata")
    metadata_response = requests.get(
        metadata_url, headers=headers, timeout=60, verify=verify_ssl, auth=auth
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
    prometheus_url: str,
    metric_name: str,
    headers: Dict,
    auth=None,
    verify_ssl: bool = True,
) -> Dict:
    url = urljoin(prometheus_url, "api/v1/series")
    params: Dict = {"match[]": f'{{__name__=~".*{metric_name}.*"}}', "limit": "10000"}

    response = requests.get(
        url, headers=headers, timeout=60, params=params, auth=auth, verify=verify_ssl
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
    auth=None,
    verify_ssl: bool = True,
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
        url=series_url,
        headers=headers,
        params=params,
        auth=auth,
        timeout=60,
        verify=verify_ssl,
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
    auth=None,
    verify_ssl: bool = True,
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
            url=url,
            headers=headers,
            params=params,
            auth=auth,
            timeout=60,
            verify=verify_ssl,
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
    auth=None,
    verify_ssl: bool = True,
) -> dict:
    metrics = None
    should_fetch_labels = True
    if should_fetch_metadata_with_series_api:
        metrics = fetch_metadata_with_series_api(
            prometheus_url=prometheus_url,
            metric_name=metric_name,
            headers=headers,
            auth=auth,
            verify_ssl=verify_ssl,
        )
        should_fetch_labels = False  # series API returns the labels
    else:
        metrics = fetch_metadata(
            prometheus_url=prometheus_url,
            headers=headers,
            auth=auth,
            verify_ssl=verify_ssl,
        )
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
                auth=auth,
                verify_ssl=verify_ssl,
            )
        else:
            metrics_labels = fetch_metrics_labels_with_series_api(
                prometheus_url=prometheus_url,
                cache=cache,
                metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
                metric_name=metric_name,
                headers=headers,
                auth=auth,
                verify_ssl=verify_ssl,
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
        if self.toolset.config.is_amp():
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Tool not supported in AMP",
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
                auth=self.toolset.config.get_auth(),
                timeout=180,
                verify=self.toolset.config.prometheus_ssl_enabled,
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
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Fetch Rules"


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
                auth=self.toolset.config.get_auth(),
                verify_ssl=self.toolset.config.prometheus_ssl_enabled,
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
        name_filter = params.get("name_filter", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Search Metrics ({name_filter})"


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
                url=url,
                headers=self.toolset.config.headers,
                auth=self.toolset.config.get_auth(),
                data=payload,
                timeout=60,
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
                error=f"Query execution failed with unexpected status code: {response.status_code}. Response: {str(response.content)}",
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
        description = params.get("description", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Query ({description})"


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
                url=url,
                headers=self.toolset.config.headers,
                auth=self.toolset.config.get_auth(),
                data=payload,
                timeout=120,
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
                error=f"Query execution failed with unexpected status code: {response.status_code}. Response: {str(response.content)}",
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
        description = params.get("description", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Query ({description})"


class AnalyzeMetricByDimensions(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="analyze_metric_by_dimensions",
            description="Analyzes any metric broken down by its available label dimensions. Automatically discovers available labels from the metric.",
            parameters={
                "metric_name": ToolParameter(
                    description="The metric name to analyze",
                    type="string",
                    required=True,
                ),
                "group_by": ToolParameter(
                    description="Labels to group by (will be validated against available labels)",
                    type="array",
                    required=False,
                ),
                "filters": ToolParameter(
                    description="Label filters to apply as key-value pairs",
                    type="object",
                    required=False,
                ),
                "percentiles": ToolParameter(
                    description="For histogram/summary metrics - percentiles to calculate",
                    type="array",
                    required=False,
                ),
                "time_range": ToolParameter(
                    description="Time range for analysis (e.g., '5m', '1h', '24h')",
                    type="string",
                    required=False,
                ),
                "aggregation": ToolParameter(
                    description="Aggregation method (avg, sum, max, min, p50, p95, p99)",
                    type="string",
                    required=False,
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
            metric_name = get_param_or_raise(params, "metric_name")
            group_by = params.get("group_by", [])
            filters = params.get("filters", {})
            time_range = params.get("time_range", "1h")
            aggregation = params.get("aggregation", "avg")

            # Build the base query with filters
            filter_str = ""
            if filters:
                filter_items = [f'{k}="{v}"' for k, v in filters.items()]
                filter_str = "{" + ",".join(filter_items) + "}"

            # Build the query based on aggregation type
            if aggregation in ["p50", "p95", "p99"]:
                percentile = float(aggregation[1:]) / 100
                query = f"histogram_quantile({percentile}, sum(rate({metric_name}_bucket{filter_str}[{time_range}])) by (le"
                if group_by:
                    query += f", {', '.join(group_by)}"
                query += "))"
            elif group_by:
                query = f'{aggregation}(rate({metric_name}{filter_str}[{time_range}])) by ({", ".join(group_by)})'
            else:
                query = f"{aggregation}(rate({metric_name}{filter_str}[{time_range}]))"

            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query")
            payload = {"query": query}

            response = requests.post(
                url=url,
                headers=self.toolset.config.headers,
                auth=self.toolset.config.get_auth(),
                data=payload,
                timeout=60,
                verify=self.toolset.config.prometheus_ssl_enabled,
            )

            if response.status_code == 200:
                data = response.json()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=json.dumps(data.get("data"), indent=2),
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Query failed with status {response.status_code}: {response.text}",
                    params=params,
                )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error analyzing metric: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        metric_name = params.get("metric_name", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Analyze {metric_name} by dimensions"


class FindTopMetricValues(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="find_top_metric_values",
            description="Finds the highest values for any metric, grouped by labels. Useful for identifying outliers or slowest operations.",
            parameters={
                "metric_name": ToolParameter(
                    description="The metric to analyze",
                    type="string",
                    required=True,
                ),
                "group_by_label": ToolParameter(
                    description="Label to group results by",
                    type="string",
                    required=True,
                ),
                "top_n": ToolParameter(
                    description="Number of top entries to return",
                    type="integer",
                    required=False,
                ),
                "percentile": ToolParameter(
                    description="For histogram/summary metrics - percentile to use (e.g., 0.95)",
                    type="number",
                    required=False,
                ),
                "time_range": ToolParameter(
                    description="Time range for analysis",
                    type="string",
                    required=False,
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
            metric_name = get_param_or_raise(params, "metric_name")
            group_by_label = get_param_or_raise(params, "group_by_label")
            top_n = params.get("top_n", 10)
            percentile = params.get("percentile", 0.95)
            time_range = params.get("time_range", "1h")

            # Check if it's a histogram metric
            if "_bucket" in metric_name or percentile:
                query = f"topk({top_n}, histogram_quantile({percentile}, sum(rate({metric_name}_bucket[{time_range}])) by (le, {group_by_label})))"
            else:
                query = f"topk({top_n}, avg(rate({metric_name}[{time_range}])) by ({group_by_label}))"

            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query")
            payload = {"query": query}

            response = requests.post(
                url=url,
                headers=self.toolset.config.headers,
                auth=self.toolset.config.get_auth(),
                data=payload,
                timeout=60,
                verify=self.toolset.config.prometheus_ssl_enabled,
            )

            if response.status_code == 200:
                data = response.json()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=json.dumps(data.get("data"), indent=2),
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Query failed with status {response.status_code}: {response.text}",
                    params=params,
                )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error finding top values: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        metric_name = params.get("metric_name", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Find top values for {metric_name}"


class CompareMetricPeriods(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="compare_metric_periods",
            description="Compares a metric between two time periods to identify changes or degradations.",
            parameters={
                "metric_name": ToolParameter(
                    description="The metric to compare",
                    type="string",
                    required=True,
                ),
                "current_period": ToolParameter(
                    description="Current time period (e.g., '1h')",
                    type="string",
                    required=False,
                ),
                "comparison_offset": ToolParameter(
                    description="How far back to compare (e.g., '24h' for yesterday)",
                    type="string",
                    required=False,
                ),
                "group_by": ToolParameter(
                    description="Labels to group comparison by",
                    type="array",
                    required=False,
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
            metric_name = get_param_or_raise(params, "metric_name")
            current_period = params.get("current_period", "1h")
            comparison_offset = params.get("comparison_offset", "24h")
            group_by = params.get("group_by", [])

            # Build group by clause
            group_clause = ""
            if group_by:
                group_clause = f' by ({", ".join(group_by)})'

            # Query comparing current vs offset period
            query = f"""
                (avg(rate({metric_name}[{current_period}])){group_clause} -
                 avg(rate({metric_name}[{current_period}] offset {comparison_offset})){group_clause}) /
                 avg(rate({metric_name}[{current_period}] offset {comparison_offset})){group_clause} * 100
            """

            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query")
            payload = {"query": query}

            response = requests.post(
                url=url,
                headers=self.toolset.config.headers,
                auth=self.toolset.config.get_auth(),
                data=payload,
                timeout=60,
                verify=self.toolset.config.prometheus_ssl_enabled,
            )

            if response.status_code == 200:
                data = response.json()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=json.dumps(data.get("data"), indent=2),
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Query failed with status {response.status_code}: {response.text}",
                    params=params,
                )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error comparing periods: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        metric_name = params.get("metric_name", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Compare {metric_name} periods"


class DetectMetricAnomalies(BasePrometheusTool):
    def __init__(self, toolset: "PrometheusToolset"):
        super().__init__(
            name="detect_metric_anomalies",
            description="Detects anomalous patterns in metrics using statistical analysis. Identifies spikes and deviations from normal.",
            parameters={
                "metric_name": ToolParameter(
                    description="The metric to analyze",
                    type="string",
                    required=True,
                ),
                "sensitivity": ToolParameter(
                    description="Standard deviations for anomaly threshold (2-4 typical)",
                    type="number",
                    required=False,
                ),
                "lookback_window": ToolParameter(
                    description="Historical window for baseline (e.g., '7d')",
                    type="string",
                    required=False,
                ),
                "group_by": ToolParameter(
                    description="Labels to detect anomalies by",
                    type="array",
                    required=False,
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
            metric_name = get_param_or_raise(params, "metric_name")
            sensitivity = params.get("sensitivity", 3)
            lookback_window = params.get("lookback_window", "1h")
            group_by = params.get("group_by", [])

            # Build group by clause
            group_clause = ""
            if group_by:
                group_clause = f' by ({", ".join(group_by)})'

            # Z-score based anomaly detection query
            query = f"""
                (rate({metric_name}[5m]){group_clause} -
                 avg_over_time(rate({metric_name}[5m])[{lookback_window}:]){group_clause}) /
                 stddev_over_time(rate({metric_name}[5m])[{lookback_window}:]){group_clause} > {sensitivity}
            """

            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query")
            payload = {"query": query}

            response = requests.post(
                url=url,
                headers=self.toolset.config.headers,
                auth=self.toolset.config.get_auth(),
                data=payload,
                timeout=60,
                verify=self.toolset.config.prometheus_ssl_enabled,
            )

            if response.status_code == 200:
                data = response.json()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=json.dumps(data.get("data"), indent=2),
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Query failed with status {response.status_code}: {response.text}",
                    params=params,
                )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error detecting anomalies: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        metric_name = params.get("metric_name", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Detect anomalies in {metric_name}"


class PrometheusToolset(Toolset):
    config: Optional[Union[PrometheusConfig, AMPConfig]] = None

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
                AnalyzeMetricByDimensions(toolset=self),
                FindTopMetricValues(toolset=self),
                CompareMetricPeriods(toolset=self),
                DetectMetricAnomalies(toolset=self),
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

    def determine_prometheus_class(
        self, config: dict[str, Any]
    ) -> Type[Union[PrometheusConfig, AMPConfig]]:
        has_aws_credentials = (
            "aws_access_key" in config or "aws_secret_access_key" in config
        )
        return AMPConfig if has_aws_credentials else PrometheusConfig

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        try:
            if config:
                config_cls = self.determine_prometheus_class(config)
                self.config = config_cls(**config)  # type: ignore

                self._reload_llm_instructions()
                return self._is_healthy()
        except Exception:
            logging.exception("Failed to create prometheus config")
            return False, "Failed to create prometheus config"
        try:
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
        except Exception as e:
            logging.exception("Failed to set up prometheus")
            return False, str(e)

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
                url=url,
                headers=self.config.headers,
                auth=self.config.get_auth(),
                timeout=10,
                verify=self.config.prometheus_ssl_enabled,
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
