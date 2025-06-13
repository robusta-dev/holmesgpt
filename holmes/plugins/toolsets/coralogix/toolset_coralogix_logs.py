from typing import Any, Optional, Tuple

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    ToolResultStatus,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import (
    TOOLSET_CONFIG_MISSING_ERROR,
)
from holmes.plugins.toolsets.coralogix.api import (
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
from holmes.plugins.toolsets.logging_utils.logging_api import (
    BasePodLoggingToolset,
    FetchPodLogsParams,
    PodLoggingTool,
)


class CoralogixLogsToolset(BasePodLoggingToolset):
    def __init__(self):
        super().__init__(
            name="coralogix/logs",
            description="Toolset for interacting with Coralogix to fetch logs",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/coralogix_logs.html",
            icon_url="https://avatars.githubusercontent.com/u/35295744?s=200&v=4",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                PodLoggingTool(self),
            ],
            tags=[ToolsetTag.CORE],
        )

    def get_example_config(self):
        example_config = CoralogixConfig(
            api_key="<cxuw_...>", team_hostname="my-team", domain="eu2.coralogix.com"
        )
        return example_config.model_dump()

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR

        self.config = CoralogixConfig(**config)

        if not self.config.api_key:
            return False, "Missing configuration field 'api_key'"

        return health_check(domain=self.config.domain, api_key=self.config.api_key)

    @property
    def coralogix_config(self) -> Optional[CoralogixConfig]:
        return self.config

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        if not self.coralogix_config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"The {self.name} toolset is not configured",
                params=params.model_dump(),
            )

        logs_data = query_logs_for_all_tiers(
            config=self.coralogix_config, params=params
        )
        (start, end) = get_start_end(params=params)
        query_string = build_query_string(config=self.coralogix_config, params=params)

        url = build_coralogix_link_to_logs(
            config=self.coralogix_config,
            lucene_query=query_string,
            start=start,
            end=end,
        )

        data: str
        if logs_data.error:
            data = logs_data.error
        else:
            logs = stringify_flattened_logs(logs_data.logs)
            # Remove link and query from results once the UI and slackbot properly handle the URL from the StructuredToolResult
            data = f"link: {url}\nquery: {query_string}\n{logs}"

        return StructuredToolResult(
            status=(
                ToolResultStatus.ERROR if logs_data.error else ToolResultStatus.SUCCESS
            ),
            error=logs_data.error,
            data=data,
            url=url,
            invocation=query_string,
            params=params.model_dump(),
        )
