
from typing import Any, Dict
import yaml

from holmes.core.tools import EnvironmentVariablePrerequisite, Tool, ToolParameter, Toolset
from holmes.plugins.toolsets.grafana.loki_api import GRAFANA_API_KEY_ENV_NAME, GRAFANA_URL_ENV_NAME, list_loki_datasources, query_loki_logs_by_node, query_loki_logs_by_pod

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

class GetLokiLogsByNode(Tool):

    def __init__(self):
        super().__init__(
            name = "fetch_loki_logs_by_node",
            description = """Fetches the Loki logs for a given node""",
            parameters = {
                "loki_datasource_uid": ToolParameter(
                    description="The uid of the loki datasource to use. Call the tool list_loki_datasources",
                    type="string",
                    required=True,
                ),
                "node_name": ToolParameter(
                    description="The name of the kubernetes node to fetch",
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

    def invoke(self, params: Dict) -> str:

        print(params)
        datasources= query_loki_logs_by_node(
            loki_datasource_uid=get_param_or_raise(params, "loki_datasource_uid"),
            node_name=get_param_or_raise(params, "node_name"),
            time_range_minutes=int(get_param_or_raise(params, "time_range_minutes")),
            limit=int(get_param_or_raise(params, "limit"))
        )
        return yaml.dump(datasources)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched Loki logs ({str(params)})"


class GetLokiLogsByPod(Tool):

    def __init__(self):
        super().__init__(
            name = "fetch_loki_logs_by_pod",
            description = "Fetches the Loki logs for a given pod",
            parameters = {
                "loki_datasource_uid": ToolParameter(
                    description="The uid of the loki datasource to use. Call the tool list_loki_datasources",
                    type="string",
                    required=True,
                ),
                "pod_regex": ToolParameter(
                    description="Regular expression to match pod names",
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

    def invoke(self, params: Dict) -> str:

        print(params)
        datasources= query_loki_logs_by_pod(
            loki_datasource_uid=get_param_or_raise(params, "loki_datasource_uid"),
            pod_regex=get_param_or_raise(params, "pod_regex"),
            namespace=get_param_or_raise(params, "namespace"),
            time_range_minutes=int(get_param_or_raise(params, "time_range_minutes")),
            limit=int(get_param_or_raise(params, "limit"))
        )
        return yaml.dump(datasources)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched Loki logs({str(params)})"

class GrafanaLokiToolset(Toolset):
    def __init__(self):
        super().__init__(
            name = "grafana_loki",
            prerequisites = [
                EnvironmentVariablePrerequisite(GRAFANA_API_KEY_ENV_NAME),
                EnvironmentVariablePrerequisite(GRAFANA_URL_ENV_NAME)
            ],
            tools = [
                ListLokiDatasources(),
                GetLokiLogsByNode(),
                GetLokiLogsByPod(),
            ],
        )
        self.check_prerequisites()
