import json
import logging
import os
from typing import Any, Optional, Dict, Tuple
from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from tenacity import RetryError
from holmes.plugins.toolsets.consts import (
    TOOLSET_CONFIG_MISSING_ERROR,
    STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
)
from holmes.plugins.toolsets.datadog.datadog_api import (
    DatadogBaseConfig,
    DataDogRequestError,
    execute_datadog_http_request,
    get_headers,
    MAX_RETRY_COUNT_ON_RATE_LIMIT,
)
from holmes.plugins.toolsets.utils import (
    get_param_or_raise,
    process_timestamps_to_int,
    standard_start_datetime_tool_param_description,
)

DEFAULT_TIME_SPAN_SECONDS = 3600


class DatadogMetricsConfig(DatadogBaseConfig):
    default_limit: int = 1000


class BaseDatadogMetricsTool(Tool):
    toolset: "DatadogMetricsToolset"


ACTIVE_METRICS_DEFAULT_LOOK_BACK_HOURS = 24
ACTIVE_METRICS_DEFAULT_TIME_SPAN_SECONDS = 24 * 60 * 60


class ListActiveMetrics(BaseDatadogMetricsTool):
    def __init__(self, toolset: "DatadogMetricsToolset"):
        super().__init__(
            name="list_active_datadog_metrics",
            description=f"List active metrics from the last {ACTIVE_METRICS_DEFAULT_LOOK_BACK_HOURS} hours. This includes metrics that have actively reported data points.",
            parameters={
                "from_time": ToolParameter(
                    description=f"Start time for listing metrics. Can be an RFC3339 formatted datetime (e.g. '2023-03-01T10:30:00Z') or a negative integer for relative seconds from now (e.g. -86400 for 24 hours ago). Defaults to {ACTIVE_METRICS_DEFAULT_LOOK_BACK_HOURS} hours ago",
                    type="string",
                    required=False,
                ),
                "host": ToolParameter(
                    description="Filter metrics by hostname",
                    type="string",
                    required=False,
                ),
                "tag_filter": ToolParameter(
                    description="Filter metrics by tags in the format tag:value",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.dd_config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=TOOLSET_CONFIG_MISSING_ERROR,
                params=params,
            )

        url = None
        query_params = None

        try:
            from_time_str = params.get("from_time")

            from_time, _ = process_timestamps_to_int(
                start=from_time_str,
                end=None,
                default_time_span_seconds=ACTIVE_METRICS_DEFAULT_TIME_SPAN_SECONDS,
            )

            url = f"{self.toolset.dd_config.site_api_url}/api/v1/metrics"
            headers = get_headers(self.toolset.dd_config)

            query_params = {
                "from": from_time,
            }

            if params.get("host"):
                query_params["host"] = params["host"]

            if params.get("tag_filter"):
                query_params["tag_filter"] = params["tag_filter"]

            data = execute_datadog_http_request(
                url=url,
                headers=headers,
                timeout=self.toolset.dd_config.request_timeout,
                method="GET",
                payload_or_params=query_params,
            )

            metrics = data.get("metrics", [])

            output = ["Metric Name"]
            output.append("-" * 50)

            for metric in sorted(metrics):
                output.append(metric)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data="\n".join(output),
                params=params,
            )

        except DataDogRequestError as e:
            logging.exception(e, exc_info=True)

            if e.status_code == 429:
                error_msg = f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts."
            elif e.status_code == 403:
                error_msg = (
                    f"Permission denied. Ensure your Datadog Application Key has the 'metrics_read' "
                    f"and 'timeseries_query' permissions. Error: {str(e)}"
                )
            else:
                error_msg = f"Exception while querying Datadog: {str(e)}"

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
                invocation=json.dumps({"url": url, "params": query_params})
                if url and query_params
                else None,
            )

        except Exception as e:
            logging.exception(
                f"Failed to query Datadog metrics for params: {params}", exc_info=True
            )

            if isinstance(e, RetryError):
                try:
                    original_error = e.last_attempt.exception()
                    if (
                        isinstance(original_error, DataDogRequestError)
                        and original_error.status_code == 429
                    ):
                        return StructuredToolResult(
                            status=ToolResultStatus.ERROR,
                            error=f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts.",
                            params=params,
                        )
                except Exception:
                    pass

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception while querying Datadog: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        filters = []
        if params.get("host"):
            filters.append(f"host={params['host']}")
        if params.get("tag_filter"):
            filters.append(f"tag_filter={params['tag_filter']}")
        filter_str = f" with filters: {', '.join(filters)}" if filters else ""
        return f"List active Datadog metrics{filter_str}"


class QueryMetrics(BaseDatadogMetricsTool):
    def __init__(self, toolset: "DatadogMetricsToolset"):
        super().__init__(
            name="query_datadog_metrics",
            description="Query timeseries data for a specific metric",
            parameters={
                "query": ToolParameter(
                    description="The metric query string (e.g., 'system.cpu.user{host:myhost}')",
                    type="string",
                    required=True,
                ),
                "from_time": ToolParameter(
                    description=standard_start_datetime_tool_param_description(
                        DEFAULT_TIME_SPAN_SECONDS
                    ),
                    type="string",
                    required=False,
                ),
                "to_time": ToolParameter(
                    description=STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.dd_config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=TOOLSET_CONFIG_MISSING_ERROR,
                params=params,
            )

        url = None
        query_params = None

        try:
            query = get_param_or_raise(params, "query")

            (from_time, to_time) = process_timestamps_to_int(
                start=params.get("from_time"),
                end=params.get("to_time"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )

            url = f"{self.toolset.dd_config.site_api_url}/api/v1/query"
            headers = get_headers(self.toolset.dd_config)

            query_params = {
                "query": query,
                "from": from_time,
                "to": to_time,
            }

            data = execute_datadog_http_request(
                url=url,
                headers=headers,
                timeout=self.toolset.dd_config.request_timeout,
                method="GET",
                payload_or_params=query_params,
            )

            series = data.get("series", [])

            if not series:
                return StructuredToolResult(
                    status=ToolResultStatus.NO_DATA,
                    error="The query returned no data. Please check your query syntax and time range.",
                    params=params,
                )

            response_data = {
                "status": "success",
                "query": query,
                "from_time": from_time,
                "to_time": to_time,
                "series": series,
            }

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(response_data, indent=2),
                params=params,
            )

        except DataDogRequestError as e:
            logging.exception(e, exc_info=True)

            if e.status_code == 429:
                error_msg = f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts."
            elif e.status_code == 403:
                error_msg = (
                    f"Permission denied. Ensure your Datadog Application Key has the 'metrics_read' "
                    f"and 'timeseries_query' permissions. Error: {str(e)}"
                )
            else:
                error_msg = f"Exception while querying Datadog: {str(e)}"

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
                invocation=json.dumps({"url": url, "params": query_params})
                if url and query_params
                else None,
            )

        except Exception as e:
            logging.exception(
                f"Failed to query Datadog metrics for params: {params}", exc_info=True
            )

            if isinstance(e, RetryError):
                try:
                    original_error = e.last_attempt.exception()
                    if (
                        isinstance(original_error, DataDogRequestError)
                        and original_error.status_code == 429
                    ):
                        return StructuredToolResult(
                            status=ToolResultStatus.ERROR,
                            error=f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts.",
                            params=params,
                        )
                except Exception:
                    pass

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception while querying Datadog: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        query = params.get("query", "<no query>")
        return f"Query Datadog metrics: {query}"


class QueryMetricsMetadata(BaseDatadogMetricsTool):
    def __init__(self, toolset: "DatadogMetricsToolset"):
        super().__init__(
            name="get_datadog_metric_metadata",
            description="Get metadata about one or more metrics including their type, description, unit, and other properties",
            parameters={
                "metric_names": ToolParameter(
                    description="Comma-separated list of metric names to get metadata for (e.g., 'system.cpu.user, system.mem.used')",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.dd_config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=TOOLSET_CONFIG_MISSING_ERROR,
                params=params,
            )

        try:
            metric_names_str = get_param_or_raise(params, "metric_names")

            metric_names = [
                name.strip()
                for name in metric_names_str.split(",")
                if name.strip()  # Filter out empty strings
            ]

            if not metric_names:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="metric_names cannot be empty",
                    params=params,
                )

            headers = get_headers(self.toolset.dd_config)

            results = {}
            errors = {}

            for metric_name in metric_names:
                try:
                    url = f"{self.toolset.dd_config.site_api_url}/api/v1/metrics/{metric_name}"

                    data = execute_datadog_http_request(
                        url=url,
                        headers=headers,
                        payload_or_params={},
                        timeout=self.toolset.dd_config.request_timeout,
                        method="GET",
                    )

                    results[metric_name] = data

                except DataDogRequestError as e:
                    if e.status_code == 404:
                        errors[metric_name] = "Metric not found"
                    else:
                        errors[metric_name] = f"Error {e.status_code}: {str(e)}"
                except Exception as e:
                    errors[metric_name] = f"Exception: {str(e)}"

            response_data = {
                "metrics_metadata": results,
                "errors": errors,
                "total_requested": len(metric_names),
                "successful": len(results),
                "failed": len(errors),
            }

            if not results and errors:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Failed to retrieve metadata for all metrics",
                    data=json.dumps(response_data, indent=2),
                    params=params,
                )

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(response_data, indent=2),
                params=params,
            )

        except Exception as e:
            logging.exception(
                f"Failed to query Datadog metric metadata for params: {params}",
                exc_info=True,
            )

            if isinstance(e, RetryError):
                try:
                    original_error = e.last_attempt.exception()
                    if (
                        isinstance(original_error, DataDogRequestError)
                        and original_error.status_code == 429
                    ):
                        return StructuredToolResult(
                            status=ToolResultStatus.ERROR,
                            error=f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts.",
                            params=params,
                        )
                except Exception:
                    pass

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception while querying Datadog: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        metric_names = params.get("metric_names", [])
        if isinstance(metric_names, list):
            if len(metric_names) == 1:
                return f"Get Datadog metric metadata for: {metric_names[0]}"
            elif len(metric_names) > 1:
                return f"Get Datadog metric metadata for {len(metric_names)} metrics"
        return "Get Datadog metric metadata"


class DatadogMetricsToolset(Toolset):
    dd_config: Optional[DatadogMetricsConfig] = None

    def __init__(self):
        super().__init__(
            name="datadog/metrics",
            description="Toolset for interacting with Datadog to fetch metrics and metadata",
            docs_url="https://docs.datadoghq.com/api/latest/metrics/",
            icon_url="https://imgix.datadoghq.com//img/about/presskit/DDlogo.jpg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                ListActiveMetrics(toolset=self),
                QueryMetrics(toolset=self),
                QueryMetricsMetadata(toolset=self),
            ],
            experimental=True,
            tags=[ToolsetTag.CORE],
        )
        self._reload_instructions()

    def _perform_healthcheck(self, dd_config: DatadogMetricsConfig) -> Tuple[bool, str]:
        try:
            logging.info("Performing Datadog metrics configuration healthcheck...")

            url = f"{dd_config.site_api_url}/api/v1/validate"
            headers = get_headers(dd_config)

            data = execute_datadog_http_request(
                url=url,
                headers=headers,
                payload_or_params={},
                timeout=dd_config.request_timeout,
                method="GET",
            )

            if data.get("valid", False):
                logging.info("Datadog metrics healthcheck completed successfully")
                return True, ""
            else:
                error_msg = "Datadog API key validation failed"
                logging.error(f"Datadog metrics healthcheck failed: {error_msg}")
                return False, f"Datadog metrics healthcheck failed: {error_msg}"

        except Exception as e:
            logging.exception("Failed during Datadog metrics healthcheck")
            return False, f"Healthcheck failed with exception: {str(e)}"

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return (
                False,
                TOOLSET_CONFIG_MISSING_ERROR,
            )

        try:
            dd_config = DatadogMetricsConfig(**config)
            self.dd_config = dd_config

            success, error_msg = self._perform_healthcheck(dd_config)
            return success, error_msg

        except Exception as e:
            logging.exception("Failed to set up Datadog metrics toolset")
            return (False, f"Failed to parse Datadog configuration: {str(e)}")

    def get_example_config(self) -> Dict[str, Any]:
        return {
            "dd_api_key": "your-datadog-api-key",
            "dd_app_key": "your-datadog-application-key",
            "site_api_url": "https://api.datadoghq.com",
            "default_limit": 1000,
            "request_timeout": 60,
        }

    def _reload_instructions(self):
        """Load Datadog metrics specific troubleshooting instructions."""
        template_file_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "datadog_metrics_instructions.jinja2"
            )
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
