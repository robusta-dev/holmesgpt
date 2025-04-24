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

from holmes.plugins.toolsets.coralogix.api import (
    DEFAULT_LOG_COUNT,
    DEFAULT_TIME_SPAN_SECONDS,
    build_query_string,
    health_check,
    query_logs_for_all_tiers,
)
from holmes.plugins.toolsets.coralogix.utils import (
    CoralogixConfig,
    stringify_flattened_logs,
)
from holmes.plugins.toolsets.utils import (
    STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
    TOOLSET_CONFIG_MISSING_ERROR,
    standard_start_datetime_tool_param_description,
)


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
            name="fetch_logs",
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

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="The coralogix/logs toolset is not configured",
                data=None,
                params=params,
            )

        logs_data = query_logs_for_all_tiers(config=self.toolset.config, params=params)

        return StructuredToolResult(
            status=ToolResultStatus.ERROR
            if logs_data.error
            else ToolResultStatus.SUCCESS,
            error=logs_data.error,
            data=None if logs_data.error else stringify_flattened_logs(logs_data.logs),
            params=params,
        )

    def get_parameterized_one_liner(self, params) -> str:
        if not self.toolset.config:
            return "The coralogix/logs toolset is not configured"
        query_string = build_query_string(self.toolset.config, params)
        return f"fetching coralogix logs. query={query_string}"


class CoralogixLogsToolset(BaseCoralogixToolset):
    def __init__(self):
        super().__init__(
            name="coralogix/logs",
            description="Toolset for interacting with Coralogix to fetch logs",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/coralogix_logs.html",
            icon_url="https://avatars.githubusercontent.com/u/35295744?s=200&v=4",
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
