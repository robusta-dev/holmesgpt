from typing import Dict
from urllib.parse import urlencode
from holmes.core.tools import Tool, ToolParameter
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset


class ListGrafanaDashboards(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="list_grafana_dashboards",
            description="Lists all available Grafana dashboards",
            parameters={},
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        return f"{self._toolset._grafana_config.url}/dashboards"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Generate a Grafana dashboards list URL"


class BuildGrafanaDashboardURL(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="build_grafana_dashboard_url",
            description="Builds a Grafana dashboard URL with parameters",
            parameters={
                "dashboard_uid": ToolParameter(
                    description="The UID of the Grafana dashboard",
                    type="string",
                    required=True,
                ),
                "pod_name": ToolParameter(
                    description="The pod name to filter logs",
                    type="string",
                    required=False,
                ),
                "namespace": ToolParameter(
                    description="The namespace of the resource",
                    type="string",
                    required=False,
                ),
                "cluster_name": ToolParameter(
                    description="The cluster name to scope the dashboard",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        dashboard_uid = params.get("dashboard_uid")
        query_params = {
            key: value
            for key, value in params.items()
            if key != "dashboard_uid" and value
        }
        url = (
            self._toolset._grafana_config.external_url
            or self._toolset._grafana_config.url
        )
        dashboard_url = f"{url}/d/{dashboard_uid}?{urlencode(query_params)}"
        return dashboard_url

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Generate a Grafana dashboard URL for UID={params.get('dashboard_uid')} with filters"


class GrafanaToolset(BaseGrafanaToolset):
    def __init__(self):
        super().__init__(
            name="grafana",
            description="Provides tools for interacting with Grafana dashboards",
            icon_url="https://w7.pngwing.com/pngs/434/923/png-transparent-grafana-hd-logo-thumbnail.png",
            docs_url="",
            tools=[
                ListGrafanaDashboards(self),
                BuildGrafanaDashboardURL(self),
            ],
        )
