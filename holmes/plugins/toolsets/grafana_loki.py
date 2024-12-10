
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel
import yaml
import time
from holmes.core.tools import EnvironmentVariablePrerequisite, Tool, ToolParameter, Toolset
from holmes.plugins.toolsets.grafana.loki_api import GRAFANA_API_KEY_ENV_NAME, GRAFANA_URL_ENV_NAME, list_loki_datasources, query_loki_logs_by_node, query_loki_logs_by_pod

class GrafanaLokiConfig(BaseModel):
    pod_name_search_key: str = "pod"
    namespace_search_key: str = "namespace"
    node_name_search_key: str = "node"

class GrafanaConfig(BaseModel):
    loki: GrafanaLokiConfig = GrafanaLokiConfig()

def get_param_or_raise(dict:Dict, param:str) -> Any:
    value = dict.get(param)
    if not value:
        raise Exception(f'Missing param "{param}"')
    return value

class ListLokiDatasources(Tool):

    def __init__(self):
        super().__init__(
            name = "list_loki_datasources",
            description = "Fetches the Loki data sources in Grafana",
            parameters = {},
        )

    def invoke(self, params: Dict) -> str:
        datasources= list_loki_datasources()
        return yaml.dump(datasources)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return "Fetched Grafana Loki datasources"

ONE_HOUR = 3600

def process_timestamps(start_timestamp: Optional[Union[int, str]], end_timestamp: Optional[Union[int, str]]):
    if start_timestamp and isinstance(start_timestamp, str):
        start_timestamp = int(start_timestamp)
    if end_timestamp and isinstance(end_timestamp, str):
        end_timestamp = int(end_timestamp)

    if not end_timestamp:
        end_timestamp = int(time.time())
    if not start_timestamp:
        start_timestamp = end_timestamp - ONE_HOUR
    if start_timestamp < 0:
        start_timestamp = end_timestamp + start_timestamp
    return (start_timestamp, end_timestamp)

class GetLokiLogsByNode(Tool):

    def __init__(self, config: GrafanaLokiConfig = GrafanaLokiConfig()):
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
            loki_datasource_id=get_param_or_raise(params, "loki_datasource_id"),
            node_name=get_param_or_raise(params, "node_name"),
            node_name_search_key=self._config.node_name_search_key,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit"))
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched Loki logs ({str(params)})"


class GetLokiLogsByPod(Tool):

    def __init__(self, config: GrafanaLokiConfig = GrafanaLokiConfig()):
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
                "time_range_minutes": ToolParameter(
                    description="Time range to query in minutes",
                    type="string",
                    required=True,
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
            loki_datasource_id=get_param_or_raise(params, "loki_datasource_id"),
            pod_regex=get_param_or_raise(params, "pod_regex"),
            namespace=get_param_or_raise(params, "namespace"),
            namespace_search_key=self._config.namespace_search_key,
            pod_name_search_key=self._config.pod_name_search_key,
            start=start,
            end=end,
            limit=int(get_param_or_raise(params, "limit"))
        )
        return yaml.dump(logs)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched Loki logs({str(params)})"

class GrafanaLokiToolset(Toolset):
    def __init__(self, config: GrafanaLokiConfig):
        super().__init__(
            name = "grafana_loki",
            prerequisites = [
                EnvironmentVariablePrerequisite(GRAFANA_API_KEY_ENV_NAME),
                EnvironmentVariablePrerequisite(GRAFANA_URL_ENV_NAME)
            ],
            tools = [
                ListLokiDatasources(),
                GetLokiLogsByNode(config),
                GetLokiLogsByPod(config),
            ],
        )
        self.check_prerequisites()
