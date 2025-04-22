import logging
from typing import Any, Optional, Tuple
from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    ToolResultStatus,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)

from holmes.plugins.toolsets.coralogix.api import execute_query, health_check
from holmes.plugins.toolsets.coralogix.utils import (
    CoralogixConfig,
    build_coralogix_link_to_logs,
    format_logs,
)
from holmes.plugins.toolsets.utils import (
    STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
    TOOLSET_CONFIG_MISSING_ERROR,
    process_timestamps_to_rfc3339,
    standard_start_datetime_tool_param_description,
)

DEFAULT_LOG_COUNT = 1000
DEFAULT_TIME_SPAN_SECONDS = 86400


class BaseCoralogixToolset(Toolset):
    config: Optional[CoralogixConfig] = None

    def get_example_config(self):
        example_config = CoralogixConfig(
            api_key="<cxuw_...>", team_hostname="my-team", domain="eu2.coralogix.com"
        )
        return example_config.model_dump()


class BaseCoralogixTool(Tool):
    toolset: BaseCoralogixToolset


class FetchLogs(BaseCoralogixTool):
    def __init__(self, toolset: BaseCoralogixToolset):
        super().__init__(
            name="coralogix_fetch_logs",
            description="Retrieve logs from Coralogix",
            parameters={
                "app_name": ToolParameter(
                    description="The application name to filter logs",
                    type="string",
                    required=False,
                ),
                "namespace_name": ToolParameter(
                    description="The Kubernetes namespace to filter logs",
                    type="string",
                    required=False,
                ),
                "pod_name": ToolParameter(
                    description="The specific pod name to filter logs",
                    type="string",
                    required=False,
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
                "log_count": ToolParameter(
                    description=f"Maximum number of logs to retrieve (default: {DEFAULT_LOG_COUNT})",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _get_query_string(self, config: CoralogixConfig, params: Any) -> str:
        app_name = params.get("app_name", None)
        namespace_name = params.get("namespace_name", None)
        pod_name = params.get("pod_name", None)
        log_count = params.get("log_count", DEFAULT_LOG_COUNT)

        query_filters = []
        if namespace_name:
            query_filters.append(f"{config.labels.namespace}:{namespace_name}")
        if pod_name:
            query_filters.append(f"{config.labels.pod}:{pod_name}")
        if app_name:
            query_filters.append(f"{config.labels.app}:{app_name}")

        query_string = " AND ".join(query_filters)
        query_string = f"source logs | lucene '{query_string}' | limit {log_count}"
        return query_string

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="The coralogix/logs toolset is not configured",
                data=None,
                params=params,
            )

        (start, end) = process_timestamps_to_rfc3339(
            start_timestamp=params.get("start"),
            end_timestamp=params.get("end"),
            default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
        )
        query_string = self._get_query_string(self.toolset.config, params)
        query = {
            "query": query_string,
            "metadata": {
                "syntax": "QUERY_SYNTAX_DATAPRIME",
                "startDate": start,
                "endDate": end,
            },
        }
        response = execute_query(
            domain=self.toolset.config.domain,
            api_key=self.toolset.config.api_key,
            query=query,
        )

        # Do not print tags if they are repeating the query
        namespace_name = params.get("namespace_name", None)
        pod_name = params.get("pod_name", None)
        add_namespace_tag = not namespace_name and not pod_name
        add_pod_tag = not pod_name

        try:
            logs = format_logs(
                raw_logs=response.text.strip(),
                add_namespace_tag=add_namespace_tag,
                add_pod_tag=add_pod_tag,
            )
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS if logs else ToolResultStatus.ERROR,
                error=None if logs else "The query returned no logs",
                data=logs,
                invocation=query_string,
                url=build_coralogix_link_to_logs(
                    config=self.toolset.config,
                    lucene_query=query_string,
                    start=start,
                    end=end,
                ),
                params=params,
            )
        except Exception:
            logging.error(f"Failed to decode JSON response: {response} {response.text}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Failed to decode JSON response. Raw response set to data field.",
                data=response.text,
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        if not self.toolset.config:
            return "The coralogix/logs toolset is not configured"
        query_string = self._get_query_string(self.toolset.config, params)
        return f"fetching coralogix logs. query={query_string}"


class CoralogixLogsToolset(BaseCoralogixToolset):
    def __init__(self):
        super().__init__(
            name="coralogix/logs",
            description="Toolset for interacting with Coralogix to fetch logs",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/coralogix_logs.html",
            icon_url="https://www.coralogix.com/wp-content/uploads/2021/02/coralogix-logo-dark.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                FetchLogs(self),
            ],
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR
        self.config = CoralogixConfig(**config)
        if self.config.api_key:
            return health_check(domain=self.config.domain, api_key=self.config.api_key)
        else:
            return False, "Missing configuration field 'api_key'"
