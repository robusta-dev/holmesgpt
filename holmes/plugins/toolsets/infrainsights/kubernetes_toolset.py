"""
Kubernetes Toolset for InfraInsights

Provides tools for investigating Kubernetes clusters, pods, and resources
in the InfraInsights multi-instance architecture.
"""

import json
import logging
from typing import Dict, List, Optional, Any
import requests

from holmes.core.tools import (
    StructuredToolResult,
    ToolParameter,
    ToolResultStatus,
)
from holmes.plugins.toolsets.utils import get_param_or_raise

from .base_toolset import BaseInfraInsightsTool, BaseInfraInsightsToolset


class KubernetesConnection:
    """Manages Kubernetes connection through InfraInsights API"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get('base_url', 'http://localhost:3000')
        self.session = requests.Session()
        
        # Set up authentication
        if config.get('api_key'):
            self.session.headers.update({
                'Authorization': f'Bearer {config["api_key"]}',
                'Content-Type': 'application/json'
            })
        elif config.get('username') and config.get('password'):
            self.session.auth = (config['username'], config['password'])
            self.session.headers.update({'Content-Type': 'application/json'})
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to InfraInsights Kubernetes API"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Kubernetes API request failed: {e}")
            raise Exception(f"Failed to connect to Kubernetes API: {e}")


class ListKubernetesNodes(BaseInfraInsightsTool):
    """List all nodes in the Kubernetes cluster"""
    
    def __init__(self, toolset: "KubernetesToolset"):
        super().__init__(
            name="list_kubernetes_nodes",
            description="List all nodes in the Kubernetes cluster with their status, roles, and resource information",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kubernetes instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kubernetes instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Create connection
            k8s_conn = KubernetesConnection(connection_config)
            
            # Get nodes
            nodes_data = k8s_conn._make_request('GET', '/api/multi-kubernetes/nodes')
            
            # Format response
            result = {
                "cluster_name": instance.name,
                "total_nodes": len(nodes_data),
                "nodes": []
            }
            
            for node in nodes_data:
                result["nodes"].append({
                    "name": node.get('name'),
                    "status": node.get('status'),
                    "roles": node.get('roles'),
                    "version": node.get('version'),
                    "age": node.get('age'),
                    "capacity": node.get('capacity', {}),
                    "allocatable": node.get('allocatable', {}),
                    "conditions": node.get('conditions', [])
                })
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list Kubernetes nodes: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"List Kubernetes nodes for instance: {instance_name}"


class GetKubernetesNodeDetails(BaseInfraInsightsTool):
    """Get detailed information about a specific Kubernetes node"""
    
    def __init__(self, toolset: "KubernetesToolset"):
        super().__init__(
            name="get_kubernetes_node_details",
            description="Get detailed information about a Kubernetes node including pods, resources, and health",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kubernetes instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kubernetes instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
                "node_name": ToolParameter(
                    description="Name of the node to get details for",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Get parameters
            node_name = get_param_or_raise(params, "node_name")
            
            # Create connection
            k8s_conn = KubernetesConnection(connection_config)
            
            # Get node details
            node_data = k8s_conn._make_request('GET', f'/api/multi-kubernetes/nodes/{node_name}')
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(node_data, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Kubernetes node details: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        node_name = params.get('node_name', 'unknown')
        return f"Get Kubernetes node details for {node_name} in instance: {instance_name}"


class ListKubernetesPods(BaseInfraInsightsTool):
    """List pods in the Kubernetes cluster"""
    
    def __init__(self, toolset: "KubernetesToolset"):
        super().__init__(
            name="list_kubernetes_pods",
            description="List pods in the Kubernetes cluster with their status and resource usage",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kubernetes instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kubernetes instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
                "namespace": ToolParameter(
                    description="Namespace to list pods from (default: all namespaces)",
                    type="string",
                    required=False,
                ),
                "node_name": ToolParameter(
                    description="Filter pods by node name",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Get parameters
            namespace = params.get('namespace')
            node_name = params.get('node_name')
            
            # Create connection
            k8s_conn = KubernetesConnection(connection_config)
            
            # Build endpoint
            endpoint = '/api/multi-kubernetes/pods'
            query_params = {}
            
            if namespace:
                query_params['namespace'] = namespace
            if node_name:
                query_params['nodeName'] = node_name
            
            # Get pods
            pods_data = k8s_conn._make_request('GET', endpoint, params=query_params)
            
            # Format response
            result = {
                "cluster_name": instance.name,
                "total_pods": len(pods_data),
                "pods": []
            }
            
            for pod in pods_data:
                result["pods"].append({
                    "name": pod.get('name'),
                    "namespace": pod.get('namespace'),
                    "status": pod.get('status'),
                    "node_name": pod.get('nodeName'),
                    "age": pod.get('age'),
                    "ready": pod.get('ready'),
                    "restart_count": pod.get('restartCount'),
                    "containers": pod.get('containers', {})
                })
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list Kubernetes pods: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        namespace = params.get('namespace', 'all')
        return f"List Kubernetes pods in namespace {namespace} for instance: {instance_name}"


class GetKubernetesClusterHealth(BaseInfraInsightsTool):
    """Get overall Kubernetes cluster health"""
    
    def __init__(self, toolset: "KubernetesToolset"):
        super().__init__(
            name="get_kubernetes_cluster_health",
            description="Get overall Kubernetes cluster health including node status, component health, and resource usage",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kubernetes instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kubernetes instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Create connection
            k8s_conn = KubernetesConnection(connection_config)
            
            # Get cluster health
            health_data = k8s_conn._make_request('GET', '/api/multi-kubernetes/cluster-health')
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(health_data, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Kubernetes cluster health: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"Get Kubernetes cluster health for instance: {instance_name}"


class KubernetesToolset(BaseInfraInsightsToolset):
    """Kubernetes toolset for InfraInsights"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.name = "InfraInsights Kubernetes"
        self.description = "Tools for investigating Kubernetes clusters, nodes, and pods in InfraInsights"
        self.tags = [ToolsetTag.CLUSTER]
        self.enabled = True
        
        # Initialize tools
        self.tools = [
            ListKubernetesNodes(self),
            GetKubernetesNodeDetails(self),
            ListKubernetesPods(self),
            GetKubernetesClusterHealth(self),
        ]
    
    def get_service_type(self) -> str:
        return "kubernetes"
    
    def get_llm_instructions(self) -> str:
        return """
        This toolset provides tools for investigating Kubernetes clusters managed by InfraInsights.
        
        Available tools:
        - list_kubernetes_nodes: List all nodes with status and resource info
        - get_kubernetes_node_details: Get detailed node information including pods
        - list_kubernetes_pods: List pods with filtering by namespace/node
        - get_kubernetes_cluster_health: Get overall cluster health status
        
        When investigating Kubernetes issues:
        1. Start with cluster health to understand overall status
        2. List nodes to identify problematic nodes
        3. Get node details to understand resource usage and pod distribution
        4. List pods to identify specific workload issues
        
        The toolset automatically handles:
        - Multi-instance support (production, staging, etc.)
        - Authentication and connection management
        - User context and access control
        """ 