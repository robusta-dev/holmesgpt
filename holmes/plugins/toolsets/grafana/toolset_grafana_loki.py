import os
from typing import Any, cast, Set
from pydantic import BaseModel

from holmes.core.tools import CallablePrerequisite
from holmes.plugins.toolsets.grafana.common import (
    GrafanaConfig,
    format_log,
    get_base_url,
)
from holmes.plugins.toolsets.grafana.grafana_api import grafana_health_check
from holmes.plugins.toolsets.logging_utils.logging_api import (
    BasePodLoggingToolset,
    FetchPodLogsParams,
    LoggingCapability,
    PodLoggingTool,
    DEFAULT_TIME_SPAN_SECONDS,
    DEFAULT_LOG_LIMIT,
)
from holmes.plugins.toolsets.utils import (
    process_timestamps_to_rfc3339,
)

from holmes.plugins.toolsets.grafana.loki_api import (
    query_loki_logs_by_label,
)
from holmes.core.tools import (
    StructuredToolResult,
    StructuredToolResultStatus,
    ToolParameter,
)


class GrafanaLokiLabelsConfig(BaseModel):
    pod: str = "pod"
    namespace: str = "namespace"


class GrafanaLokiConfig(GrafanaConfig):
    labels: GrafanaLokiLabelsConfig = GrafanaLokiLabelsConfig()


class LokiPodLoggingTool(PodLoggingTool):
    """Custom pod logging tool for Loki with wildcard support"""

    def _get_tool_parameters(self, toolset: BasePodLoggingToolset) -> dict:
        """Override to add wildcard support to pod_name parameter"""
        # Get base parameters from parent
        params = super()._get_tool_parameters(toolset)

        # Override pod_name description to indicate wildcard support
        params["pod_name"] = ToolParameter(
            description="The kubernetes pod name. Use '*' to fetch logs from all pods in the namespace, or use wildcards like 'payment-*' to match multiple pods",
            type="string",
            required=True,
        )

        return params


class GrafanaLokiToolset(BasePodLoggingToolset):
    @property
    def supported_capabilities(self) -> Set[LoggingCapability]:
        """Loki only supports substring matching, not regex or exclude filters"""
        return set()  # No regex support, no exclude filter

    def __init__(self):
        super().__init__(
            name="grafana/loki",
            description="Fetches kubernetes pods logs from Loki",
            icon_url="https://grafana.com/media/docs/loki/logo-grafana-loki.png",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/grafanaloki/",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[],  # Initialize with empty tools first
        )
        # Now that parent is initialized and self.name exists, create the tool
        # Use our custom LokiPodLoggingTool with wildcard support
        self.tools = [LokiPodLoggingTool(self)]
        self._reload_instructions()

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

    def logger_name(self) -> str:
        return "Loki"

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        (start, end) = process_timestamps_to_rfc3339(
            start_timestamp=params.start_time,
            end_timestamp=params.end_time,
            default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
        )

        base_url = get_base_url(self.grafana_config)
        logs = query_loki_logs_by_label(
            base_url=base_url,
            api_key=self.grafana_config.api_key,
            headers=self.grafana_config.headers,
            filter=params.filter,
            namespace=params.namespace,
            namespace_search_key=self.grafana_config.labels.namespace,
            label=self.grafana_config.labels.pod,
            label_value=params.pod_name,
            start=start,
            end=end,
            limit=params.limit or DEFAULT_LOG_LIMIT,
        )
        if logs:
            logs.sort(key=lambda x: x["timestamp"])
            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data="\n".join([format_log(log) for log in logs]),
                params=params.model_dump(),
            )
        else:
            return StructuredToolResult(
                status=StructuredToolResultStatus.NO_DATA,
                params=params.model_dump(),
            )

    def _reload_instructions(self):
        """Load Loki specific instructions."""
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "loki_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
