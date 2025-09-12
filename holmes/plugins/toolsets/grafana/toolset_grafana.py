from typing import Dict, List
from urllib.parse import urlencode, urljoin
from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    StructuredToolResultStatus,
)
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset
import requests  # type: ignore
import logging

from holmes.plugins.toolsets.utils import toolset_name_for_one_liner


class ListAndBuildGrafanaDashboardURLs(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="list_and_build_grafana_dashboard_urls",
            description="Lists all available Grafana dashboard urls",
            parameters={
                "cluster_name": ToolParameter(
                    description="The cluster name. Defaults to None.",
                    type="string",
                    required=False,
                ),
                "namespace": ToolParameter(
                    description="The namespace for filtering dashboards.",
                    type="string",
                    required=False,
                ),
                "node_name": ToolParameter(
                    description="The node name to filter for node-related dashboards.",
                    type="string",
                    required=False,
                ),
                "pod_name": ToolParameter(
                    description="The pod name to filter dashboards.",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        url = urljoin(
            self._toolset._grafana_config.url, "/api/search?query=&type=dash-db"
        )
        headers = {"Authorization": f"Bearer {self._toolset._grafana_config.api_key}"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            dashboards = response.json()
            formatted_dashboards: List[str] = []
            base_url = (
                self._toolset._grafana_config.external_url
                or self._toolset._grafana_config.url
            )
            for dash in dashboards:
                dashboard_url = urljoin(
                    base_url,
                    f"/d/{dash['uid']}/{dash['uri'].split('/')[-1]}",
                )

                params_dict = {
                    "var-cluster": params.get("cluster_name", ""),
                    "var-namespace": params.get("namespace", ""),
                    "var-pod": params.get("pod_name", ""),
                    "var-node": params.get("node_name", ""),
                    "var-datasource": self._toolset._grafana_config.grafana_datasource_uid,
                    "refresh": "5s",
                }

                # If filtering for nodes, ensure only node-related dashboards are included
                if params.get("node_name") and "node" not in dash["title"].lower():
                    continue

                # we add all params since if the dashboard isnt configured for a param it will ignore it if it is added
                query_string = urlencode({k: v for k, v in params_dict.items() if v})
                dashboard_url = (
                    f"{dashboard_url}?{query_string}" if query_string else dashboard_url
                )

                formatted_dashboards.append(
                    f"Title: {dash['title']}\nURL: {dashboard_url}\n"
                )

            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS
                if formatted_dashboards
                else StructuredToolResultStatus.NO_DATA,
                data="\n".join(formatted_dashboards)
                if formatted_dashboards
                else "No dashboards found.",
                url=url,
                params=params,
            )
        except requests.RequestException as e:
            logging.error(f"Error fetching dashboards: {str(e)}")
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Error fetching dashboards: {str(e)}",
                url=url,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return (
            f"{toolset_name_for_one_liner(self._toolset.name)}: List Grafana Dashboards"
        )


class GrafanaToolset(BaseGrafanaToolset):
    def __init__(self):
        super().__init__(
            name="grafana/grafana",
            description="Provides tools for interacting with Grafana dashboards",
            icon_url="https://w7.pngwing.com/pngs/434/923/png-transparent-grafana-hd-logo-thumbnail.png",
            docs_url="",
            tools=[
                ListAndBuildGrafanaDashboardURLs(self),
            ],
        )
