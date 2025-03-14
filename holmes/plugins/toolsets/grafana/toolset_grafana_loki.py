from abc import ABC, abstractmethod
from typing import Dict, cast
from pydantic import BaseModel

from holmes.core.tools import Tool, ToolParameter
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset
from holmes.plugins.toolsets.grafana.common import (
    GrafanaConfig,
    format_log,
    get_param_or_raise,
    process_timestamps_to_rfc3339,
)
from holmes.plugins.toolsets.grafana.loki_api import (
    execute_loki_query,
    query_loki_logs_by_label,
)


class GrafanaLokiLabelsConfig(BaseModel):
    pod: str = "pod"
    namespace: str = "namespace"


class GrafanaLokiConfig(GrafanaConfig):
    labels: GrafanaLokiLabelsConfig = GrafanaLokiLabelsConfig()


def get_resource_label(params: Dict, config: GrafanaLokiConfig):
    resource_type = params.get("resource_type", "pod")
    label = None
    if resource_type == "pod":
        label = config.labels.pod
    else:
        return f'Error: unsupported resource type "{resource_type}". resource_type must be "pod"'
    return label


class BaseGrafanaLokiToolset(BaseGrafanaToolset):
    config_class = GrafanaLokiConfig

    def get_example_config(self):
        example_config = GrafanaLokiConfig(
            api_key="YOUR API KEY",
            url="YOUR GRAFANA URL",
            grafana_datasource_uid="<UID of the loki datasource to use>",
        )
        return example_config.model_dump()

    @property
    def grafana_config(self) -> GrafanaLokiConfig:
        return cast(GrafanaLokiConfig, self._grafana_config)


class BaseLokiLogsQuery(Tool, ABC):
    @abstractmethod
    def _build_query(self, params: Dict):
        pass

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Loki logs ({self._build_query(params)})"


class GetLokiLogs(Tool):
    def __init__(self, toolset: BaseGrafanaLokiToolset):
        super().__init__(
            name="fetch_loki_logs",
            description="Fetches Loki logs from any query",
            parameters={
                "query": ToolParameter(
                    description="The query.",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the log search period. Epoch in seconds. Logs with timestamps before this value will be excluded from the results. If negative, the number of seconds relative to the end_timestamp. Defaults to negative one hour (-3600)",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the log search period. Epoch in seconds. Logs with timestamps after this value will be excluded from the results. Defaults to NOW()",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of logs to return. Defaults to 5000. Reduce if the query times out",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps_to_rfc3339(
            params.get("start_timestamp"), params.get("end_timestamp")
        )
        query = get_param_or_raise(params, "query")
        logs = execute_loki_query(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            loki_datasource_uid=self._toolset._grafana_config.grafana_datasource_uid,
            query=query,
            start=start,
            end=end,
            limit=int(params.get("limit", 5000)),
        )
        return "\n".join([format_log(log) for log in logs])

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Loki logs ({str(params)})"


class GetLokiLogsForResource(Tool):
    def __init__(self, toolset: BaseGrafanaLokiToolset):
        super().__init__(
            name="fetch_loki_logs_for_resource",
            description="Fetches the Loki logs for a given kubernetes resource",
            parameters={
                "resource_type": ToolParameter(
                    description="The type of resource. Can only be 'pod' for now. Defaults to 'pod'.",
                    type="string",
                    required=False,
                ),
                "resource_name": ToolParameter(
                    description='Regular expression to match the resource name. This can be a regular expression. For example "<pod-name>.*" will match any pod name starting with "<pod-name>"',
                    type="string",
                    required=True,
                ),
                "namespace": ToolParameter(
                    description="The pod's namespace",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the log search period. String in RFC3339 format. If negative, the number of seconds relative to the end_timestamp. Defaults to negative one hour (-3600)",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the log search period. String in RFC3339 format. Defaults to NOW()",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of logs to return. Defaults to 5000. Reduce if the query times out",
                    type="string",
                    required=False,
                ),
                "logs_filter": ToolParameter(
                    description="Filter the logs and only return log lines matching this regular expression. Use if looking for a particular string",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps_to_rfc3339(
            params.get("start_timestamp"), params.get("end_timestamp")
        )
        label = get_resource_label(params, self._toolset.grafana_config)
        resource_name = get_param_or_raise(params, "resource_name")

        logs = query_loki_logs_by_label(
            grafana_url=self._toolset.grafana_config.url,
            api_key=self._toolset.grafana_config.api_key,
            loki_datasource_uid=self._toolset.grafana_config.grafana_datasource_uid,
            filter_regexp=params.get("logs_filter"),
            namespace=get_param_or_raise(params, "namespace"),
            namespace_search_key=self._toolset.grafana_config.labels.namespace,
            label=label,
            label_value=resource_name,
            start=start,
            end=end,
            limit=int(params.get("limit", 5000)),
        )
        return "\n".join([format_log(log) for log in logs])

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Loki logs({str(params)})"


class GrafanaLokiToolset(BaseGrafanaLokiToolset):
    def __init__(self):
        super().__init__(
            name="grafana/loki",
            description="Fetches kubernetes pods and node logs from Loki",
            icon_url="https://grafana.com/media/docs/loki/logo-grafana-loki.png",
            docs_url="https://grafana.com/oss/loki/",
            tools=[GetLokiLogsForResource(self), GetLokiLogs(self)],
        )
