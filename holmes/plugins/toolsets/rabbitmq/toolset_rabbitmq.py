from enum import Enum
import os
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
from pydantic import BaseModel
from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from requests.auth import HTTPBasicAuth
from requests import RequestException
from urllib.parse import urljoin

from holmes.plugins.toolsets.utils import get_param_or_raise

class ClusterConnectionStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"

class RabbitMQClusterConfig(BaseModel):
    id: str = "rabbitmq" # must be unique
    management_url: str # e.g., http://rabbitmq-service:15672
    username: str = "guest"
    password: str = "guest"
    healthcheck_vhost: str = "/" # Virtual host for the aliveness test
    request_timeout_seconds: int = 30

    # For internal use
    connection_status: Optional[ClusterConnectionStatus] = None
    connection_error: Optional[str] = None

class RabbitMQConfig(BaseModel):
    clusters: List[RabbitMQClusterConfig]

class BaseRabbitMQTool(Tool):
    toolset: "RabbitMQToolset"

    def _get_cluster_config(self, config:RabbitMQConfig, cluster_id:Optional[str]) -> RabbitMQClusterConfig:

        cluster_ids = [c.id for c in config.clusters]
        if not cluster_id and len(cluster_ids) == 1:
            # cluster id is optional if there is only one configured
            return config.clusters[0]
        elif not cluster_id and len(cluster_ids) > 0:
            raise ValueError(f"No cluster is configured. Possible cluster_id values are: {', '.join(cluster_ids)}")
        elif not cluster_id:
            raise ValueError("No cluster is configured")

        for cluster in config.clusters:
            if cluster.id == cluster_id:
                return cluster
            
        raise ValueError(f"Failed to find cluster_id={cluster_id} amongst configured clusters. Possible cluster_id values are: {', '.join(cluster_ids)}")

    def _get_auth(self, config:RabbitMQConfig, cluster_id:Optional[str]) -> HTTPBasicAuth:
        cluster_config = self._get_cluster_config(config=config, cluster_id=cluster_id)
        return HTTPBasicAuth(
            cluster_config.username,
            cluster_config.password,
        )

    def _get_url(self, config:RabbitMQConfig, cluster_id:Optional[str], endpoint:str) -> str:
        cluster_config = self._get_cluster_config(config=config, cluster_id=cluster_id)
        return urljoin(cluster_config.management_url, endpoint)

    def _make_request(self, cluster_id:str, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> requests.Response:
        """Helper to make requests to the RabbitMQ Management API."""
        if not self.toolset.config:
            raise ValueError("RabbitMQ is not configured.")

        config = self._get_cluster_config(config=self.toolset.config, cluster_id=cluster_id)
        url = self._get_url(config=self.toolset.config, cluster_id=cluster_id, endpoint=endpoint)
        headers = {"Content-Type": "application/json"}

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            auth=self._get_auth(self.toolset.config, cluster_id),
            params=params,
            json=data,
            timeout=config.request_timeout_seconds,
            verify=True # Adjust verify=False if using self-signed certs, but be aware of security implications
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response
    
class ListConfiguredClusters(BaseRabbitMQTool):
    def __init__(self, toolset: "RabbitMQToolset"):
        super().__init__(
            name="list_configured_clusters",
            description="List all configured clusters. Useful to get the id of a configured cluster (cluster_id) and pass as argument to other rabbitmq tool calls.",
            parameters={},
            toolset=toolset,
        )
    
    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config:
            raise ValueError("RabbitMQ is not configured.")
        
        available_clusters = [{"cluster_id": c.id, "management_url": c.management_url} for c in self.toolset.config.clusters if c.connection_status == ClusterConnectionStatus.SUCCESS]
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=available_clusters
        )
    
    def get_parameterized_one_liner(self, params) -> str:
        return "list configured RabbitMQ clusters"


class GetRabbitMQClusterStatus(BaseRabbitMQTool):
    def __init__(self, toolset: "RabbitMQToolset"):
        super().__init__(
            name="get_rabbitmq_cluster_status",
            description="Fetches the overall status of the RabbitMQ cluster, including node information, listeners, and partition details. Crucial for detecting split-brain scenarios (network partitions).",
            parameters={
                "cluster_id": ToolParameter(
                    description="The id of the cluster obtained with list_configured_clusters. Only required if more than one rabbitmq cluster is configured.",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config:
            raise ValueError("RabbitMQ is not configured.")
        try:
            # Fetch node details which include partition info
            nodes_response = self._make_request(cluster_id=params.get("cluster_id"), method="GET", endpoint="api/nodes")
            nodes_data = nodes_response.json()

            # Fetch cluster name (optional but nice context)
            cluster_name = "Unknown"
            try:
                cluster_name_response = self._make_request(cluster_id=params.get("cluster_id"), method="GET", endpoint="api/cluster-name")
                cluster_name = cluster_name_response.json().get("name", "Unknown")
            except Exception:
                logging.warning("Could not fetch RabbitMQ cluster name.", exc_info=True) # Non-fatal

            # Process data to highlight partitions
            partitions = []
            node_statuses = []
            for node in nodes_data:
                node_name = node.get("name", "unknown_node")
                running = node.get("running", False)
                node_partitions = node.get("partitions", [])
                if node_partitions:
                    # A node lists partitions it cannot reach
                    partitions.append({"node": node_name, "unreachable_nodes": node_partitions})
                node_statuses.append({"node": node_name, "running": running})

            result = {
                "cluster_name": cluster_name,
                "nodes": node_statuses,
                "network_partitions_detected": bool(partitions),
                "partition_details": partitions, # Shows which nodes report partitions
                "raw_node_data": nodes_data # Include raw data for more context if needed by LLM
            }
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=result
            )

        except RequestException as e:
            logging.info("Failed to fetch RabbitMQ cluster status", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Network error while fetching RabbitMQ cluster status: {str(e)}",
                data=None
            )
        except Exception as e:
            logging.info("Failed to process RabbitMQ cluster status", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error fetching RabbitMQ cluster status: {str(e)}",
                data=None
            )

    def get_parameterized_one_liner(self, params) -> str:
        return "get RabbitMQ cluster status and partition information"


class GetRabbitMQNodeDetails(BaseRabbitMQTool):
    def __init__(self, toolset: "RabbitMQToolset"):
        super().__init__(
            name="get_rabbitmq_node_details",
            description="Fetches detailed information about a specific RabbitMQ node, including memory usage, disk space, file descriptors, and running status. Useful for diagnosing resource issues on a node.",
            parameters={
                "node_name": ToolParameter(
                    description="The full name of the RabbitMQ node (e.g., 'rabbit@hostname').",
                    type="string",
                    required=True,
                ),
                "cluster_id": ToolParameter(
                    description="The id of the cluster obtained with list_configured_clusters. Only required if more than one rabbitmq cluster is configured.",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        node_name = get_param_or_raise(params, "node_name")
        try:
            response = self._make_request(cluster_id=params.get("cluster_id"), method="GET", endpoint=f"api/nodes/{node_name}")
            node_data = response.json()

            # Simplify the output slightly for clarity
            simplified_data = {
                "name": node_data.get("name"),
                "type": node_data.get("type"),
                "running": node_data.get("running"),
                "mem_used": node_data.get("mem_used"),
                "mem_limit": node_data.get("mem_limit"),
                "mem_alarm": node_data.get("mem_alarm"),
                "disk_free": node_data.get("disk_free"),
                "disk_free_limit": node_data.get("disk_free_limit"),
                "disk_free_alarm": node_data.get("disk_free_alarm"),
                "fd_used": node_data.get("fd_used"),
                "fd_total": node_data.get("fd_total"),
                "fd_alarm": node_data.get("proc_alarm"), # Note: check API doc, might be fd_alarm or proc_alarm
                "sockets_used": node_data.get("sockets_used"),
                "sockets_total": node_data.get("sockets_total"),
                "uptime": node_data.get("uptime"),
                "partitions": node_data.get("partitions"), # Include partition info from this node's perspective
            }
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=simplified_data
            )

        except RequestException as e:
            if e.response is not None and e.response.status_code == 404:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Error: RabbitMQ node '{node_name}' not found.",
                    data=None
                )
            logging.info(f"Failed to fetch details for RabbitMQ node {node_name}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Network error while fetching details for RabbitMQ node {node_name}: {str(e)}",
                data=None
            )
        except Exception as e:
            logging.info(f"Failed to process details for RabbitMQ node {node_name}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error fetching details for RabbitMQ node {node_name}: {str(e)}",
                data=None
            )

    def get_parameterized_one_liner(self, params) -> str:
        node_name = params.get('node_name', '<missing>')
        return f"get detailed status for RabbitMQ node '{node_name}'"


class RabbitMQToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="rabbitmq/core",
            description="Provides tools to interact with RabbitMQ Management API for diagnosing cluster health, node status, and specifically network partitions (split-brain).",
            docs_url="https://www.rabbitmq.com/docs/management.html", # General Management API docs
            icon_url="https://cdn.worldvectorlogo.com/logos/rabbitmq.svg", # Example icon URL
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                ListConfiguredClusters(toolset=self),
                GetRabbitMQClusterStatus(toolset=self),
                GetRabbitMQNodeDetails(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE
            ],
        )
        self._reload_llm_instructions()

    def _reload_llm_instructions(self):
        # Load instructions from the jinja2 template file
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "rabbitmq_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config or not config.get("clusters"):
            # Attempt to load from environment variables as fallback
            env_url = os.environ.get("RABBITMQ_MANAGEMENT_URL")
            env_user = os.environ.get("RABBITMQ_USERNAME", "guest")
            env_pass = os.environ.get("RABBITMQ_PASSWORD", "guest")
            if not env_url:
                return (False, "RabbitMQ toolset is misconfigured. 'management_url' is required.")
            config = {
                "clusters": [{
                    "management_url": env_url,
                    "username": env_user,
                    "password": env_pass,
                }]
            }
            logging.info("Loaded RabbitMQ config from environment variables.")

        try:
            self.config = RabbitMQConfig(**config)
        except Exception as e:
            return (False, f"Failed to parse RabbitMQ configuration: {str(e)}")

        return self._check_clusters_config(self.config)


    def _check_clusters_config(self, config: RabbitMQConfig) -> Tuple[bool, str]:
        """Performs an aliveness test against the RabbitMQ Management APIs."""
        if not config:
            return (False, f"Toolset {self.name} cannot perform health check; configuration is missing.")


        errors = []
        for cluster_config in config.clusters:


            # Use the /api/aliveness-test endpoint
            # Requires a vhost parameter
            vhost = cluster_config.healthcheck_vhost
            # URL encode vhost name, especially '/' which becomes '%2F'
            encoded_vhost = requests.utils.quote(vhost, safe='')
            health_check_endpoint = f"api/aliveness-test/{encoded_vhost}"
            url = urljoin(cluster_config.management_url, health_check_endpoint)

            try:
                response = requests.get(
                    url=url,
                    auth=HTTPBasicAuth(cluster_config.username, cluster_config.password),
                    timeout=10, # Shorter timeout for health check
                    verify=True # As per _make_request default
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        # Reload instructions now that config is validated and healthy
                        self._reload_llm_instructions()
                        cluster_config.connection_status = ClusterConnectionStatus.SUCCESS
                    else:
                        error_message = f"RabbitMQ aliveness test failed for cluster with id={cluster_config.id} at {url}: Status was not 'ok'. Response: {response.text}"
                        cluster_config.connection_status = ClusterConnectionStatus.ERROR
                        errors.append(error_message)
                else:
                    error_message = f"Failed to connect to RabbitMQ Management API for cluster with id={cluster_config.id} at {url} at {url} for health check: HTTP {response.status_code}. Response: {response.text}"
                    cluster_config.connection_status = ClusterConnectionStatus.ERROR
                    errors.append(error_message)

            except RequestException as e:
                error_message = f"Toolset failed health check for cluster with id={cluster_config.id} at {url} due to a failed http request. Connection error: {str(e)}"
                cluster_config.connection_status = ClusterConnectionStatus.ERROR
                errors.append(error_message)
            except Exception as e:
                error_message = f"Toolset failed health check for cluster with id={cluster_config.id} at {url}: {str(e)}"
                cluster_config.connection_status = ClusterConnectionStatus.ERROR
                errors.append(error_message)
            
        if errors:
            if len(errors) == 1:
                return (False, errors[0])
            else:
                return (False, "\n".join([f"- {error}" for error in errors]))
        else:
            return (True, "")

    def get_example_config(self):
        example_config = RabbitMQConfig(
            clusters=[
                RabbitMQClusterConfig(
                    management_url="http://<your-rabbitmq-server-or-service>:15672",
                    username="admin_user",
                    password="admin_password",
                    healthcheck_vhost="/"
            )]
        )
        return example_config.model_dump()