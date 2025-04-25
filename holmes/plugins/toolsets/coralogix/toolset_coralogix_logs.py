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
    get_start_end,
    health_check,
    query_logs_for_all_tiers,
)
from holmes.plugins.toolsets.coralogix.utils import (
    CoralogixConfig,
    build_coralogix_link_to_logs,
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
            name="fetch_coralogix_logs_for_resource",
            description="Retrieve logs using coralogix",
            parameters={
                "resource_type": ToolParameter(
                    description="The type of resource. Can be one of pod, application or subsystem. Defaults to pod.",
                    type="string",
                    required=False,
                ),
                "resource_name": ToolParameter(
                    description='Regular expression to match the resource name. This can be a regular expression. For example "<pod-name>.*" will match any pod name starting with "<pod-name>"',
                    type="string",
                    required=True,
                ),
                "namespace_name": ToolParameter(
                    description="The Kubernetes namespace to filter logs",
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
        (start, end) = get_start_end(config=self.toolset.config, params=params)
        query_string = build_query_string(config=self.toolset.config, params=params)

        url = build_coralogix_link_to_logs(
            config=self.toolset.config, lucene_query=query_string, start=start, end=end
        )

        data: str
        if logs_data.error:
            data = logs_data.error
        else:
            logs = stringify_flattened_logs(logs_data.logs)
            # Remove link and query from results once the UI and slackbot properly handle the URL from the StructuredToolResult
            data = f"link: {url}\nquery: {query_string}\n{logs}"

        return StructuredToolResult(
            status=ToolResultStatus.ERROR
            if logs_data.error
            else ToolResultStatus.SUCCESS,
            error=logs_data.error,
            data=data,
            url=url,
            invocation=query_string,
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
