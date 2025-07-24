import json
import logging
import subprocess
import tempfile
import os
from typing import Dict, Any, Optional, List
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite, ToolParameter
from holmes.plugins.toolsets.infrainsights.infrainsights_client_v2 import InfraInsightsClientV2, InfraInsightsConfig, ServiceInstance

logger = logging.getLogger(__name__)


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
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name is required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Execute kubectl commands to check cluster health
            health_data = self._check_cluster_health(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=health_data,
                params=params
            )

        except Exception as e:
            logger.error(f"Error checking Kubernetes health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Kubernetes health: {str(e)}",
                params=params
            )

    def _check_cluster_health(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Check cluster health using kubectl commands"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            health_data = {
                'instance_info': {
                    'name': instance.name,
                    'environment': instance.environment,
                    'status': instance.status,
                    'description': instance.description
                },
                'cluster_health': {},
                'node_status': {},
                'component_status': {}
            }

            # Check cluster info
            try:
                cluster_info = self._run_kubectl(kubeconfig, ['cluster-info'])
                health_data['cluster_health']['cluster_info'] = cluster_info
            except Exception as e:
                health_data['cluster_health']['cluster_info_error'] = str(e)

            # Check node status
            try:
                nodes = self._run_kubectl(kubeconfig, ['get', 'nodes', '-o', 'wide'])
                health_data['node_status']['nodes'] = nodes
            except Exception as e:
                health_data['node_status']['nodes_error'] = str(e)

            # Check component status
            try:
                components = self._run_kubectl(kubeconfig, ['get', 'componentstatuses'])
                health_data['component_status']['components'] = components
            except Exception as e:
                health_data['component_status']['components_error'] = str(e)

            return health_data

        finally:
            # Clean up temporary kubeconfig
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        # Write kubeconfig content
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def _run_kubectl(self, kubeconfig: str, args: List[str]) -> str:
        """Run kubectl command with the provided kubeconfig"""
        cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise Exception(f"kubectl command failed: {result.stderr}")
        
        return result.stdout

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
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
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            kind = params.get('kind')
            namespace = params.get('namespace', 'default')
            output_format = params.get('output_format', 'wide')

            if not instance_name or not kind:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name and kind are required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Build kubectl command
            cmd_args = ['get', kind, '-o', output_format]
            if namespace and namespace.lower() != 'all':
                cmd_args.extend(['-n', namespace])
            elif namespace and namespace.lower() == 'all':
                cmd_args.append('-A')

            # Execute command
            result = self._run_kubectl_with_instance(instance, cmd_args)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'kind': kind,
                    'namespace': namespace,
                    'output_format': output_format,
                    'result': result
                },
                params=params
            )

        except Exception as e:
            logger.error(f"Error listing Kubernetes resources: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list Kubernetes resources: {str(e)}",
                params=params
            )

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        kind = params.get('kind', 'unknown')
        namespace = params.get('namespace', 'default')
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
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            kind = params.get('kind')
            name = params.get('name')
            namespace = params.get('namespace')

            if not all([instance_name, kind, name]):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name, kind, and name are required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Build kubectl command
            cmd_args = ['describe', kind, name]
            if namespace:
                cmd_args.extend(['-n', namespace])

            # Execute command
            result = self._run_kubectl_with_instance(instance, cmd_args)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'kind': kind,
                    'name': name,
                    'namespace': namespace,
                    'description': result
                },
                params=params
            )

        except Exception as e:
            logger.error(f"Error describing Kubernetes resource: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to describe Kubernetes resource: {str(e)}",
                params=params
            )

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        kind = params.get('kind', 'unknown')
        name = params.get('name', 'unknown')
        return f"kubernetes_describe_resource(instance_name={instance_name}, kind={kind}, name={name})"


# ============================================
# PHASE 2: LOGS AND EVENTS TOOLS
# ============================================

class KubernetesLogsTool(Tool):
    """Tool to fetch Kubernetes pod logs"""
    
    name: str = "kubernetes_logs"
    description: str = "Fetch logs from Kubernetes pods with various filtering options"
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
            description="Container name (for multi-container pods)",
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
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_logs",
            description="Fetch logs from Kubernetes pods with various filtering options",
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
                    description="Container name (for multi-container pods)",
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
                )
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            pod_name = params.get('pod_name')
            namespace = params.get('namespace', 'default')
            container = params.get('container')
            previous = params.get('previous', False)
            tail = params.get('tail')
            since = params.get('since')

            if not instance_name or not pod_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name and pod name are required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Build kubectl command
            cmd_args = ['logs', pod_name, '-n', namespace]
            
            if container:
                cmd_args.extend(['-c', container])
            
            if previous:
                cmd_args.append('--previous')
            
            if tail:
                cmd_args.extend(['--tail', str(tail)])
            
            if since:
                cmd_args.extend(['--since', since])

            # Execute command
            result = self._run_kubectl_with_instance(instance, cmd_args)
            
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
                    'logs': result
                },
                params=params
            )

        except Exception as e:
            logger.error(f"Error fetching Kubernetes logs: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to fetch Kubernetes logs: {str(e)}",
                params=params
            )

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        pod_name = params.get('pod_name', 'unknown')
        namespace = params.get('namespace', 'default')
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
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            resource_type = params.get('resource_type')
            resource_name = params.get('resource_name')
            namespace = params.get('namespace')
            output_format = params.get('output_format', 'wide')

            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name is required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Build kubectl command
            if resource_type and resource_name:
                # Events for specific resource
                cmd_args = ['events', '--for', f'{resource_type}/{resource_name}', '-o', output_format]
                if namespace:
                    cmd_args.extend(['-n', namespace])
            else:
                # General events
                cmd_args = ['get', 'events', '-o', output_format]
                if namespace:
                    cmd_args.extend(['-n', namespace])
                else:
                    cmd_args.append('-A')

            # Execute command
            result = self._run_kubectl_with_instance(instance, cmd_args)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'resource_type': resource_type,
                    'resource_name': resource_name,
                    'namespace': namespace,
                    'output_format': output_format,
                    'events': result
                },
                params=params
            )

        except Exception as e:
            logger.error(f"Error fetching Kubernetes events: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to fetch Kubernetes events: {str(e)}",
                params=params
            )

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        resource_type = params.get('resource_type', 'all')
        namespace = params.get('namespace', 'all')
        return f"kubernetes_events(instance_name={instance_name}, resource_type={resource_type}, namespace={namespace})"


class KubernetesLogsSearchTool(Tool):
    """Tool to search logs for specific patterns"""
    
    name: str = "kubernetes_logs_search"
    description: str = "Search Kubernetes pod logs for specific patterns or terms"
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
            description="Container name (for multi-container pods)",
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
        )
    }
    toolset: Optional[Any] = None

    def __init__(self, toolset=None):
        super().__init__(
            name="kubernetes_logs_search",
            description="Search Kubernetes pod logs for specific patterns or terms",
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
                    description="Container name (for multi-container pods)",
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
                )
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            pod_name = params.get('pod_name')
            namespace = params.get('namespace', 'default')
            search_term = params.get('search_term')
            container = params.get('container')
            case_sensitive = params.get('case_sensitive', False)
            invert_match = params.get('invert_match', False)

            if not all([instance_name, pod_name, search_term]):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name, pod name, and search term are required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Build kubectl command for logs
            cmd_args = ['logs', pod_name, '-n', namespace]
            
            if container:
                cmd_args.extend(['-c', container])

            # Execute logs command and pipe to grep
            logs_result = self._run_kubectl_with_instance(instance, cmd_args)
            
            # Apply search filter
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
                    'filtered_logs': filtered_logs,
                    'total_lines': len(logs_result.splitlines()),
                    'matching_lines': len(filtered_logs.splitlines())
                },
                params=params
            )

        except Exception as e:
            logger.error(f"Error searching Kubernetes logs: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to search Kubernetes logs: {str(e)}",
                params=params
            )

    def _filter_logs(self, logs: str, search_term: str, case_sensitive: bool, invert_match: bool) -> str:
        """Filter logs using search term"""
        import re
        
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

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        pod_name = params.get('pod_name', 'unknown')
        search_term = params.get('search_term', 'unknown')
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
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            resource_type = params.get('resource_type')
            namespace = params.get('namespace')

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

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Build kubectl command
            cmd_args = ['top', resource_type]
            if resource_type == 'pods' and namespace:
                cmd_args.extend(['-n', namespace])
            elif resource_type == 'pods':
                cmd_args.append('-A')

            # Execute command
            result = self._run_kubectl_with_instance(instance, cmd_args)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    'instance_name': instance_name,
                    'resource_type': resource_type,
                    'namespace': namespace,
                    'metrics': result
                },
                params=params
            )

        except Exception as e:
            logger.error(f"Error fetching Kubernetes metrics: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to fetch Kubernetes metrics: {str(e)}",
                params=params
            )

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        resource_type = params.get('resource_type', 'unknown')
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
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            resource_type = params.get('resource_type')
            resource_name = params.get('resource_name')
            namespace = params.get('namespace', 'default')
            troubleshooting_type = params.get('troubleshooting_type', 'status')

            if not all([instance_name, resource_type, resource_name]):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name, resource type, and resource name are required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Perform troubleshooting based on type
            troubleshooting_data = self._perform_troubleshooting(
                instance, resource_type, resource_name, namespace, troubleshooting_type
            )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=troubleshooting_data,
                params=params
            )

        except Exception as e:
            logger.error(f"Error performing Kubernetes troubleshooting: {e}", exc_info=True)
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
            # Get detailed status information
            troubleshooting_data['results']['describe'] = self._run_kubectl_with_instance(
                instance, ['describe', resource_type, resource_name, '-n', namespace]
            )
            
            troubleshooting_data['results']['get_yaml'] = self._run_kubectl_with_instance(
                instance, ['get', resource_type, resource_name, '-n', namespace, '-o', 'yaml']
            )

        elif troubleshooting_type == 'readiness':
            # Check readiness probes
            if resource_type == 'pod':
                troubleshooting_data['results']['readiness_check'] = self._check_readiness_probes(
                    instance, resource_name, namespace
                )

        elif troubleshooting_type == 'liveness':
            # Check liveness probes
            if resource_type == 'pod':
                troubleshooting_data['results']['liveness_check'] = self._check_liveness_probes(
                    instance, resource_name, namespace
                )

        elif troubleshooting_type == 'network':
            # Network connectivity checks
            troubleshooting_data['results']['network_check'] = self._check_network_connectivity(
                instance, resource_type, resource_name, namespace
            )

        elif troubleshooting_type == 'storage':
            # Storage-related checks
            troubleshooting_data['results']['storage_check'] = self._check_storage_issues(
                instance, resource_type, resource_name, namespace
            )

        return troubleshooting_data

    def _check_readiness_probes(self, instance: ServiceInstance, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Check readiness probe configuration and status"""
        try:
            # Get pod details
            pod_yaml = self._run_kubectl_with_instance(
                instance, ['get', 'pod', pod_name, '-n', namespace, '-o', 'yaml']
            )
            
            # Parse YAML to check readiness probe configuration
            import yaml
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
            pod_yaml = self._run_kubectl_with_instance(
                instance, ['get', 'pod', pod_name, '-n', namespace, '-o', 'yaml']
            )
            
            # Parse YAML to check liveness probe configuration
            import yaml
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
                network_info['endpoints'] = self._run_kubectl_with_instance(
                    instance, ['get', 'endpoints', resource_name, '-n', namespace, '-o', 'yaml']
                )
            
            # Get service details
            if resource_type == 'service':
                network_info['service_details'] = self._run_kubectl_with_instance(
                    instance, ['get', 'service', resource_name, '-n', namespace, '-o', 'yaml']
                )
            
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
                storage_info['pvc'] = self._run_kubectl_with_instance(
                    instance, ['get', 'pvc', '-n', namespace, '-o', 'wide']
                )
            
            # Get persistent volumes
            storage_info['pv'] = self._run_kubectl_with_instance(
                instance, ['get', 'pv', '-o', 'wide']
            )
            
            return storage_info
            
        except Exception as e:
            return {'error': f"Failed to check storage issues: {str(e)}"}

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        resource_type = params.get('resource_type', 'unknown')
        resource_name = params.get('resource_name', 'unknown')
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
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            analysis_type = params.get('analysis_type')
            namespace = params.get('namespace')
            resource_kind = params.get('resource_kind')

            if not instance_name or not analysis_type:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Instance name and analysis type are required",
                    params=params
                )

            # Get instance details from InfraInsights
            instance = self.toolset.get_instance(instance_name)
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kubernetes instance '{instance_name}' not found",
                    params=params
                )

            # Perform analysis based on type
            analysis_data = self._perform_analysis(
                instance, analysis_type, namespace, resource_kind
            )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=analysis_data,
                params=params
            )

        except Exception as e:
            logger.error(f"Error performing Kubernetes resource analysis: {e}", exc_info=True)
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
                optimization_data['resource_efficiency'] = self._run_kubectl_with_instance(
                    instance, ['get', 'pods', '-A', '-o', 'custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,CPU_REQUEST:.spec.containers[*].resources.requests.cpu,MEMORY_REQUEST:.spec.containers[*].resources.requests.memory']
                )
            
            # Check for unused resources
            optimization_data['unused_resources'] = self._run_kubectl_with_instance(
                instance, ['get', 'pods', '-A', '--field-selector=status.phase!=Running,status.phase!=Pending']
            )
            
            return optimization_data
            
        except Exception as e:
            return {'error': f"Failed to analyze optimization: {str(e)}"}

    def _analyze_security(self, instance: ServiceInstance, namespace: str, resource_kind: str) -> Dict[str, Any]:
        """Analyze security configurations"""
        security_data = {}
        
        try:
            # Check for pods running as root
            security_data['root_pods'] = self._run_kubectl_with_instance(
                instance, ['get', 'pods', '-A', '-o', 'custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,SECURITY_CONTEXT:.spec.securityContext.runAsUser']
            )
            
            # Check for privileged containers
            security_data['privileged_containers'] = self._run_kubectl_with_instance(
                instance, ['get', 'pods', '-A', '-o', 'custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,PRIVILEGED:.spec.containers[*].securityContext.privileged']
            )
            
            return security_data
            
        except Exception as e:
            return {'error': f"Failed to analyze security: {str(e)}"}

    def _run_kubectl_with_instance(self, instance: ServiceInstance, args: List[str]) -> str:
        """Run kubectl command with instance kubeconfig"""
        kubeconfig = self._create_temp_kubeconfig(instance)
        
        try:
            cmd = ['kubectl', '--kubeconfig', kubeconfig] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"kubectl command failed: {result.stderr}")
            
            return result.stdout
        finally:
            if os.path.exists(kubeconfig):
                os.unlink(kubeconfig)

    def _create_temp_kubeconfig(self, instance: ServiceInstance) -> str:
        """Create a temporary kubeconfig file from instance config"""
        if not instance.config or 'kubeconfig' not in instance.config:
            raise Exception("No kubeconfig found in instance configuration")
        
        fd, temp_path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write(instance.config['kubeconfig'])
        
        return temp_path

    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        analysis_type = params.get('analysis_type', 'unknown')
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
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/infrainsights.html",
            icon_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRPKA-U9m5BxYQDF1O7atMfj9EMMXEoGu4t0Q&s",
            prerequisites=[
                CallablePrerequisite(callable=self._check_prerequisites)
            ],
            tools=[
                # Phase 1 tools
                KubernetesHealthCheckTool(self),
                KubernetesListResourcesTool(self),
                KubernetesDescribeResourceTool(self),
                # Phase 2 tools
                KubernetesLogsTool(self),
                KubernetesEventsTool(self),
                KubernetesLogsSearchTool(self),
                # Phase 3 tools
                KubernetesMetricsTool(self),
                KubernetesTroubleshootingTool(self),
                KubernetesResourceAnalysisTool(self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
            is_default=False,
        )

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with InfraInsights connection details"""
        try:
            # Extract configuration
            infrainsights_url = config.get('infrainsights_url')
            api_key = config.get('api_key')
            timeout = config.get('timeout', 30)
            
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
            
            logger.info(f"InfraInsights Kubernetes toolset configured with URL: {infrainsights_url}")
            
        except Exception as e:
            logger.error(f"Failed to configure InfraInsights Kubernetes toolset: {e}")
            raise

    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if prerequisites are met"""
        try:
            logger.info("🔍 Checking prerequisites for InfraInsights Kubernetes toolset")
            
            infrainsights_client = getattr(self, 'infrainsights_client', None)
            if not infrainsights_client:
                logger.warning("🔍 InfraInsights client not configured")
                return False, "InfraInsights client not configured"
            
            logger.info("🔍 InfraInsights client configured, checking API accessibility")
            
            # Check if InfraInsights API is accessible
            if not infrainsights_client.health_check():
                logger.warning("🔍 InfraInsights API is not accessible")
                return False, "InfraInsights API is not accessible"
            
            logger.info("🔍 InfraInsights API is accessible, checking kubectl availability")
            
            # Check if kubectl is available
            try:
                result = subprocess.run(['kubectl', 'version', '--client'], 
                                      capture_output=True, text=True, timeout=10)
                logger.info(f"🔍 kubectl version check result: {result.returncode}")
                if result.returncode != 0:
                    logger.warning(f"🔍 kubectl version check failed: {result.stderr}")
                    return False, f"kubectl version check failed: {result.stderr}"
                logger.info("🔍 kubectl is available and working")
            except FileNotFoundError:
                logger.warning("🔍 kubectl command not found")
                return False, "kubectl is not available (command not found)"
            except subprocess.TimeoutExpired:
                logger.warning("🔍 kubectl version check timed out")
                return False, "kubectl version check timed out"
            except subprocess.CalledProcessError as e:
                logger.warning(f"🔍 kubectl version check failed with error: {e}")
                return False, f"kubectl version check failed: {e}"
            
            logger.info("✅ All prerequisites check passed for InfraInsights Kubernetes toolset")
            return True, ""
            
        except Exception as e:
            logger.error(f"🔍 Prerequisites check failed with exception: {e}")
            return False, f"Prerequisites check failed: {str(e)}"

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