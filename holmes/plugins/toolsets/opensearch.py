import logging
from typing import Any, Dict, List, Optional
from holmes.core.tools import StaticPrerequisite, Tool, ToolParameter, Toolset, ToolsetTag
from opensearchpy import OpenSearch
import json

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

class ListIndexes(Tool):
    def __init__(self, opensearch_clients:List[OpenSearchClient]):
        super().__init__(
            name = "opensearch_list_indexes",
            description = "List the indexes within an opensearch cluster",
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
        aliases = client.client.cat.indices()
        return str(aliases)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"opensearch ListShards({params.get('host')})"

class ReadIndex(Tool):
    def __init__(self, opensearch_clients: List[OpenSearch]):
        super().__init__(
            name="opensearch_read_index",
            description=(
                "Fetch documents from an OpenSearch index. Optionally filter by time range and specify a larger limit."
            ),
            parameters={
                "host": ToolParameter(
                    description="The OpenSearch cluster host",
                    type="string",
                    required=False,
                ),
                "index": ToolParameter(
                    description="The name of the index to fetch documents from",
                    type="string",
                    required=True,
                ),
                "query": ToolParameter(
                    description="The query in JSON format (e.g., '{\"match_all\": {}}')",
                    type="string",
                    required=False,
                    default=json.dumps({"match_all": {}}),
                ),
                "limit": ToolParameter(
                    description="Maximum number of documents to fetch (default is 1000)",
                    type="integer",
                    required=False,
                    default=1000,
                ),
                "start_time": ToolParameter(
                    description="Start of the time frame in ISO 8601 format (e.g., '2025-01-01T00:00:00Z')",
                    type="string",
                    required=False,
                ),
                "end_time": ToolParameter(
                    description="End of the time frame in ISO 8601 format (e.g., '2025-01-01T23:59:59Z')",
                    type="string",
                    required=False,
                ),
            },
        )
        self._opensearch_clients = opensearch_clients

    def invoke(self, params: Any) -> str:
        client = get_client(self._opensearch_clients, host=params.get("host", ""))
        index = params.get("index")
        query = json.loads(params.get("query", json.dumps({"match_all": {}})))
        limit = params.get("limit", 1000)

        # Add time range to the query if start_time or end_time is provided
        if params.get("start_time") or params.get("end_time"):
            time_range = {}
            if params.get("start_time"):
                time_range["gte"] = params.get("start_time")
            if params.get("end_time"):
                time_range["lte"] = params.get("end_time")

            query = {
                "bool": {
                    "must": query,
                    "filter": {
                        "range": {
                            "@timestamp": {
                                **time_range,
                                "format": "strict_date_optional_time",
                            }
                        }
                    },
                }
            }


        response = client.client.search(
            index=index,
            body={
                "size": limit,
                "query": query,
            },
        )
        return json.dumps(response, indent=2)

    def get_parameterized_one_liner(self, params) -> str:
        return (
            f"opensearch ReadIndex(index={params.get('index')}, query={params.get('query')}, "
            f"start_time={params.get('start_time')}, end_time={params.get('end_time')})"
        )

        
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
                ListIndexes(clients),
                ReadIndex(clients)
            ],
            tags=[ToolsetTag.CORE,]
        )
        self._clients = clients
