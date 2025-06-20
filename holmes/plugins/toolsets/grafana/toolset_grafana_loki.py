from typing import Any, cast
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
    PodLoggingTool,
)
from holmes.plugins.toolsets.utils import (
    process_timestamps_to_rfc3339,
)

from holmes.plugins.toolsets.grafana.loki_api import (
    query_loki_logs_by_label,
)
from holmes.core.tools import StructuredToolResult, ToolResultStatus

DEFAULT_TIME_SPAN_SECONDS = 3600


class GrafanaLokiLabelsConfig(BaseModel):
    pod: str = "pod"
    namespace: str = "namespace"


class GrafanaLokiConfig(GrafanaConfig):
    labels: GrafanaLokiLabelsConfig = GrafanaLokiLabelsConfig()


class GrafanaLokiToolset(BasePodLoggingToolset):
    def __init__(self):
        super().__init__(
            name="grafana/loki",
            description="Fetches kubernetes pods logs from Loki",
            icon_url="https://grafana.com/media/docs/loki/logo-grafana-loki.png",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanaloki.html",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                PodLoggingTool(self),
            ],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not config:
            return False, "Missing Grafana Loki configuration. Check your config."

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
            limit=params.limit or 2000,
        )
        if logs:
            logs.sort(key=lambda x: x["timestamp"])
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data="\n".join([format_log(log) for log in logs]),
                params=params.model_dump(),
            )
        else:
            return StructuredToolResult(
                status=ToolResultStatus.NO_DATA,
                params=params.model_dump(),
            )
