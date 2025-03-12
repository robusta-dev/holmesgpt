from typing import Dict, List
from urllib.parse import urlencode, parse_qsl, urljoin
from holmes.core.tools import Tool, ToolParameter
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset
import requests


class ListGrafanaDashboards(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="list_grafana_dashboards",
            description="Lists all available Grafana dashboards",
            parameters={},
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        url = urljoin(
            self._toolset._grafana_config.url, "/api/search?query=&type=dash-db"
        )
        headers = {"Authorization": f"Bearer {self._toolset._grafana_config.api_key}"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            dashboards = response.json()

            formatted_dashboards: List[str] = []
            for dash in dashboards:
                dashboard_url = urljoin(
                    self._toolset._grafana_config.url,
                    f"/d/{dash['uid']}/{dash['uri'].split('/')[-1]}",
                )
                formatted_dashboards.append(
                    f"Title: {dash['title']}\n"
                    f"URL: {dashboard_url}?var-cluster=CLUSTER_NAME&var-namespace=NAMESPACE&var-pod=POD_NAME&var-datasource=prometheus\n"
                    f"Params: cluster=CLUSTER_NAME, namespace=NAMESPACE, pod=POD_NAME, datasource=prometheus\n"
                )

            return "\n".join(formatted_dashboards) or "No dashboards found."
        except requests.RequestException as e:
            return f"Error fetching dashboards: {str(e)}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Fetches and lists all available Grafana dashboards with formatted URLs and parameters"


class BuildGrafanaDashboardURL(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="build_grafana_dashboard_url",
            description="Builds a Grafana dashboard URL with parameters",
            parameters={
                "uid": ToolParameter(
                    description="The UID of the Grafana dashboard",
                    type="string",
                    required=True,
                ),
                "slug": ToolParameter(
                    description="The slug of the Grafana dashboard",
                    type="string",
                    required=True,
                ),
                "additional_params": ToolParameter(
                    description="A comma-separated list of key=value pairs representing additional parameters for the dashboard URL. Example: 'var-cluster=my-cluster,var-namespace=my-namespace,var-pod=my-pod'",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        uid = params.get("uid")
        slug = params.get("slug")
        base_url = urljoin(self._toolset._grafana_config.url, f"/d/{uid}/{slug}")
        additional_params = params.get("additional_params", "")

        # Convert the comma-separated string to a dictionary
        params_dict = (
            dict(parse_qsl(additional_params.replace(",", "&")))
            if additional_params
            else {}
        )

        # Ensure var-datasource=prometheus is always included
        params_dict["var-datasource"] = (
            self._toolset._grafana_config.grafana_datasource_uid
        )

        # if "var-cluster" not in params_dict or not params_dict["var-cluster"]:
        params_dict["var-cluster"] = ""
        if "refresh" not in params_dict or not params_dict["refresh"]:
            params_dict["refresh"] = "5s"
        query_string = urlencode(params_dict)
        dashboard_url = f"{base_url}?{query_string}" if query_string else base_url

        return dashboard_url

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Generate a Grafana dashboard URL with parameters: {params.get('additional_params', '')}"


class GrafanaToolset(BaseGrafanaToolset):
    def __init__(self):
        super().__init__(
            name="grafana/grafana",
            description="Provides tools for interacting with Grafana dashboards",
            icon_url="https://w7.pngwing.com/pngs/434/923/png-transparent-grafana-hd-logo-thumbnail.png",
            docs_url="",
            tools=[
                ListGrafanaDashboards(self),
                BuildGrafanaDashboardURL(self),
            ],
        )
