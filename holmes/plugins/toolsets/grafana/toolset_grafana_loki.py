from typing import Dict

import yaml

from holmes.core.tools import Tool, ToolParameter
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset
from holmes.plugins.toolsets.grafana.common import (
    GrafanaConfig,
    get_datasource_id,
    get_param_or_raise,
    process_timestamps,
)
from holmes.plugins.toolsets.grafana.grafana_api import list_grafana_datasources
from holmes.plugins.toolsets.grafana.loki_api import (
    execute_loki_query,
    query_loki_logs_by_node,
    query_loki_logs_by_pod,
)


class GrafanaLokiConfig(GrafanaConfig):
    pod_name_search_key: str = "pod"
    namespace_search_key: str = "namespace"
    node_name_search_key: str = "node"


class ListLokiDatasources(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="list_loki_datasources",
            description="Fetches the Loki data sources in Grafana",
            parameters={},
        )
        self._toolset: BaseGrafanaToolset = toolset

    def invoke(self, params: Dict) -> str:
        datasources = list_grafana_datasources(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            source_name="loki",
        )
        return yaml.dump(datasources)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Fetched Grafana Loki datasources"


class GetLokiLogsByNode(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="fetch_loki_logs_by_node",
            description="""Fetches the Loki logs for a given node""",
            parameters={
                "loki_datasource_id": ToolParameter(
                    description="The id of the loki datasource to use. First call the tool list_loki_datasources, then pass the numerical id field here",
                    type="string",
                    required=True,
                ),
                "node_name": ToolParameter(
                    description="The name of the kubernetes node to fetch",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the log search period. Epoch in seconds. Logs with timestamps before this value will be excluded from the results. If negative, the number of seconds relative to the end_timestamp.",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the log search period. Epoch in seconds. Logs with timestamps after this value will be excluded from the results. Defaults to NOW()",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of logs to return.",
                    type="string",
                    required=True,
                ),
            },
        )
        self._toolset: BaseGrafanaToolset = toolset

    def invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps(
            params.get("start_timestamp"), params.get("end_timestamp")
        )
        logs = query_loki_logs_by_node(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            loki_datasource_id=get_datasource_id(params, "loki_datasource_id"),
            node_name=get_param_or_raise(params, "node_name"),
            node_name_search_key=self._toolset._grafana_config.node_name_search_key,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit")),
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Loki logs ({str(params)})"


class GetLokiLogsByLabel(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="fetch_loki_logs_by_label",
            description="""Fetches Loki logs matching a <label>=<value> pair""",
            parameters={
                "loki_datasource_id": ToolParameter(
                    description="The id of the loki datasource to use. Call the tool list_loki_datasources",
                    type="string",
                    required=True,
                ),
                "label": ToolParameter(
                    description="The label for the query.",
                    type="string",
                    required=True,
                ),
                "value": ToolParameter(
                    description="The value of the label.",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the log search period. Epoch in seconds. Logs with timestamps before this value will be excluded from the results. If negative, the number of seconds relative to the end_timestamp.",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the log search period. Epoch in seconds. Logs with timestamps after this value will be excluded from the results. Defaults to NOW()",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of logs to return.",
                    type="string",
                    required=True,
                ),
            },
        )
        self._toolset = toolset

    def invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps(
            params.get("start_timestamp"), params.get("end_timestamp")
        )
        label = get_param_or_raise(params, "label")
        value = get_param_or_raise(params, "value")
        query = f'{{{label}="{value}"}}'
        logs = execute_loki_query(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            loki_datasource_id=get_datasource_id(params, "loki_datasource_id"),
            query=query,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit")),
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Loki logs ({str(params)})"


class GetLokiLogsByPod(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="fetch_loki_logs_by_pod",
            description="Fetches the Loki logs for a given pod",
            parameters={
                "loki_datasource_id": ToolParameter(
                    description="The id of the loki datasource to use. Call the tool list_loki_datasources",
                    type="string",
                    required=True,
                ),
                "pod_regex": ToolParameter(
                    description="Regular expression to match pod names",
                    type="string",
                    required=True,
                ),
                "namespace": ToolParameter(
                    description="The pod's namespace",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the log search period. Epoch in seconds. Logs with timestamps before this value will be excluded from the results. If negative, the number of seconds relative to the end_timestamp.",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the log search period. Epoch in seconds. Logs with timestamps after this value will be excluded from the results. Defaults to NOW()",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of logs to return.",
                    type="string",
                    required=True,
                ),
            },
        )
        self._toolset = toolset

    def invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps(
            params.get("start_timestamp"), params.get("end_timestamp")
        )
        logs = query_loki_logs_by_pod(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            loki_datasource_id=get_datasource_id(params, "loki_datasource_id"),
            pod_regex=get_param_or_raise(params, "pod_regex"),
            namespace=get_param_or_raise(params, "namespace"),
            namespace_search_key=self._toolset._grafana_config.namespace_search_key,
            pod_name_search_key=self._toolset._grafana_config.pod_name_search_key,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit")),
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Loki logs({str(params)})"


class GrafanaLokiToolset(BaseGrafanaToolset):
    config_class = GrafanaLokiConfig

    def __init__(self):
        super().__init__(
            name="grafana/loki",
            description="Fetches kubernetes pods and node logs from Loki",
            icon_url="https://grafana.com/media/docs/loki/logo-grafana-loki.png",
            doc_url="https://grafana.com/oss/loki/",
            tools=[
                ListLokiDatasources(self),
                GetLokiLogsByNode(self),
                GetLokiLogsByPod(self),
                GetLokiLogsByLabel(self),
            ],
        )

    def get_example_config(self):
        example_config = GrafanaLokiConfig(
            api_key="YOUR API KEY", url="YOUR GRAFANA URL"
        )
        return example_config.model_dump()
