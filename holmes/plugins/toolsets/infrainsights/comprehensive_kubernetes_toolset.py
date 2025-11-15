import logging
import tempfile
import os
import re
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config import kube_config

# Import base classes
from .base_toolset_v2 import BaseInfraInsightsToolsetV2
from kubernetes.config.kube_config import KubeConfigLoader
import base64
import json

from holmes.core.tools import (
    Toolset, Tool, ToolsetTag, CallablePrerequisite, ToolParameter, 
    ToolResultStatus, StructuredToolResult
)
from holmes.plugins.toolsets.infrainsights.infrainsights_client_v2 import (
    InfraInsightsClientV2, InfraInsightsConfig, ServiceInstance
)

logger = logging.getLogger(__name__)


# ============================================
# ENHANCED CONTAINER INTELLIGENCE UTILITIES
# ============================================

class EnhancedContainerHandler:
    """Enhanced container handling logic for intelligent container detection and multi-container operations"""
    
    @staticmethod
    def should_check_all_containers(prompt: str) -> bool:
        """Determine if prompt indicates checking all containers"""
        if not prompt:
            return False
            
        all_container_patterns = [
            r'all\s+containers?',
            r'check.*all.*containers?', 
            r'containers?\s+of\s+pod',
            r'every\s+container',
            r'each\s+container',
            r'all\s+container.*of.*pod',
            r'investigate.*containers?',
            r'check.*for.*all.*container',
            r'logs.*from.*all.*container',
            r'all.*container.*logs'
        ]
        
        for pattern in all_container_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                logger.info(f"🔍 Detected 'all containers' request with pattern: {pattern}")
                return True
        return False
    
    @staticmethod
    def extract_container_name(prompt: str) -> Optional[str]:
        """Extract specific container name from prompt"""
        if not prompt:
            return None
            
        patterns = [
            r'container[:\s]+([a-zA-Z0-9\-_]+)',
            r'container_name[:\s]+([a-zA-Z0-9\-_]+)',
            r'([a-zA-Z0-9\-_]+)\s+container',
            r'container\s+([a-zA-Z0-9\-_]+)',
            r'in\s+container\s+([a-zA-Z0-9\-_]+)',
            r'from\s+container\s+([a-zA-Z0-9\-_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1)
                if extracted.lower() not in ['container', 'in', 'from']:
                    logger.info(f"🔍 Extracted container name from prompt: {extracted}")
                    return extracted
        return None

    @staticmethod
    def get_pod_containers(core_api: client.CoreV1Api, pod_name: str, namespace: str) -> List[Dict[str, Any]]:
        """Get all containers in a pod with their status"""
        try:
            pod = core_api.read_namespaced_pod(name=pod_name, namespace=namespace)
            containers = []
            
            for container in pod.spec.containers:
                container_status = None
                if pod.status.container_statuses:
                    container_status = next(
                        (cs for cs in pod.status.container_statuses if cs.name == container.name), 
                        None
                    )
                
                containers.append({
                    'name': container.name,
                    'image': container.image,
                    'ready': container_status.ready if container_status else False,
                    'restart_count': container_status.restart_count if container_status else 0,
                    'state': str(container_status.state) if container_status else 'Unknown'
                })
            
            logger.info(f"🔍 Found {len(containers)} containers in pod {pod_name}: {[c['name'] for c in containers]}")
            return containers
        except Exception as e:
            logger.error(f"Failed to get pod containers: {e}")
            return []

    @staticmethod 
    def fetch_logs_all_containers(core_api: client.CoreV1Api, pod_name: str, namespace: str, **kwargs) -> Dict[str, Dict[str, Any]]:
        """Fetch logs from all containers in a pod"""
        containers = EnhancedContainerHandler.get_pod_containers(core_api, pod_name, namespace)
        all_logs = {}
        
        for container in containers:
            try:
                container_kwargs = kwargs.copy()
                container_kwargs['container'] = container['name']
                
                logs = core_api.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    **container_kwargs
                )
                
                all_logs[container['name']] = {
                    'logs': logs if logs else "No logs available",
                    'container_info': container
                }
                
                logger.info(f"🔍 Successfully fetched logs for container: {container['name']}")
                
            except Exception as e:
                logger.error(f"Failed to fetch logs for container {container['name']}: {e}")
                all_logs[container['name']] = {
                    'logs': f"Error fetching logs: {str(e)}",
                    'container_info': container
                }
        
        return all_logs


# ============================================
# PHASE 1: BASIC KUBERNETES TOOLS
# ============================================

class KubernetesHealthCheckTool(Tool):
    """Tool to check Kubernetes cluster health and connectivity"""
    
    name: str = "kubernetes_health_check"
    description: str = "Check the health status of a Kubernetes cluster including node status and basic cluster info"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance to check",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_health_check",
            description="Check the health status of a Kubernetes cluster including node status and basic cluster info",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance to check",
                    type="string",
                    required=True
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Check Kubernetes cluster health"""
        try:
            instance_name = params.get("instance_name")
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name is required",
                    params=params
                )
            
            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )
            
            # Check cluster health
            health_info = self._check_cluster_health(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=health_info,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to check Kubernetes health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Kubernetes health: {str(e)}",
                params=params
            )

    def _check_cluster_health(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Check cluster health using Kubernetes Python client"""
        try:
            # Create Kubernetes client from kubeconfig
            k8s_client = self._create_kubernetes_client(instance)
            
            health_info = {
                "instance_info": {
                    "name": instance.name,
                    "environment": instance.environment,
                    "status": instance.status,
                    "description": instance.description
                },
                "cluster_health": {},
                "node_status": {},
                "component_status": {}
            }
            
            # Get cluster info
            try:
                version_api = client.VersionApi(k8s_client)
                version_info = version_api.get_code()
                health_info["cluster_health"]["cluster_info"] = {
                    "kubernetes_version": version_info.git_version,
                    "platform": version_info.platform,
                    "go_version": version_info.go_version
                }
            except Exception as e:
                health_info["cluster_health"]["cluster_info_error"] = str(e)
            
            # Get node status
            try:
                core_api = client.CoreV1Api(k8s_client)
                nodes = core_api.list_node()
                node_status = {
                    "total_nodes": len(nodes.items),
                    "ready_nodes": 0,
                    "not_ready_nodes": 0,
                    "node_details": []
                }
                
                for node in nodes.items:
                    node_info = {
                        "name": node.metadata.name,
                        "status": "Unknown",
                        "conditions": []
                    }
                    
                    for condition in node.status.conditions:
                        if condition.type == "Ready":
                            node_info["status"] = "Ready" if condition.status == "True" else "NotReady"
                            if condition.status == "True":
                                node_status["ready_nodes"] += 1
                            else:
                                node_status["not_ready_nodes"] += 1
                        
                        node_info["conditions"].append({
                            "type": condition.type,
                            "status": condition.status,
                            "message": condition.message
                        })
                    
                    node_status["node_details"].append(node_info)
                
                health_info["node_status"]["nodes"] = node_status
            except Exception as e:
                health_info["node_status"]["nodes_error"] = str(e)
            
            # Get component status
            try:
                component_status = core_api.list_component_status()
                components = {}
                for comp in component_status.items:
                    components[comp.metadata.name] = {
                        "healthy": comp.conditions[0].status == "True" if comp.conditions else False,
                        "message": comp.conditions[0].message if comp.conditions else "Unknown"
                    }
                health_info["component_status"]["components"] = components
            except Exception as e:
                health_info["component_status"]["components_error"] = str(e)
            
            # Determine overall health
            if (health_info["node_status"].get("ready_nodes", 0) > 0 and 
                health_info["node_status"].get("not_ready_nodes", 0) == 0):
                health_info["overall_health"] = "healthy"
            elif health_info["node_status"].get("ready_nodes", 0) > 0:
                health_info["overall_health"] = "degraded"
            else:
                health_info["overall_health"] = "unhealthy"
            
            return health_info
            
        except Exception as e:
            logger.error(f"Failed to check cluster health: {e}", exc_info=True)
            return {
                "error": f"Failed to check cluster health: {str(e)}",
                "overall_health": "unknown"
            }

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        return f"kubernetes_health_check(instance_name={instance_name})"

class KubernetesListResourcesTool(Tool):
    """Tool to list Kubernetes resources"""
    
    name: str = "kubernetes_list_resources"
    description: str = "List Kubernetes resources by kind, namespace, and other filters"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "kind": ToolParameter(
            description="Resource kind (e.g., pods, services, deployments)",
            type="string",
            required=True
        ),
        "namespace": ToolParameter(
            description="Namespace to search in (optional, use 'all' for all namespaces)",
            type="string",
            required=False
        ),
        "output_format": ToolParameter(
            description="Output format (wide, json, yaml)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_list_resources",
            description="List Kubernetes resources by kind, namespace, and other filters",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "kind": ToolParameter(
                    description="Resource kind (e.g., pods, services, deployments)",
                    type="string",
                    required=True
                ),
                "namespace": ToolParameter(
                    description="Namespace to search in (optional, use 'all' for all namespaces)",
                    type="string",
                    required=False
                ),
                "output_format": ToolParameter(
                    description="Output format (wide, json, yaml)",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """List Kubernetes resources"""
        try:
            instance_name = params.get("instance_name")
            kind = params.get("kind", "").lower()
            namespace = params.get("namespace", "default")
            output_format = params.get("output_format", "wide")
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name is required",
                    params=params
                )
            
            if not kind:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Resource kind is required",
                    params=params
                )
            
            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )
            
            # List resources
            resources = self._list_resources(instance, kind, namespace, output_format)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'kind': kind,
                    'namespace': namespace,
                    'output_format': output_format,
                    'result': resources
                },
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to list Kubernetes resources: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list Kubernetes resources: {str(e)}",
                params=params
            )

    def _list_resources(self, instance: ServiceInstance, kind: str, namespace: str, output_format: str) -> Dict[str, Any]:
        """List resources using Kubernetes Python client"""
        try:
            # Normalize kind to plural form (accept both singular and plural)
            kind_mapping = {
                "pod": "pods",
                "pods": "pods",
                "service": "services",
                "services": "services",
                "svc": "services",
                "deployment": "deployments",
                "deployments": "deployments",
                "deploy": "deployments"
            }
            normalized_kind = kind_mapping.get(kind.lower(), kind.lower())
            
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            apps_api = client.AppsV1Api(k8s_client)
            
            resources = {
                "instance_name": instance.name,
                "kind": normalized_kind,
                "namespace": namespace,
                "output_format": output_format,
                "items": []
            }
            
            if normalized_kind == "pods":
                if namespace == "all":
                    response = core_api.list_pod_for_all_namespaces()
                else:
                    response = core_api.list_namespaced_pod(namespace=namespace)
                
                for pod in response.items:
                    pod_info = {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "status": pod.status.phase,
                        "ready": f"{pod.status.container_statuses[0].ready if pod.status.container_statuses else False}/{len(pod.spec.containers)}",
                        "restarts": pod.status.container_statuses[0].restart_count if pod.status.container_statuses else 0,
                        "age": str(pod.metadata.creation_timestamp) if pod.metadata.creation_timestamp else "Unknown"
                    }
                    resources["items"].append(pod_info)
            
            elif normalized_kind == "services":
                if namespace == "all":
                    response = core_api.list_service_for_all_namespaces()
                else:
                    response = core_api.list_namespaced_service(namespace=namespace)
                
                for svc in response.items:
                    svc_info = {
                        "name": svc.metadata.name,
                        "namespace": svc.metadata.namespace,
                        "type": svc.spec.type,
                        "cluster_ip": svc.spec.cluster_ip,
                        "external_ip": svc.status.load_balancer.ingress[0].ip if svc.status.load_balancer.ingress else "None",
                        "ports": [f"{port.port}:{port.target_port}/{port.protocol}" for port in svc.spec.ports] if svc.spec.ports else []
                    }
                    resources["items"].append(svc_info)
            
            elif normalized_kind == "deployments":
                if namespace == "all":
                    response = apps_api.list_deployment_for_all_namespaces()
                else:
                    response = apps_api.list_namespaced_deployment(namespace=namespace)
                
                for deploy in response.items:
                    deploy_info = {
                        "name": deploy.metadata.name,
                        "namespace": deploy.metadata.namespace,
                        "ready": f"{deploy.status.ready_replicas or 0}/{deploy.spec.replicas}",
                        "up_to_date": deploy.status.updated_replicas or 0,
                        "available": deploy.status.available_replicas or 0,
                        "age": str(deploy.metadata.creation_timestamp) if deploy.metadata.creation_timestamp else "Unknown"
                    }
                    resources["items"].append(deploy_info)
            
            else:
                return {
                    "error": f"Unsupported resource kind: {kind}. Supported kinds: pod/pods, service/services/svc, deployment/deployments/deploy"
                }
            
            resources["total_count"] = len(resources["items"])
            return resources
            
        except Exception as e:
            logger.error(f"Failed to list resources: {e}", exc_info=True)
            return {"error": f"Failed to list resources: {str(e)}"}

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        kind = params.get("kind", "pods")
        namespace = params.get("namespace", "default")
        return f"kubernetes_list_resources(instance_name={instance_name}, kind={kind}, namespace={namespace})"

class KubernetesDescribeResourceTool(Tool):
    """Tool to describe Kubernetes resources"""
    
    name: str = "kubernetes_describe_resource"
    description: str = "Get detailed description of a Kubernetes resource"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "kind": ToolParameter(
            description="Resource kind (e.g., pod, service, deployment)",
            type="string",
            required=True
        ),
        "name": ToolParameter(
            description="Resource name",
            type="string",
            required=True
        ),
        "namespace": ToolParameter(
            description="Namespace (optional)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_describe_resource",
            description="Get detailed description of a Kubernetes resource",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "kind": ToolParameter(
                    description="Resource kind (e.g., pod, service, deployment)",
                    type="string",
                    required=True
                ),
                "name": ToolParameter(
                    description="Resource name",
                    type="string",
                    required=True
                ),
                "namespace": ToolParameter(
                    description="Namespace (optional)",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Describe Kubernetes resource"""
        try:
            instance_name = params.get("instance_name")
            kind = params.get("kind", "").lower()
            name = params.get("name")
            namespace = params.get("namespace", "default")
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name is required",
                    params=params
                )
            
            if not kind or not name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Resource kind and name are required",
                    params=params
                )
            
            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )
            
            # Describe resource
            resource_info = self._describe_resource(instance, kind, name, namespace)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'kind': kind,
                    'name': name,
                    'namespace': namespace,
                    'description': resource_info
                },
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to describe Kubernetes resource: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to describe Kubernetes resource: {str(e)}",
                params=params
            )

    def _describe_resource(self, instance: ServiceInstance, kind: str, name: str, namespace: str) -> Dict[str, Any]:
        """Describe resource using Kubernetes Python client"""
        try:
            # Normalize kind to singular form (accept both singular and plural)
            kind_mapping = {
                "pods": "pod",
                "pod": "pod",
                "services": "service",
                "service": "service",
                "svc": "service",
                "deployments": "deployment",
                "deployment": "deployment",
                "deploy": "deployment"
            }
            normalized_kind = kind_mapping.get(kind.lower(), kind.lower())
            
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            apps_api = client.AppsV1Api(k8s_client)
            
            resource_info = {
                "instance_name": instance.name,
                "kind": normalized_kind,
                "name": name,
                "namespace": namespace,
                "details": {}
            }
            
            if normalized_kind == "pod":
                try:
                    pod = core_api.read_namespaced_pod(name=name, namespace=namespace)
                    resource_info["details"] = {
                        "metadata": {
                            "name": pod.metadata.name,
                            "namespace": pod.metadata.namespace,
                            "creation_timestamp": str(pod.metadata.creation_timestamp),
                            "labels": pod.metadata.labels,
                            "annotations": pod.metadata.annotations
                        },
                        "status": {
                            "phase": pod.status.phase,
                            "pod_ip": pod.status.pod_ip,
                            "host_ip": pod.status.host_ip,
                            "start_time": str(pod.status.start_time) if pod.status.start_time else None
                        },
                        "containers": []
                    }
                    
                    for container in pod.spec.containers:
                        container_status = next((cs for cs in pod.status.container_statuses if cs.name == container.name), None)
                        container_info = {
                            "name": container.name,
                            "image": container.image,
                            "ready": container_status.ready if container_status else False,
                            "restart_count": container_status.restart_count if container_status else 0,
                            "state": str(container_status.state) if container_status else "Unknown"
                        }
                        resource_info["details"]["containers"].append(container_info)
                
                except ApiException as e:
                    if e.status == 404:
                        resource_info["details"] = {"error": f"Pod '{name}' not found in namespace '{namespace}'"}
                    else:
                        resource_info["details"] = {"error": f"API error: {e.reason}"}
            
            elif normalized_kind == "service":
                try:
                    svc = core_api.read_namespaced_service(name=name, namespace=namespace)
                    resource_info["details"] = {
                        "metadata": {
                            "name": svc.metadata.name,
                            "namespace": svc.metadata.namespace,
                            "creation_timestamp": str(svc.metadata.creation_timestamp),
                            "labels": svc.metadata.labels
                        },
                        "spec": {
                            "type": svc.spec.type,
                            "cluster_ip": svc.spec.cluster_ip,
                            "external_ips": svc.spec.external_i_ps,
                            "ports": [{"port": port.port, "target_port": port.target_port, "protocol": port.protocol} for port in svc.spec.ports] if svc.spec.ports else []
                        },
                        "status": {
                            "load_balancer": svc.status.load_balancer.ingress[0].ip if svc.status.load_balancer.ingress else None
                        }
                    }
                
                except ApiException as e:
                    if e.status == 404:
                        resource_info["details"] = {"error": f"Service '{name}' not found in namespace '{namespace}'"}
                    else:
                        resource_info["details"] = {"error": f"API error: {e.reason}"}
            
            elif normalized_kind == "deployment":
                try:
                    deploy = apps_api.read_namespaced_deployment(name=name, namespace=namespace)
                    resource_info["details"] = {
                        "metadata": {
                            "name": deploy.metadata.name,
                            "namespace": deploy.metadata.namespace,
                            "creation_timestamp": str(deploy.metadata.creation_timestamp),
                            "labels": deploy.metadata.labels
                        },
                        "spec": {
                            "replicas": deploy.spec.replicas,
                            "strategy": deploy.spec.strategy.type if deploy.spec.strategy else None,
                            "selector": deploy.spec.selector.match_labels
                        },
                        "status": {
                            "ready_replicas": deploy.status.ready_replicas,
                            "updated_replicas": deploy.status.updated_replicas,
                            "available_replicas": deploy.status.available_replicas,
                            "unavailable_replicas": deploy.status.unavailable_replicas
                        }
                    }
                
                except ApiException as e:
                    if e.status == 404:
                        resource_info["details"] = {"error": f"Deployment '{name}' not found in namespace '{namespace}'"}
                    else:
                        resource_info["details"] = {"error": f"API error: {e.reason}"}
            
            else:
                resource_info["details"] = {"error": f"Unsupported resource kind: {kind}. Supported kinds: pod/pods, service/services/svc, deployment/deployments/deploy"}
            
            return resource_info
            
        except Exception as e:
            logger.error(f"Failed to describe resource: {e}", exc_info=True)
            return {"error": f"Failed to describe resource: {str(e)}"}

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        kind = params.get("kind", "pod")
        name = params.get("name", "unknown")
        namespace = params.get("namespace", "default")
        return f"kubernetes_describe_resource(instance_name={instance_name}, kind={kind}, name={name}, namespace={namespace})"


# ============================================
# PHASE 2: LOGS AND EVENTS TOOLS
# ============================================

class KubernetesLogsTool(Tool):
    """Tool to fetch Kubernetes pod logs with intelligent container detection"""
    
    name: str = "kubernetes_logs"
    description: str = """Fetch logs from Kubernetes pods with intelligent container handling. 
    Supports fetching logs from all containers when 'all containers' is mentioned in prompts,
    or can extract specific container names from natural language requests."""
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "pod_name": ToolParameter(
            description="Name of the pod to get logs from",
            type="string",
            required=True
        ),
        "namespace": ToolParameter(
            description="Namespace of the pod",
            type="string",
            required=False
        ),
        "container": ToolParameter(
            description="Container name (for multi-container pods). Leave empty to auto-detect from user prompt",
            type="string",
            required=False
        ),
        "previous": ToolParameter(
            description="Get logs from previous pod instance",
            type="boolean",
            required=False
        ),
        "tail": ToolParameter(
            description="Number of lines to show from the end",
            type="integer",
            required=False
        ),
        "since": ToolParameter(
            description="Show logs since timestamp (e.g., 1h, 2m, 2023-01-01T00:00:00Z)",
            type="string",
            required=False
        ),
        "user_prompt": ToolParameter(
            description="Original user prompt for intelligent container detection",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_logs",
            description="""Fetch logs from Kubernetes pods with intelligent container handling. 
            Supports fetching logs from all containers when 'all containers' is mentioned in prompts,
            or can extract specific container names from natural language requests.""",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "pod_name": ToolParameter(
                    description="Name of the pod to get logs from",
                    type="string",
                    required=True
                ),
                "namespace": ToolParameter(
                    description="Namespace of the pod",
                    type="string",
                    required=False
                ),
                "container": ToolParameter(
                    description="Container name (for multi-container pods). Leave empty to auto-detect from user prompt",
                    type="string",
                    required=False
                ),
                "previous": ToolParameter(
                    description="Get logs from previous pod instance",
                    type="boolean",
                    required=False
                ),
                "tail": ToolParameter(
                    description="Number of lines to show from the end",
                    type="integer",
                    required=False
                ),
                "since": ToolParameter(
                    description="Show logs since timestamp (e.g., 1h, 2m, 2023-01-01T00:00:00Z)",
                    type="string",
                    required=False
                ),
                "user_prompt": ToolParameter(
                    description="Original user prompt for intelligent container detection",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Fetch Kubernetes pod logs"""
        try:
            instance_name = params.get("instance_name")
            pod_name = params.get("pod_name")
            namespace = params.get("namespace", "default")
            container = params.get("container")
            previous = params.get("previous", False)
            tail = params.get("tail")
            since = params.get("since")

            user_prompt = params.get("user_prompt", "")

            if not instance_name or not pod_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name and pod name are required",
                    params=params
                )

            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Fetch logs with enhanced container intelligence
            logs_data = self._fetch_logs_enhanced(instance, pod_name, namespace, container, previous, tail, since, user_prompt)
            
            # Parse logs_data to check if it's from multiple containers
            if isinstance(logs_data, dict) and 'all_containers' in logs_data:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        'instance_name': instance_name,
                        'pod_name': pod_name,
                        'namespace': namespace,
                        'container': container,
                        'previous': previous,
                        'tail': tail,
                        'since': since,
                        'user_prompt': user_prompt,
                        'all_containers_checked': True,
                        'container_count': logs_data.get('container_count', 0),
                        'logs': logs_data['logs']
                    },
                    params=params
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        'instance_name': instance_name,
                        'pod_name': pod_name,
                        'namespace': namespace,
                        'container': container,
                        'previous': previous,
                        'tail': tail,
                        'since': since,
                        'user_prompt': user_prompt,
                        'all_containers_checked': False,
                        'logs': logs_data
                    },
                    params=params
                )
            
        except Exception as e:
            logger.error(f"Failed to fetch Kubernetes logs: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to fetch Kubernetes logs: {str(e)}",
                params=params
            )

    def _fetch_logs(self, instance: ServiceInstance, pod_name: str, namespace: str, container: Optional[str], previous: bool, tail: Optional[int], since: Optional[str]) -> str:
        """Fetch logs using Kubernetes Python client"""
        try:
            logger.info(f"🔍 Starting to fetch logs for pod={pod_name}, namespace={namespace}, container={container}, previous={previous}")
            
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            
            # First check if the pod exists and get its status
            try:
                pod_info = core_api.read_namespaced_pod(name=pod_name, namespace=namespace)
                logger.info(f"🔍 Pod status: {pod_info.status.phase}")
                
                # Log container statuses for debugging, but don't block log retrieval
                # Even crashed/not-ready containers have logs that are crucial for troubleshooting
                if pod_info.status.container_statuses:
                    for cs in pod_info.status.container_statuses:
                        logger.info(f"🔍 Container '{cs.name}': ready={cs.ready}, state={cs.state}")
                
            except ApiException as pod_e:
                if pod_e.status == 404:
                    return f"Pod '{pod_name}' not found in namespace '{namespace}'"
                elif pod_e.status == 403:
                    return f"Access to pod '{pod_name}' in namespace '{namespace}' is forbidden. Check permissions."
                else:
                    logger.warning(f"🔍 Could not check pod status: {pod_e.status} - {pod_e.reason}")
            
            # Build API parameters
            kwargs = {}
            
            if container:
                kwargs['container'] = container
            
            if previous:
                kwargs['previous'] = True
            
            if tail:
                kwargs['tail_lines'] = tail
            
            if since:
                since_seconds = self._parse_since_seconds(since)
                if since_seconds:
                    kwargs['since_seconds'] = since_seconds
            
            logger.info(f"🔍 API parameters: {kwargs}")
            
            # Execute API call
            try:
                result = core_api.read_namespaced_pod_log(
                    name=pod_name, 
                    namespace=namespace, 
                    **kwargs
                )
                
                logger.info(f"🔍 Successfully retrieved logs (length: {len(result) if result else 0})")
                return result if result else "No logs available"
                
            except ApiException as log_e:
                if log_e.status == 400 and previous:
                    logger.warning(f"🔍 Previous logs not available, trying current logs")
                    # Remove previous parameter and try again
                    kwargs.pop('previous', None)
                    logger.info(f"🔍 Retrying with API parameters: {kwargs}")
                    
                    try:
                        result = core_api.read_namespaced_pod_log(
                            name=pod_name, 
                            namespace=namespace, 
                            **kwargs
                        )
                        
                        logger.info(f"🔍 Successfully retrieved current logs (length: {len(result) if result else 0})")
                        return f"Previous logs not available. Current logs:\n\n{result if result else 'No logs available'}"
                        
                    except ApiException as retry_e:
                        logger.error(f"🔍 API Exception in retry: {retry_e.status} - {retry_e.reason}")
                        logger.error(f"🔍 Full error details: {retry_e.body if hasattr(retry_e, 'body') else 'No body'}")
                        
                        if retry_e.status == 404:
                            return f"Pod '{pod_name}' not found in namespace '{namespace}'"
                        elif retry_e.status == 403:
                            return f"Access to logs for pod '{pod_name}' in namespace '{namespace}' is forbidden. Check permissions."
                        elif retry_e.status == 410:
                            return f"Pod '{pod_name}' in namespace '{namespace}' is gone. It might have been deleted."
                        elif retry_e.status == 400:
                            # Try to get more specific error information
                            error_msg = f"Bad request for pod '{pod_name}' in namespace '{namespace}'. "
                            if hasattr(retry_e, 'body') and retry_e.body:
                                try:
                                    error_body = json.loads(retry_e.body)
                                    if 'message' in error_body:
                                        error_msg += f"API Error: {error_body['message']}"
                                    else:
                                        error_msg += f"API Error: {retry_e.body}"
                                except:
                                    error_msg += f"API Error: {retry_e.body}"
                            else:
                                error_msg += "This might be due to the pod not being ready for logs or container issues."
                            return error_msg
                        else:
                            return f"API error fetching logs: {retry_e.reason}"
                else:
                    raise log_e
            
        except ApiException as e:
            logger.error(f"🔍 API Exception in logs: {e.status} - {e.reason}")
            logger.error(f"🔍 Full error details: {e.body if hasattr(e, 'body') else 'No body'}")
            
            if e.status == 404:
                return f"Pod '{pod_name}' not found in namespace '{namespace}'"
            elif e.status == 403: # Forbidden
                return f"Access to logs for pod '{pod_name}' in namespace '{namespace}' is forbidden. Check permissions."
            elif e.status == 410: # Gone
                return f"Pod '{pod_name}' in namespace '{namespace}' is gone. It might have been deleted."
            elif e.status == 400: # Bad Request
                # Try to get more specific error information
                error_msg = f"Bad request for pod '{pod_name}' in namespace '{namespace}'. "
                if hasattr(e, 'body') and e.body:
                    try:
                        error_body = json.loads(e.body)
                        if 'message' in error_body:
                            error_msg += f"API Error: {error_body['message']}"
                        else:
                            error_msg += f"API Error: {e.body}"
                    except:
                        error_msg += f"API Error: {e.body}"
                else:
                    error_msg += "This might be due to invalid parameters or the pod not being ready."
                return error_msg
            else:
                return f"API error fetching logs: {e.reason}"
        except Exception as e:
            logger.error(f"🔍 Failed to fetch logs: {e}", exc_info=True)
            return f"Failed to fetch logs: {str(e)}"

    def _fetch_logs_enhanced(self, instance: ServiceInstance, pod_name: str, namespace: str, container: Optional[str], previous: bool, tail: Optional[int], since: Optional[str], user_prompt: str) -> Any:
        """Enhanced fetch logs with intelligent container handling"""
        try:
            logger.info(f"🔍 Enhanced log fetching for pod={pod_name}, namespace={namespace}, container={container}, user_prompt='{user_prompt[:100]}...'")
            
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            
            # Check if user wants all containers
            check_all = EnhancedContainerHandler.should_check_all_containers(user_prompt)
            
            # If no container specified but user wants all containers
            if container is None and check_all:
                logger.info("🔍 User requested all containers - fetching from all containers in pod")
                
                # Build kwargs for log fetching
                kwargs = {}
                if previous:
                    kwargs['previous'] = True
                if tail:
                    kwargs['tail_lines'] = tail
                if since:
                    since_seconds = self._parse_since_seconds(since)
                    if since_seconds:
                        kwargs['since_seconds'] = since_seconds
                
                # Fetch logs from all containers
                all_logs = EnhancedContainerHandler.fetch_logs_all_containers(
                    core_api, pod_name, namespace, **kwargs
                )
                
                # Format the result
                result = f"=== LOGS FROM ALL CONTAINERS IN POD '{pod_name}' ===\n\n"
                for container_name, log_data in all_logs.items():
                    result += f"🔶 CONTAINER: {container_name}\n"
                    result += f"   Image: {log_data['container_info']['image']}\n"
                    result += f"   Ready: {log_data['container_info']['ready']}\n"
                    result += f"   Restart Count: {log_data['container_info']['restart_count']}\n"
                    result += f"   State: {log_data['container_info']['state']}\n"
                    result += f"--- LOGS ---\n{log_data['logs']}\n"
                    result += f"{'='*80}\n\n"
                
                # Return structured data for multi-container logs
                return {
                    'all_containers': True,
                    'container_count': len(all_logs),
                    'logs': result
                }
                
            # If no container specified, try to extract from prompt
            elif container is None:
                extracted_container = EnhancedContainerHandler.extract_container_name(user_prompt)
                if extracted_container:
                    logger.info(f"🔍 Extracted container name from prompt: {extracted_container}")
                    container = extracted_container
            
            # If still no container specified, check if pod has multiple containers
            if container is None:
                try:
                    pod_containers = EnhancedContainerHandler.get_pod_containers(core_api, pod_name, namespace)
                    # get_pod_containers already returns only regular containers (not init containers)
                    
                    if len(pod_containers) > 1:
                        logger.info(f"🔍 Pod has {len(pod_containers)} containers and no container specified - fetching from all containers")
                        
                        # Build kwargs for log fetching
                        kwargs = {}
                        if previous:
                            kwargs['previous'] = True
                        if tail:
                            kwargs['tail_lines'] = tail
                        if since:
                            since_seconds = self._parse_since_seconds(since)
                            if since_seconds:
                                kwargs['since_seconds'] = since_seconds
                        
                        # Fetch logs from all containers
                        all_logs = EnhancedContainerHandler.fetch_logs_all_containers(
                            core_api, pod_name, namespace, **kwargs
                        )
                        
                        # Format the result
                        result = f"=== LOGS FROM ALL CONTAINERS IN POD '{pod_name}' ===\n\n"
                        for container_name, log_data in all_logs.items():
                            result += f"🔶 CONTAINER: {container_name}\n"
                            result += f"   Image: {log_data['container_info']['image']}\n"
                            result += f"   Ready: {log_data['container_info']['ready']}\n"
                            result += f"   Restart Count: {log_data['container_info']['restart_count']}\n"
                            result += f"   State: {log_data['container_info']['state']}\n"
                            result += f"--- LOGS ---\n{log_data['logs']}\n"
                            result += f"{'='*80}\n\n"
                        
                        # Return structured data for multi-container logs
                        return {
                            'all_containers': True,
                            'container_count': len(all_logs),
                            'logs': result
                        }
                    elif len(pod_containers) == 1:
                        # Single container pod - use that container
                        container = pod_containers[0]['name']
                        logger.info(f"🔍 Pod has single container '{container}' - using it automatically")
                    else:
                        logger.warning(f"🔍 Pod has no containers found")
                        
                except Exception as e:
                    logger.warning(f"🔍 Could not determine pod containers: {e}")
            
            # Use original single container logic
            return self._fetch_logs(instance, pod_name, namespace, container, previous, tail, since)
            
        except Exception as e:
            logger.error(f"Enhanced log fetching failed: {e}", exc_info=True)
            return f"Error fetching logs: {str(e)}"

    def _parse_since_seconds(self, since_str: Optional[str]) -> Optional[int]:
        """Parse 'since' parameter into seconds"""
        if not since_str:
            return None
        try:
            if since_str.endswith('s'):
                return int(since_str[:-1])
            elif since_str.endswith('m'):
                return int(since_str[:-1]) * 60
            elif since_str.endswith('h'):
                return int(since_str[:-1]) * 3600
            elif re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', since_str): # ISO 8601 timestamp
                return int((datetime.now() - datetime.fromisoformat(since_str)).total_seconds())
            else:
                return None # Unsupported format
        except ValueError:
            return None # Invalid number

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        pod_name = params.get("pod_name", "unknown")
        namespace = params.get("namespace", "default")
        container = params.get("container")
        user_prompt = params.get("user_prompt", "")
        
        if container:
            return f"kubernetes_logs(instance_name={instance_name}, pod_name={pod_name}, namespace={namespace}, container={container})"
        elif user_prompt:
            return f"kubernetes_logs(instance_name={instance_name}, pod_name={pod_name}, namespace={namespace}, user_prompt='{user_prompt[:50]}...')"
        else:
            return f"kubernetes_logs(instance_name={instance_name}, pod_name={pod_name}, namespace={namespace})"


class KubernetesEventsTool(Tool):
    """Tool to fetch Kubernetes events"""
    
    name: str = "kubernetes_events"
    description: str = "Fetch Kubernetes events for resources or namespaces"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "resource_type": ToolParameter(
            description="Resource type (e.g., pod, service, deployment)",
            type="string",
            required=False
        ),
        "resource_name": ToolParameter(
            description="Resource name",
            type="string",
            required=False
        ),
        "namespace": ToolParameter(
            description="Namespace to get events from",
            type="string",
            required=False
        ),
        "output_format": ToolParameter(
            description="Output format (wide, json, yaml)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_events",
            description="Fetch Kubernetes events for resources or namespaces",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "resource_type": ToolParameter(
                    description="Resource type (e.g., pod, service, deployment)",
                    type="string",
                    required=False
                ),
                "resource_name": ToolParameter(
                    description="Resource name",
                    type="string",
                    required=False
                ),
                "namespace": ToolParameter(
                    description="Namespace to get events from",
                    type="string",
                    required=False
                ),
                "output_format": ToolParameter(
                    description="Output format (wide, json, yaml)",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Fetch Kubernetes events"""
        try:
            instance_name = params.get("instance_name")
            resource_type = params.get("resource_type")
            resource_name = params.get("resource_name")
            namespace = params.get("namespace")
            output_format = params.get("output_format", "wide")

            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name is required",
                    params=params
                )

            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Fetch events
            events_data = self._fetch_events(instance, resource_type, resource_name, namespace, output_format)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'resource_type': resource_type,
                    'resource_name': resource_name,
                    'namespace': namespace,
                    'output_format': output_format,
                    'events': events_data
                },
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch Kubernetes events: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to fetch Kubernetes events: {str(e)}",
                params=params
            )

    def _fetch_events(self, instance: ServiceInstance, resource_type: Optional[str], resource_name: Optional[str], namespace: Optional[str], output_format: str) -> str:
        """Fetch events using Kubernetes Python client"""
        try:
            logger.info(f"🔍 Starting to fetch events for resource_type={resource_type}, resource_name={resource_name}, namespace={namespace}")
            
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            
            logger.info(f"🔍 Created Kubernetes client, fetching events...")
            
            # Use CoreV1Api for proper authentication handling
            if namespace:
                event_list = core_api.list_namespaced_event(namespace=namespace, watch=False)
            else:
                event_list = core_api.list_event_for_all_namespaces(watch=False)
            
            logger.info(f"🔍 Retrieved {len(event_list.items)} events from API")
            
            # Convert event objects to our format
            raw_events = []
            for event in event_list.items:
                raw_events.append({
                    'type': event.type,
                    'reason': event.reason,
                    'message': event.message,
                    'count': event.count if event.count else 1,
                    'firstTimestamp': event.first_timestamp.isoformat() if event.first_timestamp else 'Unknown',
                    'lastTimestamp': event.last_timestamp.isoformat() if event.last_timestamp else 'Unknown',
                    'involvedObject': {
                        'kind': event.involved_object.kind,
                        'name': event.involved_object.name,
                        'namespace': event.involved_object.namespace
                    }
                })
            
            # Convert raw events to our format
            events_list = []
            for i, raw_event in enumerate(raw_events):
                try:
                    logger.debug(f"🔍 Processing raw event {i+1}/{len(raw_events)}")
                    event_info = {
                        "type": raw_event.get('type', 'Unknown'),
                        "reason": raw_event.get('reason', 'Unknown'),
                        "message": raw_event.get('message', 'No message'),
                        "count": raw_event.get('count', 0),
                        "first_timestamp": raw_event.get('firstTimestamp', 'Unknown'),
                        "last_timestamp": raw_event.get('lastTimestamp', 'Unknown'),
                        "involved_object": raw_event.get('involvedObject', {})
                    }
                    events_list.append(event_info)
                except Exception as event_error:
                    logger.warning(f"🔍 Failed to process raw event {i+1}: {event_error}")
                    events_list.append({
                        "type": "Unknown",
                        "reason": "EventProcessingError",
                        "message": f"Failed to process event: {str(event_error)}",
                        "count": 1,
                        "first_timestamp": "Unknown",
                        "last_timestamp": "Unknown",
                        "involved_object": None
                    })
            
            logger.info(f"🔍 Successfully processed {len(events_list)} events")
            
            # Filter events if resource_type and resource_name are specified
            if resource_type and resource_name:
                filtered_events = []
                for event in events_list:
                    involved_obj = event.get("involved_object", {})
                    if (involved_obj and 
                        involved_obj.get("kind", "").lower() == resource_type.lower() and
                        involved_obj.get("name", "") == resource_name):
                        filtered_events.append(event)
                events_list = filtered_events
                logger.info(f"🔍 Filtered to {len(events_list)} events for {resource_type}/{resource_name}")
            
            # Format output
            if output_format == 'json':
                return json.dumps(events_list, indent=2)
            elif output_format == 'yaml':
                return yaml.dump(events_list, default_flow_style=False)
            else:
                # Format as readable text
                formatted_events = []
                for event in events_list:
                    involved_obj = event.get("involved_object", {})
                    obj_info = f"{involved_obj.get('kind', 'Unknown')}/{involved_obj.get('name', 'Unknown')}" if involved_obj else "Unknown"
                    formatted_events.append(
                        f"Type: {event['type']}, Reason: {event['reason']}, "
                        f"Object: {obj_info}, "
                        f"Message: {event['message']}, Count: {event['count']}, "
                        f"First: {event['first_timestamp']}, Last: {event['last_timestamp']}"
                    )
                return "\n".join(formatted_events) if formatted_events else "No events found"
            
        except ApiException as e:
            logger.error(f"🔍 API Exception in events: {e.status} - {e.reason}")
            if e.status == 404:
                return f"Resource type '{resource_type}' or name '{resource_name}' not found in namespace '{namespace}'"
            elif e.status == 403: # Forbidden
                return f"Access to events for resource '{resource_type}/{resource_name}' in namespace '{namespace}' is forbidden. Check permissions."
            elif e.status == 410: # Gone
                return f"Resource '{resource_type}/{resource_name}' in namespace '{namespace}' is gone. It might have been deleted."
            else:
                return f"API error fetching events: {e.reason}"
        except Exception as e:
            logger.error(f"🔍 Failed to fetch events: {e}", exc_info=True)
            return f"Failed to fetch events: {str(e)}"

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        resource_type = params.get("resource_type", "all")
        namespace = params.get("namespace", "all")
        return f"kubernetes_events(instance_name={instance_name}, resource_type={resource_type}, namespace={namespace})"


class KubernetesLogsSearchTool(Tool):
    """Tool to search logs for specific patterns with intelligent container detection"""
    
    name: str = "kubernetes_logs_search"
    description: str = """Search Kubernetes pod logs for specific patterns or terms with intelligent container handling.
    Supports searching across all containers when 'all containers' is mentioned in prompts,
    or can extract specific container names from natural language requests."""
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "pod_name": ToolParameter(
            description="Name of the pod to search logs from",
            type="string",
            required=True
        ),
        "namespace": ToolParameter(
            description="Namespace of the pod",
            type="string",
            required=False
        ),
        "search_term": ToolParameter(
            description="Search term or pattern to look for",
            type="string",
            required=True
        ),
        "container": ToolParameter(
            description="Container name (for multi-container pods). Leave empty to auto-detect from user prompt",
            type="string",
            required=False
        ),
        "case_sensitive": ToolParameter(
            description="Case sensitive search",
            type="boolean",
            required=False
        ),
        "invert_match": ToolParameter(
            description="Invert match (show lines that don't match)",
            type="boolean",
            required=False
        ),
        "user_prompt": ToolParameter(
            description="Original user prompt for intelligent container detection",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_logs_search",
            description="""Search Kubernetes pod logs for specific patterns or terms with intelligent container handling.
            Supports searching across all containers when 'all containers' is mentioned in prompts,
            or can extract specific container names from natural language requests.""",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "pod_name": ToolParameter(
                    description="Name of the pod to search logs from",
                    type="string",
                    required=True
                ),
                "namespace": ToolParameter(
                    description="Namespace of the pod",
                    type="string",
                    required=False
                ),
                "search_term": ToolParameter(
                    description="Search term or pattern to look for",
                    type="string",
                    required=True
                ),
                "container": ToolParameter(
                    description="Container name (for multi-container pods). Leave empty to auto-detect from user prompt",
                    type="string",
                    required=False
                ),
                "case_sensitive": ToolParameter(
                    description="Case sensitive search",
                    type="boolean",
                    required=False
                ),
                "invert_match": ToolParameter(
                    description="Invert match (show lines that don't match)",
                    type="boolean",
                    required=False
                ),
                "user_prompt": ToolParameter(
                    description="Original user prompt for intelligent container detection",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Search Kubernetes pod logs"""
        try:
            instance_name = params.get("instance_name")
            pod_name = params.get("pod_name")
            namespace = params.get("namespace", "default")
            search_term = params.get("search_term")
            container = params.get("container")
            case_sensitive = params.get("case_sensitive", False)
            invert_match = params.get("invert_match", False)
            user_prompt = params.get("user_prompt", "")

            if not instance_name or not pod_name or not search_term:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name, pod name, and search term are required",
                    params=params
                )

            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Fetch logs with enhanced container intelligence and apply search filter
            logs_result = self._fetch_logs_for_search_enhanced(instance, pod_name, namespace, container, user_prompt)
            filtered_logs = self._filter_logs(logs_result, search_term, case_sensitive, invert_match)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'pod_name': pod_name,
                    'namespace': namespace,
                    'container': container,
                    'search_term': search_term,
                    'case_sensitive': case_sensitive,
                    'invert_match': invert_match,
                    'user_prompt': user_prompt,
                    'filtered_logs': filtered_logs,
                    'total_lines': len(logs_result.splitlines()),
                    'matching_lines': len(filtered_logs.splitlines())
                },
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to search Kubernetes logs: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to search Kubernetes logs: {str(e)}",
                params=params
            )

    def _fetch_logs_for_search(self, instance: ServiceInstance, pod_name: str, namespace: str, container: Optional[str]) -> str:
        """Fetch logs for search using Kubernetes Python client"""
        try:
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            
            # Build kubectl command arguments for logs
            cmd_args = ['logs', pod_name, '-n', namespace]
            
            if container:
                cmd_args.extend(['-c', container])

            # Execute command
            result = core_api.read_namespaced_pod_log(name=pod_name, namespace=namespace, **{'follow': False})
            
            return result
            
        except ApiException as e:
            if e.status == 404:
                return f"Pod '{pod_name}' not found in namespace '{namespace}'"
            elif e.status == 403: # Forbidden
                return f"Access to logs for pod '{pod_name}' in namespace '{namespace}' is forbidden. Check permissions."
            elif e.status == 410: # Gone
                return f"Pod '{pod_name}' in namespace '{namespace}' is gone. It might have been deleted."
            else:
                return f"API error fetching logs for search: {e.reason}"
        except Exception as e:
            logger.error(f"Failed to fetch logs for search: {e}", exc_info=True)
            return f"Failed to fetch logs for search: {str(e)}"

    def _fetch_logs_for_search_enhanced(self, instance: ServiceInstance, pod_name: str, namespace: str, container: Optional[str], user_prompt: str) -> str:
        """Enhanced fetch logs for search with intelligent container handling"""
        try:
            logger.info(f"🔍 Enhanced log search for pod={pod_name}, namespace={namespace}, container={container}, user_prompt='{user_prompt[:100]}...'")
            
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            
            # Check if user wants all containers
            check_all = EnhancedContainerHandler.should_check_all_containers(user_prompt)
            
            # If no container specified but user wants all containers
            if container is None and check_all:
                logger.info("🔍 User requested all containers for search - fetching from all containers in pod")
                
                # Fetch logs from all containers without specific parameters (for search)
                all_logs = EnhancedContainerHandler.fetch_logs_all_containers(
                    core_api, pod_name, namespace, follow=False
                )
                
                # Combine all logs into one searchable string
                combined_logs = f"=== COMBINED LOGS FOR SEARCH FROM ALL CONTAINERS IN POD '{pod_name}' ===\n\n"
                for container_name, log_data in all_logs.items():
                    combined_logs += f"🔶 CONTAINER: {container_name}\n"
                    combined_logs += f"--- LOGS ---\n{log_data['logs']}\n"
                    combined_logs += f"{'='*80}\n\n"
                
                return combined_logs
                
            # If no container specified, try to extract from prompt
            elif container is None:
                extracted_container = EnhancedContainerHandler.extract_container_name(user_prompt)
                if extracted_container:
                    logger.info(f"🔍 Extracted container name from prompt for search: {extracted_container}")
                    container = extracted_container
            
            # Use original single container logic
            return self._fetch_logs_for_search(instance, pod_name, namespace, container)
            
        except Exception as e:
            logger.error(f"Enhanced log search failed: {e}", exc_info=True)
            return f"Error fetching logs for search: {str(e)}"

    def _filter_logs(self, logs: str, search_term: str, case_sensitive: bool, invert_match: bool) -> str:
        """Filter logs using search term"""
        
        lines = logs.splitlines()
        filtered_lines = []
        
        # Build regex pattern
        if case_sensitive:
            pattern = re.compile(re.escape(search_term))
        else:
            pattern = re.compile(re.escape(search_term), re.IGNORECASE)
        
        for line in lines:
            match = pattern.search(line)
            if (match and not invert_match) or (not match and invert_match):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        pod_name = params.get("pod_name", "unknown")
        search_term = params.get("search_term", "unknown")
        container = params.get("container")
        user_prompt = params.get("user_prompt", "")
        
        if container:
            return f"kubernetes_logs_search(instance_name={instance_name}, pod_name={pod_name}, search_term={search_term}, container={container})"
        elif user_prompt:
            return f"kubernetes_logs_search(instance_name={instance_name}, pod_name={pod_name}, search_term={search_term}, user_prompt='{user_prompt[:50]}...')"
        else:
            return f"kubernetes_logs_search(instance_name={instance_name}, pod_name={pod_name}, search_term={search_term})"


# ============================================
# PHASE 3: ADVANCED ANALYSIS TOOLS
# ============================================

class KubernetesMetricsTool(Tool):
    """Tool to fetch Kubernetes resource metrics"""
    
    name: str = "kubernetes_metrics"
    description: str = "Fetch real-time CPU and memory metrics for pods and nodes"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "resource_type": ToolParameter(
            description="Resource type (pods, nodes)",
            type="string",
            required=True
        ),
        "namespace": ToolParameter(
            description="Namespace (for pods only)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_metrics",
            description="Fetch real-time CPU and memory metrics for pods and nodes",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "resource_type": ToolParameter(
                    description="Resource type (pods, nodes)",
                    type="string",
                    required=True
                ),
                "namespace": ToolParameter(
                    description="Namespace (for pods only)",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Fetch Kubernetes resource metrics"""
        try:
            instance_name = params.get("instance_name")
            resource_type = params.get("resource_type")
            namespace = params.get("namespace")

            if not instance_name or not resource_type:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name and resource type are required",
                    params=params
                )

            if resource_type not in ['pods', 'nodes']:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Resource type must be 'pods' or 'nodes'",
                    params=params
                )

            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Fetch metrics
            metrics_data = self._fetch_metrics(instance, resource_type, namespace)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'resource_type': resource_type,
                    'namespace': namespace,
                    'metrics': metrics_data
                },
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch Kubernetes metrics: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to fetch Kubernetes metrics: {str(e)}",
                params=params
            )

    def _fetch_metrics(self, instance: ServiceInstance, resource_type: str, namespace: Optional[str]) -> str:
        """Fetch metrics using Kubernetes Python client"""
        try:
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            apps_api = client.AppsV1Api(k8s_client)
            
            cmd_args = ['top', resource_type]
            
            if resource_type == 'pods' and namespace:
                cmd_args.extend(['-n', namespace])
            elif resource_type == 'pods':
                cmd_args.append('-A')

            # Execute command
            if resource_type == 'pods':
                if namespace:
                    result = core_api.list_namespaced_pod(namespace=namespace, watch=False)
                else:
                    result = core_api.list_pod_for_all_namespaces(watch=False)
                
                # Convert to string representation
                pods_list = []
                for pod in result.items:
                    pod_info = {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "status": pod.status.phase,
                        "ready": f"{len([cs for cs in pod.status.container_statuses if cs.ready])}/{len(pod.spec.containers)}" if pod.status.container_statuses else "0/0",
                        "restarts": sum(cs.restart_count for cs in pod.status.container_statuses) if pod.status.container_statuses else 0,
                        "age": str(pod.metadata.creation_timestamp) if pod.metadata.creation_timestamp else "Unknown"
                    }
                    pods_list.append(pod_info)
                
                return str(pods_list)
            elif resource_type == 'nodes':
                result = core_api.list_node(watch=False)
                
                # Convert to string representation
                nodes_list = []
                for node in result.items:
                    node_info = {
                        "name": node.metadata.name,
                        "status": next((cond.status for cond in node.status.conditions if cond.type == "Ready"), "Unknown"),
                        "age": str(node.metadata.creation_timestamp) if node.metadata.creation_timestamp else "Unknown"
                    }
                    nodes_list.append(node_info)
                
                return str(nodes_list)
            else:
                return f"Unsupported resource type: {resource_type}. Supported types: pods, nodes"
            
        except ApiException as e:
            if e.status == 404:
                return f"Resource type '{resource_type}' not found"
            elif e.status == 403: # Forbidden
                return f"Access to metrics for resource type '{resource_type}' in namespace '{namespace}' is forbidden. Check permissions."
            elif e.status == 410: # Gone
                return f"Resource type '{resource_type}' in namespace '{namespace}' is gone. It might have been deleted."
            else:
                return f"API error fetching metrics: {e.reason}"
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {e}", exc_info=True)
            return f"Failed to fetch metrics: {str(e)}"

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        resource_type = params.get("resource_type", "unknown")
        return f"kubernetes_metrics(instance_name={instance_name}, resource_type={resource_type})"


class KubernetesTroubleshootingTool(Tool):
    """Tool for advanced Kubernetes troubleshooting"""
    
    name: str = "kubernetes_troubleshoot"
    description: str = "Advanced troubleshooting for Kubernetes resources including status analysis and debugging"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "resource_type": ToolParameter(
            description="Resource type (pod, deployment, service, etc.)",
            type="string",
            required=True
        ),
        "resource_name": ToolParameter(
            description="Resource name",
            type="string",
            required=True
        ),
        "namespace": ToolParameter(
            description="Namespace",
            type="string",
            required=False
        ),
        "troubleshooting_type": ToolParameter(
            description="Type of troubleshooting (status, readiness, liveness, network, storage)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_troubleshoot",
            description="Advanced troubleshooting for Kubernetes resources including status analysis and debugging",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "resource_type": ToolParameter(
                    description="Resource type (pod, deployment, service, etc.)",
                    type="string",
                    required=True
                ),
                "resource_name": ToolParameter(
                    description="Resource name",
                    type="string",
                    required=True
                ),
                "namespace": ToolParameter(
                    description="Namespace",
                    type="string",
                    required=False
                ),
                "troubleshooting_type": ToolParameter(
                    description="Type of troubleshooting (status, readiness, liveness, network, storage)",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Perform specific type of troubleshooting"""
        try:
            instance_name = params.get("instance_name")
            resource_type = params.get("resource_type")
            resource_name = params.get("resource_name")
            namespace = params.get("namespace", "default")
            troubleshooting_type = params.get("troubleshooting_type", "status")

            if not instance_name or not resource_type or not resource_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name, resource type, and resource name are required",
                    params=params
                )

            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Perform troubleshooting based on type
            troubleshooting_data = self._perform_troubleshooting(instance, resource_type, resource_name, namespace, troubleshooting_type)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=troubleshooting_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to perform Kubernetes troubleshooting: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to perform Kubernetes troubleshooting: {str(e)}",
                params=params
            )

    def _perform_troubleshooting(self, instance: ServiceInstance, resource_type: str, 
                                resource_name: str, namespace: str, troubleshooting_type: str) -> Dict[str, Any]:
        """Perform specific type of troubleshooting"""
        troubleshooting_data = {
            'instance_name': instance.name,
            'resource_type': resource_type,
            'resource_name': resource_name,
            'namespace': namespace,
            'troubleshooting_type': troubleshooting_type,
            'results': {}
        }

        if troubleshooting_type == 'status':
            # Get detailed status information using Kubernetes Python client
            try:
                k8s_client = self._create_kubernetes_client(instance)
                core_api = client.CoreV1Api(k8s_client)
                apps_api = client.AppsV1Api(k8s_client)
                
                if resource_type == 'pod':
                    resource = core_api.read_namespaced_pod(name=resource_name, namespace=namespace)
                elif resource_type == 'service':
                    resource = core_api.read_namespaced_service(name=resource_name, namespace=namespace)
                elif resource_type == 'deployment':
                    resource = apps_api.read_namespaced_deployment(name=resource_name, namespace=namespace)
                else:
                    troubleshooting_data['results']['describe'] = f"Unsupported resource type: {resource_type}"
                    return troubleshooting_data
                
                troubleshooting_data['results']['describe'] = str(resource)
                troubleshooting_data['results']['get_yaml'] = str(resource)
                
            except ApiException as e:
                troubleshooting_data['results']['describe'] = f"API error: {e.reason}"
                troubleshooting_data['results']['get_yaml'] = f"API error: {e.reason}"

        elif troubleshooting_type == 'readiness':
            # Check readiness probes
            if resource_type == 'pod':
                troubleshooting_data['results']['readiness_check'] = self._check_readiness_probes(instance, resource_name, namespace)

        elif troubleshooting_type == 'liveness':
            # Check liveness probes
            if resource_type == 'pod':
                troubleshooting_data['results']['liveness_check'] = self._check_liveness_probes(instance, resource_name, namespace)

        elif troubleshooting_type == 'network':
            # Network connectivity checks
            troubleshooting_data['results']['network_check'] = self._check_network_connectivity(instance, resource_type, resource_name, namespace)

        elif troubleshooting_type == 'storage':
            # Storage-related checks
            troubleshooting_data['results']['storage_check'] = self._check_storage_issues(instance, resource_type, resource_name, namespace)

        return troubleshooting_data

    def _check_readiness_probes(self, instance: ServiceInstance, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Check readiness probe configuration and status"""
        try:
            # Get pod details
            pod_yaml = self._run_kubectl_with_instance(instance, ['get', 'pod', pod_name, '-n', namespace, '-o', 'yaml'])
            
            # Parse YAML to check readiness probe configuration
            pod_data = yaml.safe_load(pod_yaml)
            
            readiness_info = {
                'pod_status': pod_data.get('status', {}),
                'readiness_probes': []
            }
            
            # Extract readiness probe configurations
            containers = pod_data.get('spec', {}).get('containers', [])
            for container in containers:
                container_name = container.get('name', '')
                readiness_probe = container.get('readinessProbe', {})
                if readiness_probe:
                    readiness_info['readiness_probes'].append({
                        'container': container_name,
                        'probe_config': readiness_probe
                    })
            
            return readiness_info
            
        except Exception as e:
            return {'error': f"Failed to check readiness probes: {str(e)}"}

    def _check_liveness_probes(self, instance: ServiceInstance, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Check liveness probe configuration and status"""
        try:
            # Get pod details
            pod_yaml = self._run_kubectl_with_instance(instance, ['get', 'pod', pod_name, '-n', namespace, '-o', 'yaml'])
            
            # Parse YAML to check liveness probe configuration
            pod_data = yaml.safe_load(pod_yaml)
            
            liveness_info = {
                'pod_status': pod_data.get('status', {}),
                'liveness_probes': []
            }
            
            # Extract liveness probe configurations
            containers = pod_data.get('spec', {}).get('containers', [])
            for container in containers:
                container_name = container.get('name', '')
                liveness_probe = container.get('livenessProbe', {})
                if liveness_probe:
                    liveness_info['liveness_probes'].append({
                        'container': container_name,
                        'probe_config': liveness_probe
                    })
            
            return liveness_info
            
        except Exception as e:
            return {'error': f"Failed to check liveness probes: {str(e)}"}

    def _check_network_connectivity(self, instance: ServiceInstance, resource_type: str, 
                                   resource_name: str, namespace: str) -> Dict[str, Any]:
        """Check network connectivity for resources"""
        network_info = {}
        
        try:
            # Get endpoints
            if resource_type == 'service':
                network_info['endpoints'] = self._run_kubectl_with_instance(instance, ['get', 'endpoints', resource_name, '-n', namespace, '-o', 'yaml'])
            
            # Get service details
            if resource_type == 'service':
                network_info['service_details'] = self._run_kubectl_with_instance(instance, ['get', 'service', resource_name, '-n', namespace, '-o', 'yaml'])
            
            return network_info
            
        except Exception as e:
            return {'error': f"Failed to check network connectivity: {str(e)}"}

    def _check_storage_issues(self, instance: ServiceInstance, resource_type: str, 
                             resource_name: str, namespace: str) -> Dict[str, Any]:
        """Check storage-related issues"""
        storage_info = {}
        
        try:
            # Get persistent volume claims
            if resource_type == 'pod':
                storage_info['pvc'] = self._run_kubectl_with_instance(instance, ['get', 'pvc', '-n', namespace, '-o', 'wide'])
            
            # Get persistent volumes
            storage_info['pv'] = self._run_kubectl_with_instance(instance, ['get', 'pv', '-o', 'wide'])
            
            return storage_info
            
        except Exception as e:
            return {'error': f"Failed to check storage issues: {str(e)}"}

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        try:
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            apps_api = client.AppsV1Api(k8s_client)
            
            # Build kubectl command
            cmd = ['kubectl']
            cmd.extend(args)
            
            # Execute command
            result = core_api.read_namespaced_pod_log(name=args[2], namespace=args[3]) # Simplified for describe, get, events
            
            return result.to_str()
            
        except ApiException as e:
            if e.status == 404:
                return f"Resource '{args[2]}' not found in namespace '{args[3]}'"
            elif e.status == 403: # Forbidden
                return f"Access to resource '{args[2]}' in namespace '{args[3]}' is forbidden. Check permissions."
            elif e.status == 410: # Gone
                return f"Resource '{args[2]}' in namespace '{args[3]}' is gone. It might have been deleted."
            else:
                return f"API error executing kubectl command: {e.reason}"
        except Exception as e:
            logger.error(f"Failed to run kubectl command: {e}", exc_info=True)
            return f"Failed to run kubectl command: {str(e)}"

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        resource_type = params.get("resource_type", "unknown")
        resource_name = params.get("resource_name", "unknown")
        return f"kubernetes_troubleshoot(instance_name={instance_name}, resource_type={resource_type}, resource_name={resource_name})"


class KubernetesResourceAnalysisTool(Tool):
    """Tool for comprehensive resource analysis"""
    
    name: str = "kubernetes_resource_analysis"
    description: str = "Comprehensive analysis of Kubernetes resources including resource usage, configuration, and optimization opportunities"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kubernetes instance",
            type="string",
            required=True
        ),
        "analysis_type": ToolParameter(
            description="Type of analysis (resource_usage, configuration, optimization, security)",
            type="string",
            required=True
        ),
        "namespace": ToolParameter(
            description="Namespace to analyze (optional)",
            type="string",
            required=False
        ),
        "resource_kind": ToolParameter(
            description="Resource kind to focus on (optional)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_resource_analysis",
            description="Comprehensive analysis of Kubernetes resources including resource usage, configuration, and optimization opportunities",
            parameters={
                "instance_name": ToolParameter(
                    description="Name of the Kubernetes instance",
                    type="string",
                    required=True
                ),
                "analysis_type": ToolParameter(
                    description="Type of analysis (resource_usage, configuration, optimization, security)",
                    type="string",
                    required=True
                ),
                "namespace": ToolParameter(
                    description="Namespace to analyze (optional)",
                    type="string",
                    required=False
                ),
                "resource_kind": ToolParameter(
                    description="Resource kind to focus on (optional)",
                    type="string",
                    required=False
                )
            }
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Perform specific type of analysis"""
        try:
            instance_name = params.get("instance_name")
            analysis_type = params.get("analysis_type")
            namespace = params.get("namespace")
            resource_kind = params.get("resource_kind")

            if not instance_name or not analysis_type:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name and analysis type are required",
                    params=params
                )

            # Get instance from toolset
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Perform analysis based on type
            analysis_data = self._perform_analysis(instance, analysis_type, namespace, resource_kind)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=analysis_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to perform Kubernetes resource analysis: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to perform Kubernetes resource analysis: {str(e)}",
                params=params
            )

    def _perform_analysis(self, instance: ServiceInstance, analysis_type: str, 
                         namespace: str, resource_kind: str) -> Dict[str, Any]:
        """Perform specific type of analysis"""
        analysis_data = {
            'instance_name': instance.name,
            'analysis_type': analysis_type,
            'namespace': namespace,
            'resource_kind': resource_kind,
            'results': {}
        }

        if analysis_type == 'resource_usage':
            analysis_data['results'] = self._analyze_resource_usage(instance, namespace, resource_kind)
        elif analysis_type == 'configuration':
            analysis_data['results'] = self._analyze_configuration(instance, namespace, resource_kind)
        elif analysis_type == 'optimization':
            analysis_data['results'] = self._analyze_optimization(instance, namespace, resource_kind)
        elif analysis_type == 'security':
            analysis_data['results'] = self._analyze_security(instance, namespace, resource_kind)

        return analysis_data

    def _analyze_resource_usage(self, instance: ServiceInstance, namespace: str, resource_kind: str) -> Dict[str, Any]:
        """Analyze resource usage patterns"""
        usage_data = {}
        
        try:
            # Get resource requests and limits
            if resource_kind == 'pods' or not resource_kind:
                cmd_args = ['get', 'pods']
                if namespace:
                    cmd_args.extend(['-n', namespace])
                else:
                    cmd_args.append('-A')
                cmd_args.extend(['-o', 'custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,CPU_REQUEST:.spec.containers[*].resources.requests.cpu,MEMORY_REQUEST:.spec.containers[*].resources.requests.memory,CPU_LIMIT:.spec.containers[*].resources.limits.cpu,MEMORY_LIMIT:.spec.containers[*].resources.limits.memory'])
                
                usage_data['resource_requests_limits'] = self._run_kubectl_with_instance(instance, cmd_args)
            
            # Get current resource usage
            if resource_kind == 'pods' or not resource_kind:
                cmd_args = ['top', 'pods']
                if namespace:
                    cmd_args.extend(['-n', namespace])
                else:
                    cmd_args.append('-A')
                
                usage_data['current_usage'] = self._run_kubectl_with_instance(instance, cmd_args)
            
            return usage_data
            
        except Exception as e:
            return {'error': f"Failed to analyze resource usage: {str(e)}"}

    def _analyze_configuration(self, instance: ServiceInstance, namespace: str, resource_kind: str) -> Dict[str, Any]:
        """Analyze resource configurations"""
        config_data = {}
        
        try:
            # Get resource configurations
            if resource_kind:
                cmd_args = ['get', resource_kind]
                if namespace:
                    cmd_args.extend(['-n', namespace])
                else:
                    cmd_args.append('-A')
                cmd_args.extend(['-o', 'yaml'])
                
                config_data['resource_configs'] = self._run_kubectl_with_instance(instance, cmd_args)
            else:
                # Get all resource types
                cmd_args = ['api-resources', '--verbs=list', '--namespaced=true']
                config_data['available_resources'] = self._run_kubectl_with_instance(instance, cmd_args)
            
            return config_data
            
        except Exception as e:
            return {'error': f"Failed to analyze configuration: {str(e)}"}

    def _analyze_optimization(self, instance: ServiceInstance, namespace: str, resource_kind: str) -> Dict[str, Any]:
        """Analyze optimization opportunities"""
        optimization_data = {}
        
        try:
            # Check for resource waste
            if resource_kind == 'pods' or not resource_kind:
                # Find pods with high resource usage vs requests
                optimization_data['resource_efficiency'] = self._run_kubectl_with_instance(instance, ['get', 'pods', '-A', '-o', 'custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,CPU_REQUEST:.spec.containers[*].resources.requests.cpu,MEMORY_REQUEST:.spec.containers[*].resources.requests.memory'])
            
            # Check for unused resources
            optimization_data['unused_resources'] = self._run_kubectl_with_instance(instance, ['get', 'pods', '-A', '--field-selector=status.phase!=Running,status.phase!=Pending'])
            
            return optimization_data
            
        except Exception as e:
            return {'error': f"Failed to analyze optimization: {str(e)}"}

    def _analyze_security(self, instance: ServiceInstance, namespace: str, resource_kind: str) -> Dict[str, Any]:
        """Analyze security configurations"""
        security_data = {}
        
        try:
            # Check for pods running as root
            security_data['root_pods'] = self._run_kubectl_with_instance(instance, ['get', 'pods', '-A', '-o', 'custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,SECURITY_CONTEXT:.spec.securityContext.runAsUser'])
            
            # Check for privileged containers
            security_data['privileged_containers'] = self._run_kubectl_with_instance(instance, ['get', 'pods', '-A', '-o', 'custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,PRIVILEGED:.spec.containers[*].securityContext.privileged'])
            
            return security_data
            
        except Exception as e:
            return {'error': f"Failed to analyze security: {str(e)}"}

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        try:
            k8s_client = self._create_kubernetes_client(instance)
            core_api = client.CoreV1Api(k8s_client)
            apps_api = client.AppsV1Api(k8s_client)
            
            # Build kubectl command
            cmd = ['kubectl']
            cmd.extend(args)
            
            # Execute command
            result = core_api.read_namespaced_pod_log(name=args[2], namespace=args[3]) # Simplified for describe, get, events
            
            return result.to_str()
            
        except ApiException as e:
            if e.status == 404:
                return f"Resource '{args[2]}' not found in namespace '{args[3]}'"
            elif e.status == 403: # Forbidden
                return f"Access to resource '{args[2]}' in namespace '{args[3]}' is forbidden. Check permissions."
            elif e.status == 410: # Gone
                return f"Resource '{args[2]}' in namespace '{args[3]}' is gone. It might have been deleted."
            else:
                return f"API error executing kubectl command: {e.reason}"
        except Exception as e:
            logger.error(f"Failed to run kubectl command: {e}", exc_info=True)
            return f"Failed to run kubectl command: {str(e)}"

    def _create_kubernetes_client(self, instance: ServiceInstance) -> client.ApiClient:
        """Create Kubernetes client from kubeconfig"""
        try:
            if not instance.config or not instance.config.get("kubeconfig"):
                raise ValueError("No kubeconfig found in instance configuration")
            
            # Parse kubeconfig
            kubeconfig_data = instance.config["kubeconfig"]
            
            # Create temporary file for kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(kubeconfig_data)
                temp_file_path = temp_file.name
            
            try:
                # Create API client from kubeconfig
                api_client = config.new_client_from_config(config_file=temp_file_path)
                return api_client
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes client: {e}", exc_info=True)
            raise

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get parameterized one-liner for this tool"""
        instance_name = params.get("instance_name", "unknown")
        analysis_type = params.get("analysis_type", "unknown")
        return f"kubernetes_resource_analysis(instance_name={instance_name}, analysis_type={analysis_type})"


# ============================================
# INFRAINSIGHTS KUBERNETES TOOLSET
# ============================================

class InfraInsightsKubernetesToolset(Toolset):
    """InfraInsights Kubernetes toolset for advanced Kubernetes monitoring and management"""
    
    def __init__(self):
        super().__init__(
            name="infrainsights_kubernetes",
            description="Comprehensive Kubernetes monitoring, troubleshooting, and analysis toolset powered by InfraInsights. Features 9 advanced tools for cluster health checks, resource management, log analysis, metrics monitoring, advanced troubleshooting (probes, network, storage), and resource optimization. Seamlessly integrates with InfraInsights API for secure kubeconfig management and multi-cluster support.",
            prerequisites=[],  # Empty list during initialization
            tools=[
                KubernetesHealthCheckTool(self),
                KubernetesListResourcesTool(self),
                KubernetesDescribeResourceTool(self),
                KubernetesLogsTool(self),
                KubernetesEventsTool(self),
                KubernetesLogsSearchTool(self),
                KubernetesMetricsTool(self),
                KubernetesTroubleshootingTool(self),
                KubernetesResourceAnalysisTool(self),
            ],
            tags=[ToolsetTag.CORE],
            enabled=False,
        )
        
        logger.info("🚀🚀🚀 CREATING INFRAINSIGHTS KUBERNETES TOOLSET 🚀🚀🚀")
        logger.info("✅✅✅ INFRAINSIGHTS KUBERNETES TOOLSET CREATED SUCCESSFULLY ✅✅✅")

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with InfraInsights connection details"""
        try:
            logger.info("🔧🔧🔧 CONFIGURING INFRAINSIGHTS KUBERNETES TOOLSET 🔧🔧🔧")
            logger.info(f"🔧 Config received: {config}")
            
            # Extract configuration
            infrainsights_url = config.get('infrainsights_url')
            api_key = config.get('api_key')
            timeout = config.get('timeout', 30)
            
            logger.info(f"🔧 Extracted config - URL: {infrainsights_url}, API Key: {'***' if api_key else 'None'}, Timeout: {timeout}")
            
            if not infrainsights_url:
                raise ValueError("infrainsights_url is required in configuration")
            
            # Create InfraInsights config
            infrainsights_config = InfraInsightsConfig(
                base_url=infrainsights_url,
                api_key=api_key,
                timeout=timeout
            )
            
            # Initialize client
            infrainsights_client = InfraInsightsClientV2(infrainsights_config)
            
            # Set attributes using object.__setattr__ to bypass Pydantic restrictions
            object.__setattr__(self, 'infrainsights_config', infrainsights_config)
            object.__setattr__(self, 'infrainsights_client', infrainsights_client)
            
            logger.info(f"✅✅✅ INFRAINSIGHTS KUBERNETES TOOLSET CONFIGURED WITH URL: {infrainsights_url} ✅✅✅")
            
            # Enable the toolset after successful configuration
            self.enabled = True
            
            # Now add prerequisites after configuration is complete
            self.prerequisites = [CallablePrerequisite(callable=self._check_prerequisites)]
            
            # Test prerequisites check
            logger.info("🔍🔍🔍 TESTING PREREQUISITES CHECK AFTER CONFIGURATION 🔍🔍🔍")
            prereq_result, prereq_message = self._check_prerequisites({})
            logger.info(f"🔍 Prerequisites check result: {prereq_result}, message: {prereq_message}")
            
        except Exception as e:
            logger.error(f"Failed to configure InfraInsights Kubernetes toolset: {e}")
            raise

    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if prerequisites are met"""
        try:
            logger.info("🔍🔍🔍 CHECKING PREREQUISITES FOR INFRAINSIGHTS KUBERNETES TOOLSET 🔍🔍🔍")
            logger.info(f"🔍 Context received: {context}")
            
            infrainsights_client = getattr(self, 'infrainsights_client', None)
            if not infrainsights_client:
                logger.warning("🔍 InfraInsights client not configured")
                return True, f"InfraInsights client not configured (toolset still enabled)"
            
            logger.info("🔍 InfraInsights client configured, checking API accessibility")
            
            # Check if InfraInsights API is accessible
            try:
                health_result = infrainsights_client.health_check()
                logger.info(f"🔍 Health check result: {health_result}")
                if not health_result:
                    logger.warning("🔍 InfraInsights API is not accessible")
                    return True, f"InfraInsights API at {self.infrainsights_config.base_url} is not accessible (toolset still enabled)"
            except Exception as e:
                logger.warning(f"🔍 InfraInsights API health check failed: {e}")
                return True, f"InfraInsights API health check failed: {str(e)} (toolset still enabled)"
            
            logger.info("🔍 InfraInsights API is accessible, checking Kubernetes Python client availability")
            
            # Check if kubernetes Python client is available
            try:
                import kubernetes
                logger.info(f"🔍 Kubernetes Python client version: {kubernetes.__version__}")
                logger.info("🔍 Kubernetes Python client is available and working")
            except ImportError:
                logger.warning("🔍 Kubernetes Python client not installed")
                return False, "kubernetes Python client is not installed"
            except Exception as e:
                logger.warning(f"🔍 Kubernetes Python client check failed with error: {e}")
                return False, f"Kubernetes Python client check failed: {e}"
            
            logger.info("✅✅✅ ALL PREREQUISITES CHECK PASSED FOR INFRAINSIGHTS KUBERNETES TOOLSET ✅✅✅")
            return True, ""
            
        except Exception as e:
            logger.error(f"🔍 Prerequisites check failed with exception: {e}")
            return True, f"Prerequisites check failed: {str(e)} (toolset still enabled)"

    def get_instance(self, instance_name: str) -> Optional[ServiceInstance]:
        """Get Kubernetes instance by name"""
        try:
            infrainsights_client = getattr(self, 'infrainsights_client', None)
            if not infrainsights_client:
                raise Exception("InfraInsights client not configured")
            
            # Get instance with configuration
            instance = infrainsights_client.get_instance_by_name_and_type(
                service_type='kubernetes',
                name=instance_name,
                include_config=True
            )
            
            if not instance:
                logger.warning(f"Kubernetes instance '{instance_name}' not found")
                return None
            
            return instance
            
        except Exception as e:
            logger.error(f"Failed to get Kubernetes instance '{instance_name}': {e}")
            return None

    def get_example_config(self) -> Dict[str, Any]:
        """Return example configuration for this toolset"""
        return {
            "infrainsights_url": "http://localhost:3001",
            "api_key": "your-jwt-token-here",
            "timeout": 30
        } 