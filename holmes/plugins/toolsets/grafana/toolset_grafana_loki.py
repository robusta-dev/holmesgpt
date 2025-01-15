
from typing import Dict
import yaml
from holmes.core.tools import StaticPrerequisite, Tool, ToolParameter, Toolset, ToolsetTag
from holmes.plugins.toolsets.grafana.loki_api import list_grafana_datasources, query_loki_logs_by_node, query_loki_logs_by_pod, execute_loki_query
from holmes.plugins.toolsets.grafana.common import GrafanaConfig, get_grafana_toolset_prerequisite
from holmes.plugins.toolsets.grafana.common import get_datasource_id, get_param_or_raise, process_timestamps


class ListLokiDatasources(Tool):

    def __init__(self, config:GrafanaConfig):
        super().__init__(
            name = "list_loki_datasources",
            description = "Fetches the Loki data sources in Grafana",
            parameters = {},
        )
        self._config = config

    def invoke(self, params: Dict) -> str:
        datasources= list_grafana_datasources(grafana_url=self._config.url, api_key=self._config.api_key, source_name="loki")
        return yaml.dump(datasources)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return "Fetched Grafana Loki datasources"


class GetLokiLogsByNode(Tool):

    def __init__(self, config: GrafanaConfig):
        super().__init__(
            name = "fetch_loki_logs_by_node",
            description = """Fetches the Loki logs for a given node""",
            parameters = {
                "loki_datasource_id": ToolParameter(
                    description="The id of the loki datasource to use. Call the tool list_loki_datasources",
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
                )
            },
        )
        self._config = config

    def invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps(params.get("start_timestamp"), params.get("end_timestamp"))
        logs = query_loki_logs_by_node(
            grafana_url=self._config.url,
            api_key=self._config.api_key,
            loki_datasource_id=get_datasource_id(params, "loki_datasource_id"),
            node_name=get_param_or_raise(params, "node_name"),
            node_name_search_key=self._config.loki.node_name_search_key,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit"))
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched Loki logs ({str(params)})"

class GetLokiLogsByLabel(Tool):
    def __init__(self, config: GrafanaConfig):
        super().__init__(
            name = "fetch_loki_logs_by_label",
            description = """Fetches the Loki logs for a label and value from a Tempo trace""",
            parameters = {
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
                )
            },
        )
        self._config = config

    def invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps(params.get("start_timestamp"), params.get("end_timestamp"))
        label=get_param_or_raise(params, "label")
        value=get_param_or_raise(params, "value")
        query = f'{{{label}="{value}"}}'
        logs = execute_loki_query(
            grafana_url=self._config.url,
            api_key=self._config.api_key,
            loki_datasource_id=get_datasource_id(params, "loki_datasource_id"),
            query=query,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit"))
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched Loki logs ({str(params)})"

class GetLokiLogsByPod(Tool):

    def __init__(self, config: GrafanaConfig):
        super().__init__(
            name = "fetch_loki_logs_by_pod",
            description = "Fetches the Loki logs for a given pod",
            parameters = {
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
                )

            },
        )
        self._config = config

    def invoke(self, params: Dict) -> str:
        (start, end) = process_timestamps(params.get("start_timestamp"), params.get("end_timestamp"))
        logs = query_loki_logs_by_pod(
            grafana_url=self._config.url,
            api_key=self._config.api_key,
            loki_datasource_id=get_datasource_id(params, "loki_datasource_id"),
            pod_regex=get_param_or_raise(params, "pod_regex"),
            namespace=get_param_or_raise(params, "namespace"),
            namespace_search_key=self._config.loki.namespace_search_key,
            pod_name_search_key=self._config.loki.pod_name_search_key,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit"))
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched Loki logs({str(params)})"

class GrafanaLokiToolset(Toolset):
    def __init__(self, config: GrafanaConfig):
        super().__init__(
            name = "grafana_loki",
            description = "Fetchs kubernetes pods and node logs from Loki",
            icon_url = "https://grafana.com/media/docs/loki/logo-grafana-loki.png",
            prerequisites = [
                get_grafana_toolset_prerequisite(config),
                StaticPrerequisite(enabled=config.loki.enabled, disabled_reason="Loki toolset explicitly disabled by config")
            ],
            tools = [
                ListLokiDatasources(config),
                GetLokiLogsByNode(config),
                GetLokiLogsByPod(config),
                GetLokiLogsByLabel(config)
            ],
            tags = [ToolsetTag.CORE, ]
        )
        self.check_prerequisites()
