
from enum import Enum
from typing import Dict, List, Optional
from urllib.parse import urljoin

from pydantic import BaseModel
import requests
from requests.auth import HTTPBasicAuth

class ClusterConnectionStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"

class RabbitMQClusterConfig(BaseModel):
    id: str = "rabbitmq"  # must be unique
    management_url: str  # e.g., http://rabbitmq-service:15672
    username: Optional[str] = None
    password: Optional[str] = None
    request_timeout_seconds: int = 30
    verify_certs: bool = True

    # For internal use
    connection_status: Optional[ClusterConnectionStatus] = None
    connection_error: Optional[str] = None

def get_auth(config: RabbitMQClusterConfig) -> Optional[HTTPBasicAuth]:
    if config.username or config.password:
        return HTTPBasicAuth(
            config.username or "guest",
            config.password or "guest",
        )
    else:
        return None

def get_url(config: RabbitMQClusterConfig, endpoint: str
) -> str:
    return urljoin(config.management_url, endpoint)

def make_request(
    config: RabbitMQClusterConfig,
    method: str,
    url: str,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None,
) -> requests.Response:

    headers = {"Content-Type": "application/json"}

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        auth=get_auth(config),
        params=params,
        json=data,
        timeout=config.request_timeout_seconds,
        verify=config.verify_certs,
    )
    response.raise_for_status()
    return response

def get_cluster_health_from_management_url(config: RabbitMQClusterConfig):
    
    url = get_url(
        config=config, endpoint="api/nodes"
    )

    response = make_request(
        config=config,
        method="GET",
        url=url,
    )
    nodes_data = response.json()

    cluster_health = []

    for node_data in nodes_data:
        cluster_health.append(
            # Simplify the output for clarity
            {
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
                "fd_alarm": node_data.get(
                    "proc_alarm"
                ),
                "sockets_used": node_data.get("sockets_used"),
                "sockets_total": node_data.get("sockets_total"),
                "uptime": node_data.get("uptime"),
                "partitions": node_data.get(
                    "partitions"
                ), 
                "cluster_links": node_data.get(
                    "cluster_links"
                ),
            }
        )

    return cluster_health

def get_node_status(config: RabbitMQClusterConfig):

    url = get_url(
        config=config, endpoint="api/nodes"
    )

    response = make_request(
        config=config,
        method="GET",
        url=url,
    )
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
        "fd_alarm": node_data.get(
            "proc_alarm"
        ),
        "sockets_used": node_data.get("sockets_used"),
        "sockets_total": node_data.get("sockets_total"),
        "uptime": node_data.get("uptime"),
        "partitions": node_data.get(
            "partitions"
        ), 
        "cluster_links": node_data.get(
            "cluster_links"
        ),
    }

    return simplified_data