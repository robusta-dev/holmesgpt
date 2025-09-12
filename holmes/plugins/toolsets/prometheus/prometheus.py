import json
import logging
import os
import re
import time
import dateutil.parser
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from urllib.parse import urljoin

import requests  # type: ignore
from pydantic import BaseModel, field_validator, Field, model_validator
from requests import RequestException
from prometrix.connect.aws_connect import AWSPrometheusConnect
from prometrix.models.prometheus_config import PrometheusConfig as BasePrometheusConfig
from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    StructuredToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION
from holmes.plugins.toolsets.prometheus.utils import parse_duration_to_seconds
from holmes.plugins.toolsets.service_discovery import PrometheusDiscovery
from holmes.plugins.toolsets.utils import (
    get_param_or_raise,
    process_timestamps_to_rfc3339,
    standard_start_datetime_tool_param_description,
    toolset_name_for_one_liner,
)
from holmes.utils.cache import TTLCache
from holmes.common.env_vars import IS_OPENSHIFT, MAX_GRAPH_POINTS
from holmes.common.openshift import load_openshift_token
from holmes.plugins.toolsets.logging_utils.logging_api import (
    DEFAULT_GRAPH_TIME_SPAN_SECONDS,
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
    query_response_size_limit: Optional[int] = (
        80000  # Limit the max number of characters in a query result to proactively prevent truncation and advise LLM to query less data
    )

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


class AMPConfig(PrometheusConfig):
    aws_access_key: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str
    aws_service_name: str = "aps"
    healthcheck: str = "api/v1/query?query=up"
    prometheus_ssl_enabled: bool = False
    assume_role_arn: Optional[str] = None

    # Refresh the AWS client (and its STS creds) every N seconds (default: 15 minutes)
    refresh_interval_seconds: int = 900

    _aws_client: Optional[AWSPrometheusConnect] = None
    _aws_client_created_at: float = 0.0

    def is_amp(self) -> bool:
        return True

    def _should_refresh_client(self) -> bool:
        if not self._aws_client:
            return True
        return (
            time.time() - self._aws_client_created_at
        ) >= self.refresh_interval_seconds

    def get_aws_client(self) -> Optional[AWSPrometheusConnect]:
        if not self._aws_client or self._should_refresh_client():
            try:
                base_config = BasePrometheusConfig(
                    url=self.prometheus_url,
                    disable_ssl=not self.prometheus_ssl_enabled,
                    additional_labels=self.additional_labels,
                )
                self._aws_client = AWSPrometheusConnect(
                    access_key=self.aws_access_key,
                    secret_key=self.aws_secret_access_key,
                    token=None,
                    region=self.aws_region,
                    service_name=self.aws_service_name,
                    assume_role_arn=self.assume_role_arn,
                    config=base_config,
                )
                self._aws_client_created_at = time.time()
            except Exception:
                logging.exception("Failed to create/refresh AWS client")
                return self._aws_client
        return self._aws_client


class BasePrometheusTool(Tool):
    toolset: "PrometheusToolset"


def do_request(
    config,  # PrometheusConfig | AMPConfig
    url: str,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None,
    timeout: int = 60,
    verify: Optional[bool] = None,
    headers: Optional[Dict] = None,
    method: str = "GET",
) -> requests.Response:
    """
    Route a request through either:
      - AWSPrometheusConnect (SigV4) when config is AMPConfig
      - plain requests otherwise

    method defaults to GET so callers can omit it for reads.
    """
    if verify is None:
        verify = config.prometheus_ssl_enabled
    if headers is None:
        headers = config.headers or {}

    if isinstance(config, AMPConfig):
        client = config.get_aws_client()  # cached AWSPrometheusConnect
        return client.signed_request(  # type: ignore
            method=method,
            url=url,
            data=data,
            params=params,
            verify=verify,
            headers=headers,
        )

    # Non-AMP: plain HTTP
    return requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        data=data,
        timeout=timeout,
        verify=verify,
    )


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
    config,
    verify_ssl: bool = True,
) -> Dict:
    metadata_url = urljoin(prometheus_url, "api/v1/metadata")
    metadata_response = do_request(
        config=config,
        url=metadata_url,
        headers=headers,
        timeout=60,
        verify=verify_ssl,
        method="GET",
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
    config,
    verify_ssl: bool = True,
) -> Dict:
    url = urljoin(prometheus_url, "api/v1/series")
    params: Dict = {"match[]": f'{{__name__=~".*{metric_name}.*"}}', "limit": "10000"}

    response = do_request(
        config=config,
        url=url,
        headers=headers,
        params=params,
        timeout=60,
        verify=verify_ssl,
        method="GET",
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


def adjust_step_for_max_points(
    start_timestamp: str,
    end_timestamp: str,
    step: Optional[float] = None,
) -> float:
    """
    Adjusts the step parameter to ensure the number of data points doesn't exceed max_points.
    Max points is controlled by the PROMETHEUS_MAX_GRAPH_POINTS environment variable (default: 300).

    Args:
        start_timestamp: RFC3339 formatted start time
        end_timestamp: RFC3339 formatted end time
        step: The requested step duration in seconds (None for auto-calculation)

    Returns:
        Adjusted step value in seconds that ensures points <= max_points
    """

    start_dt = dateutil.parser.parse(start_timestamp)
    end_dt = dateutil.parser.parse(end_timestamp)

    time_range_seconds = (end_dt - start_dt).total_seconds()

    # If no step provided, calculate a reasonable default
    # Aim for ~60 data points across the time range (1 per minute for hourly, etc)
    if step is None:
        step = max(1, time_range_seconds / 60)
        logging.debug(
            f"No step provided, defaulting to {step}s for {time_range_seconds}s range"
        )

    current_points = time_range_seconds / step

    # If current points exceed max, adjust the step
    if current_points > MAX_GRAPH_POINTS:
        adjusted_step = time_range_seconds / MAX_GRAPH_POINTS
        logging.info(
            f"Adjusting step from {step}s to {adjusted_step}s to limit points from {current_points:.0f} to {MAX_GRAPH_POINTS}"
        )
        return adjusted_step

    return step


def add_prometheus_auth(prometheus_auth_header: Optional[str]) -> Dict[str, Any]:
    results = {}
    if prometheus_auth_header:
        results["Authorization"] = prometheus_auth_header
    return results


def create_data_summary_for_large_result(
    result_data: Dict, query: str, data_size_chars: int, is_range_query: bool = False
) -> Dict[str, Any]:
    """
    Create a summary for large Prometheus results instead of returning full data.

    Args:
        result_data: The Prometheus data result
        query: The original PromQL query
        data_size_chars: Size of the data in characters
        is_range_query: Whether this is a range query (vs instant query)

    Returns:
        Dictionary with summary information and suggestions
    """
    if is_range_query:
        series_list = result_data.get("result", [])
        num_items = len(series_list)

        # Calculate statistics for range queries
        total_points = 0
        for series in series_list[:10]:  # Sample first 10 series
            points = len(series.get("values", []))
            total_points += points

        avg_points_per_series = (
            total_points / min(10, num_items) if num_items > 0 else 0
        )
        estimated_total_points = avg_points_per_series * num_items

        # Create a sample of just the metadata (labels) without values
        sample_metrics = []
        for series in series_list[:10]:  # Sample first 10 series
            sample_metrics.append(series.get("metric", {}))

        sample_json = json.dumps(sample_metrics, indent=2)
        if len(sample_json) > 2000:
            sample_json = sample_json[:2000] + "\n... (truncated)"

        return {
            "message": f"Data too large to return ({data_size_chars:,} characters). Query returned {num_items} time series with approximately {estimated_total_points:,.0f} total data points.",
            "series_count": num_items,
            "estimated_total_points": int(estimated_total_points),
            "data_size_characters": data_size_chars,
            "sample_data": sample_json,
            "suggestion": f'Consider using topk({min(5, num_items)}, {query}) to limit results to the top {min(5, num_items)} series. To also capture remaining data as \'other\': topk({min(5, num_items)}, {query}) or label_replace((sum({query}) - sum(topk({min(5, num_items)}, {query}))), "pod", "other", "", "")',
        }
    else:
        # Instant query
        result_type = result_data.get("resultType", "")
        result_list = result_data.get("result", [])
        num_items = len(result_list)

        # Create a sample of just the metadata (labels) without values
        sample_metrics = []
        for item in result_list[:10]:  # Sample first 10 results
            if isinstance(item, dict):
                sample_metrics.append(item.get("metric", {}))

        sample_json = json.dumps(sample_metrics, indent=2)
        if len(sample_json) > 2000:
            sample_json = sample_json[:2000] + "\n... (truncated)"

        return {
            "message": f"Data too large to return ({data_size_chars:,} characters). Query returned {num_items} results.",
            "result_count": num_items,
            "result_type": result_type,
            "data_size_characters": data_size_chars,
            "sample_data": sample_json,
            "suggestion": f'Consider using topk({min(5, num_items)}, {query}) to limit results. To also capture remaining data as \'other\': topk({min(5, num_items)}, {query}) or label_replace((sum({query}) - sum(topk({min(5, num_items)}, {query}))), "instance", "other", "", "")',
        }


def fetch_metrics_labels_with_series_api(
    prometheus_url: str,
    headers: Dict[str, str],
    cache: Optional[TTLCache],
    metrics_labels_time_window_hrs: Union[int, None],
    metric_name: str,
    config=None,
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

    series_response = do_request(
        config=config,
        url=series_url,
        headers=headers,
        params=params,
        timeout=60,
        verify=verify_ssl,
        method="GET",
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
    config=None,
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

        response = do_request(
            config=config,
            url=url,
            headers=headers,
            params=params,
            timeout=60,
            verify=verify_ssl,
            method="GET",
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
    config=None,
    verify_ssl: bool = True,
) -> dict:
    metrics = None
    should_fetch_labels = True
    if should_fetch_metadata_with_series_api:
        metrics = fetch_metadata_with_series_api(
            prometheus_url=prometheus_url,
            metric_name=metric_name,
            headers=headers,
            config=config,
            verify_ssl=verify_ssl,
        )
        should_fetch_labels = False  # series API returns the labels
    else:
        metrics = fetch_metadata(
            prometheus_url=prometheus_url,
            headers=headers,
            config=config,
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
                config=config,
                verify_ssl=verify_ssl,
            )
        else:
            metrics_labels = fetch_metrics_labels_with_series_api(
                prometheus_url=prometheus_url,
                cache=cache,
                metrics_labels_time_window_hrs=metrics_labels_time_window_hrs,
                metric_name=metric_name,
                headers=headers,
                config=config,
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

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error="Prometheus is not configured. Prometheus URL is missing",
                params=params,
            )
        if self.toolset.config.is_amp():
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
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
                        status=StructuredToolResultStatus.SUCCESS,
                        data=cached_rules,
                        params=params,
                    )

            prometheus_url = self.toolset.config.prometheus_url

            rules_url = urljoin(prometheus_url, "api/v1/rules")

            rules_response = do_request(
                config=self.toolset.config,
                url=rules_url,
                params=params,
                timeout=180,
                verify=self.toolset.config.prometheus_ssl_enabled,
                headers=self.toolset.config.headers,
                method="GET",
            )
            rules_response.raise_for_status()
            data = rules_response.json()["data"]

            if self._cache:
                self._cache.set(PROMETHEUS_RULES_CACHE_KEY, data)
            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=data,
                params=params,
            )
        except requests.Timeout:
            logging.warning("Timeout while fetching prometheus rules", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error="Request timed out while fetching rules",
                params=params,
            )
        except RequestException as e:
            logging.warning("Failed to fetch prometheus rules", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Network error while fetching rules: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.warning("Failed to process prometheus rules", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
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

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
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
                    status=StructuredToolResultStatus.ERROR,
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
                config=self.toolset.config,
                verify_ssl=self.toolset.config.prometheus_ssl_enabled,
            )

            type_filter = params.get("type_filter")
            if type_filter:
                metrics = filter_metrics_by_type(metrics, type_filter)

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
                status=StructuredToolResultStatus.SUCCESS,
                data=table_output,
                params=params,
            )

        except requests.Timeout:
            logging.warn("Timeout while fetching prometheus metrics", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error="Request timed out while fetching metrics",
                params=params,
            )
        except RequestException as e:
            logging.warn("Failed to fetch prometheus metrics", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Network error while fetching metrics: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.warn("Failed to process prometheus metrics", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
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

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error="Prometheus is not configured. Prometheus URL is missing",
                params=params,
            )
        try:
            query = params.get("query", "")
            description = params.get("description", "")

            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query")

            payload = {"query": query}

            response = do_request(
                config=self.toolset.config,
                url=url,
                headers=self.toolset.config.headers,
                data=payload,
                timeout=60,
                verify=self.toolset.config.prometheus_ssl_enabled,
                method="POST",
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

                # Check if data should be included based on size
                if self.toolset.config.tool_calls_return_data:
                    result_data = data.get("data", {})

                    # Estimate the size of the data
                    data_str_preview = json.dumps(result_data)
                    data_size_chars = len(data_str_preview)

                    # Provide summary if data is too large
                    if (
                        self.toolset.config.query_response_size_limit
                        and data_size_chars
                        > self.toolset.config.query_response_size_limit
                    ):
                        response_data["data_summary"] = (
                            create_data_summary_for_large_result(
                                result_data,
                                query,
                                data_size_chars,
                                is_range_query=False,
                            )
                        )
                        logging.info(
                            f"Prometheus instant query returned large dataset: "
                            f"{response_data['data_summary'].get('result_count', 0)} results, "
                            f"{data_size_chars:,} characters. Returning summary instead of full data."
                        )
                    else:
                        response_data["data"] = result_data

                data_str = json.dumps(response_data, indent=2)
                return StructuredToolResult(
                    status=StructuredToolResultStatus.SUCCESS,
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
                    status=StructuredToolResultStatus.ERROR,
                    error=f"Query execution failed. HTTP {response.status_code}: {error_msg}",
                    params=params,
                )

            # For other status codes, just return the status code and content
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Query execution failed with unexpected status code: {response.status_code}. Response: {str(response.content)}",
                params=params,
            )

        except RequestException as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Connection error to Prometheus: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
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
                        DEFAULT_GRAPH_TIME_SPAN_SECONDS
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
                    required=False,
                ),
                "output_type": ToolParameter(
                    description="Specifies how to interpret the Prometheus result. Use 'Plain' for raw values, 'Bytes' to format byte values, 'Percentage' to scale 0–1 values into 0–100%, or 'CPUUsage' to convert values to cores (e.g., 500 becomes 500m, 2000 becomes 2).",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.prometheus_url:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error="Prometheus is not configured. Prometheus URL is missing",
                params=params,
            )

        try:
            url = urljoin(self.toolset.config.prometheus_url, "api/v1/query_range")

            query = get_param_or_raise(params, "query")
            (start, end) = process_timestamps_to_rfc3339(
                start_timestamp=params.get("start"),
                end_timestamp=params.get("end"),
                default_time_span_seconds=DEFAULT_GRAPH_TIME_SPAN_SECONDS,
            )
            step = parse_duration_to_seconds(params.get("step"))

            # adjust_step_for_max_points handles None case and converts to float
            step = adjust_step_for_max_points(
                start_timestamp=start,
                end_timestamp=end,
                step=step,
            )

            description = params.get("description", "")
            output_type = params.get("output_type", "Plain")
            payload = {
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            }

            response = do_request(
                config=self.toolset.config,
                url=url,
                headers=self.toolset.config.headers,
                data=payload,
                timeout=120,
                verify=self.toolset.config.prometheus_ssl_enabled,
                method="POST",
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

                # Check if data should be included based on size
                if self.toolset.config.tool_calls_return_data:
                    result_data = data.get("data", {})

                    # Estimate the size of the data
                    data_str_preview = json.dumps(result_data)
                    data_size_chars = len(data_str_preview)

                    # Provide summary if data is too large
                    if (
                        self.toolset.config.query_response_size_limit
                        and data_size_chars
                        > self.toolset.config.query_response_size_limit
                    ):
                        response_data["data_summary"] = (
                            create_data_summary_for_large_result(
                                result_data, query, data_size_chars, is_range_query=True
                            )
                        )
                        logging.info(
                            f"Prometheus range query returned large dataset: "
                            f"{response_data['data_summary'].get('series_count', 0)} series, "
                            f"{data_size_chars:,} characters. Returning summary instead of full data."
                        )
                    else:
                        response_data["data"] = result_data

                data_str = json.dumps(response_data, indent=2)

                return StructuredToolResult(
                    status=StructuredToolResultStatus.SUCCESS,
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
                    status=StructuredToolResultStatus.ERROR,
                    error=f"Query execution failed. HTTP {response.status_code}: {error_msg}",
                    params=params,
                )

            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Query execution failed with unexpected status code: {response.status_code}. Response: {str(response.content)}",
                params=params,
            )

        except RequestException as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Connection error to Prometheus: {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.info("Failed to connect to Prometheus", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Unexpected error executing query: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        description = params.get("description", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Query ({description})"


class PrometheusToolset(Toolset):
    config: Optional[Union[PrometheusConfig, AMPConfig]] = None

    def __init__(self):
        super().__init__(
            name="prometheus/metrics",
            description="Prometheus integration to fetch metadata and execute PromQL queries",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/prometheus/",
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

    def determine_prometheus_class(
        self, config: dict[str, Any]
    ) -> Type[Union[PrometheusConfig, AMPConfig]]:
        has_aws_fields = "aws_region" in config
        return AMPConfig if has_aws_fields else PrometheusConfig

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
            response = do_request(
                config=self.config,
                url=url,
                headers=self.config.headers,
                timeout=10,
                verify=self.config.prometheus_ssl_enabled,
                method="GET",
            )

            if response.status_code == 200:
                return True, ""
            else:
                return (
                    False,
                    f"Failed to connect to Prometheus at {url}: HTTP {response.status_code}",
                )

        except Exception as e:
            logging.exception("Failed to initialize Prometheus", exc_info=True)
            return (
                False,
                f"Failed to initialize using url={url}. Unexpected error: {str(e)}",
            )

    def get_example_config(self):
        example_config = PrometheusConfig(
            prometheus_url="http://robusta-kube-prometheus-st-prometheus:9090"
        )
        return example_config.model_dump()
