from typing import Any, cast, Dict
from pydantic import BaseModel
import os
import json
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolInvokeContext,
    ToolParameter,
    Toolset,
)
from holmes.plugins.toolsets.consts import (
    STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
)

from holmes.plugins.toolsets.grafana.common import GrafanaConfig, get_base_url
from holmes.plugins.toolsets.grafana.grafana_api import grafana_health_check
from holmes.plugins.toolsets.utils import (
    process_timestamps_to_rfc3339,
    standard_start_datetime_tool_param_description,
)
from holmes.plugins.toolsets.logging_utils.logging_api import (
    DEFAULT_TIME_SPAN_SECONDS,
    DEFAULT_LOG_LIMIT,
)
from holmes.plugins.toolsets.grafana.loki_api import (
    execute_loki_query,
)

from holmes.plugins.toolsets.utils import toolset_name_for_one_liner
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus


class GrafanaLokiLabelsConfig(BaseModel):
    pod: str = "pod"
    namespace: str = "namespace"


class GrafanaLokiConfig(GrafanaConfig):
    labels: GrafanaLokiLabelsConfig = GrafanaLokiLabelsConfig()


class GrafanaLokiToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="grafana/loki",
            description="Runs loki log quereis using Grafana Loki or Loki directly.",
            icon_url="https://grafana.com/media/docs/loki/logo-grafana-loki.png",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/grafanaloki/",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[],
        )

        self.tools = [LokiQuery(toolset=self)]
        instructions_filepath = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{instructions_filepath}")

    def prerequisites_callable(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not config:
            return False, "Missing Loki configuration. Check your config."

        self.config = GrafanaLokiConfig(**config)
        return grafana_health_check(self.config)

    def get_example_config(self):
        example_config = GrafanaLokiConfig(
            api_key="YOUR API KEY",
            url="YOUR GRAFANA URL",
            grafana_datasource_uid="<UID of the loki datasource to use>",
        )
        return example_config.model_dump()

    @property
    def grafana_config(self) -> GrafanaLokiConfig:
        return cast(GrafanaLokiConfig, self.config)


class LokiQuery(Tool):
    toolset: GrafanaLokiToolset
    name: str = "grafana_loki_query"
    description: str = "Run a query against Grafana Loki using LogQL query language."
    parameters: Dict[str, ToolParameter] = {
        "query": ToolParameter(
            description="LogQL query string.",
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
        "limit": ToolParameter(
            description="Maximum number of entries to return (default: 100)",
            type="integer",
            required=False,
        ),
    }

    def get_parameterized_one_liner(self, params) -> str:
        return f"{toolset_name_for_one_liner(self.toolset.name)}: loki query {params}"

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        (start, end) = process_timestamps_to_rfc3339(
            start_timestamp=params.get("start"),
            end_timestamp=params.get("end"),
            default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
        )

        config = self.toolset.grafana_config
        try:
            data = execute_loki_query(
                base_url=get_base_url(config),
                api_key=config.api_key,
                headers=config.headers,
                query=params.get("query"),
                start=start,
                end=end,
                limit=params.get("limit") or DEFAULT_LOG_LIMIT,
            )
            if data:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.SUCCESS,
                    data=json.dumps(data),
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.NO_DATA,
                    params=params,
                )
        except Exception as e:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                params=params,
                error=str(e),
                url=f"{get_base_url(config)}/loki/api/v1/query_range",
            )
