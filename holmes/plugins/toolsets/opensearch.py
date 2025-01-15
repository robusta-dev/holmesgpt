import logging
from typing import Any, Dict, List, Optional
from holmes.core.tools import StaticPrerequisite, Tool, ToolParameter, Toolset, ToolsetTag
from opensearchpy import OpenSearch

class OpenSearchClient:
    def __init__(self, **kwargs):
        
        # Handle http_auth explicitly
        if "http_auth" in kwargs:
            http_auth = kwargs.pop("http_auth")
            if isinstance(http_auth, dict):
                kwargs["http_auth"] = (http_auth.get("username"), http_auth.get("password"))
        # Initialize OpenSearch client
        self.client = OpenSearch(**kwargs)

def get_client(clients:List[OpenSearchClient], host:Optional[str]):
    if len(clients) == 1:
        return clients[0]

    if not host:
        raise Exception("Missing host to resolve opensearch client")

    for client in clients:
        found = any(host in client.hosts for client in clients)
        if found:
            return client

    raise Exception(f"Failed to resolve opensearch client. Could not find a matching host: {host}")

class ListShards(Tool):
    def __init__(self, opensearch_clients:List[OpenSearchClient]):
        super().__init__(
            name = "opensearch_list_shards",
            description = "List the shards within an opensearch cluster",
            parameters = {
                "host": ToolParameter(
                    description="The cluster host",
                    type="string",
                    required=False,
                )
            },
        )
        self._opensearch_clients = opensearch_clients

    def invoke(self, params:Any) -> str:
        client = get_client(self._opensearch_clients, host=params.get("host", ""))
        shards = client.client.cat.shards()
        return str(shards)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"opensearch ListShards({params.get('host')})"

class GetClusterSettings(Tool):
    def __init__(self, opensearch_clients:List[OpenSearchClient]):
        super().__init__(
            name = "opensearch_get_cluster_settings",
            description = "Retrieve the cluster's settings",
            parameters = {
                "host": ToolParameter(
                    description="The cluster host",
                    type="string",
                    required=False,
                )
            },
        )
        self._opensearch_clients = opensearch_clients

    def invoke(self, params:Any) -> str:
        client = get_client(self._opensearch_clients, host=params.get("host"))
        response = client.client.cluster.get_settings(
            include_defaults=True,
            flat_settings=True
        )
        return str(response)

    def get_parameterized_one_liner(self, params) -> str:
        return f"opensearch GetClusterSettings({params.get('host')})"


class GetClusterHealth(Tool):
    def __init__(self, opensearch_clients:List[OpenSearchClient]):
        super().__init__(
            name = "opensearch_get_cluster_health",
            description = "Retrieve the cluster's health",
            parameters = {
                "host": ToolParameter(
                    description="The cluster host",
                    type="string",
                    required=False,
                )
            },
        )
        self._opensearch_clients = opensearch_clients

    def invoke(self, params:Any) -> str:
        client = get_client(self._opensearch_clients, host=params.get("host", ""))
        health = client.client.cluster.health()
        return str(health)

    def get_parameterized_one_liner(self, params) -> str:
        return f"opensearch GetClusterSettings({params.get('host')})"

class OpenSearchToolset(Toolset):
    def __init__(self, clusters_configs:List[Dict]):
        clients: List[OpenSearchClient] = []
        for config in clusters_configs:
            try:
                logging.info(f"Setting up OpenSearch client")
                client = OpenSearchClient(**config)
                if client.client.cluster.health():
                    clients.append(client)
            except Exception:
                logging.exception("Failed to set up opensearch client")

        super().__init__(
            name = "opensearch",
            description="Provide cluster metadata information like health, shards, settings.",
            docs_url="https://opensearch.org/docs/latest/clients/python-low-level/",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/9/91/Opensearch_Logo.svg",
            prerequisites = [
                StaticPrerequisite(enabled=len(clients) > 0, disabled_reason="No opensearch client was configured")
            ],
            tools = [
                ListShards(clients),
                GetClusterSettings(clients),
                GetClusterHealth(clients),
            ],
            tags=[ToolsetTag.CORE,]
        )
        self._clients = clients
