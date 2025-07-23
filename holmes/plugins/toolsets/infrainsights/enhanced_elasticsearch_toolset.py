import json
import logging
from typing import Dict, Any, Optional
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite, ToolParameter

logger = logging.getLogger(__name__)


class ElasticsearchHealthCheckTool(Tool):
    """Tool to check Elasticsearch/OpenSearch cluster health"""
    
    name: str = "elasticsearch_health_check"
    description: str = "Check the health status of an Elasticsearch or OpenSearch cluster"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance to check",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Checking health for Elasticsearch/OpenSearch instance: {instance_name}")
            
            # Get instance configuration from toolset
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Resolve instance
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            # Get cluster health
            health_data = self.toolset.infrainsights_client.get_elasticsearch_health(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=health_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error checking Elasticsearch health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Elasticsearch health: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_health_check(instance_name={instance_name})"


class ElasticsearchListIndicesTool(Tool):
    """Tool to list Elasticsearch/OpenSearch indices"""
    
    name: str = "elasticsearch_list_indices"
    description: str = "List all indices in an Elasticsearch or OpenSearch cluster"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Listing indices for Elasticsearch/OpenSearch instance: {instance_name}")
            
            # Get instance configuration from toolset
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Resolve instance
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            # Get indices
            indices_data = self.toolset.infrainsights_client.get_elasticsearch_indices(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=indices_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error listing Elasticsearch indices: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list Elasticsearch indices: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_list_indices(instance_name={instance_name})"


class ElasticsearchClusterStatsTool(Tool):
    """Tool to get Elasticsearch/OpenSearch cluster statistics"""
    
    name: str = "elasticsearch_cluster_stats"
    description: str = "Retrieve cluster-wide statistics including disk usage, shard distribution, and data nodes"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting cluster stats for Elasticsearch/OpenSearch instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            stats_data = self.toolset.infrainsights_client.get_elasticsearch_cluster_stats(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=stats_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting cluster stats: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get cluster stats: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_cluster_stats(instance_name={instance_name})"


class ElasticsearchNodeStatsTool(Tool):
    """Tool to get Elasticsearch/OpenSearch node statistics"""
    
    name: str = "elasticsearch_node_stats"
    description: str = "Fetch detailed statistics for all nodes including JVM memory, CPU usage, and thread pool metrics"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting node stats for Elasticsearch/OpenSearch instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            stats_data = self.toolset.infrainsights_client.get_elasticsearch_node_stats(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=stats_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting node stats: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get node stats: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_node_stats(instance_name={instance_name})"


class ElasticsearchIndexStatsTool(Tool):
    """Tool to get Elasticsearch/OpenSearch index statistics"""
    
    name: str = "elasticsearch_index_stats"
    description: str = "Retrieve statistics for a specific index including document count, size, and shard status"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        ),
        "index_name": ToolParameter(
            description="Name of the index (optional - if not provided, returns stats for all indices)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            index_name = params.get('index_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting index stats for Elasticsearch/OpenSearch instance: {instance_name}, index: {index_name or 'all'}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            stats_data = self.toolset.infrainsights_client.get_elasticsearch_index_stats(instance, index_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=stats_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting index stats: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get index stats: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        index_name = params.get('index_name', 'all')
        return f"elasticsearch_index_stats(instance_name={instance_name}, index_name={index_name})"


class ElasticsearchShardAllocationTool(Tool):
    """Tool to get Elasticsearch/OpenSearch shard allocation information"""
    
    name: str = "elasticsearch_shard_allocation"
    description: str = "Fetch shard allocation and unassigned shard information for the cluster or a specific index"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        ),
        "index_name": ToolParameter(
            description="Name of the index (optional - if not provided, returns allocation for all indices)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            index_name = params.get('index_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting shard allocation for Elasticsearch/OpenSearch instance: {instance_name}, index: {index_name or 'all'}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            allocation_data = self.toolset.infrainsights_client.get_elasticsearch_shard_allocation(instance, index_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=allocation_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting shard allocation: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get shard allocation: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        index_name = params.get('index_name', 'all')
        return f"elasticsearch_shard_allocation(instance_name={instance_name}, index_name={index_name})"


class ElasticsearchTasksTool(Tool):
    """Tool to get Elasticsearch/OpenSearch running tasks"""
    
    name: str = "elasticsearch_tasks"
    description: str = "List all currently running tasks in the cluster including task type and duration"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting running tasks for Elasticsearch/OpenSearch instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            tasks_data = self.toolset.infrainsights_client.get_elasticsearch_tasks(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=tasks_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting tasks: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get tasks: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_tasks(instance_name={instance_name})"


class ElasticsearchPendingTasksTool(Tool):
    """Tool to get Elasticsearch/OpenSearch pending tasks"""
    
    name: str = "elasticsearch_pending_tasks"
    description: str = "List pending cluster-level tasks that might indicate bottlenecks"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting pending tasks for Elasticsearch/OpenSearch instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            pending_data = self.toolset.infrainsights_client.get_elasticsearch_pending_tasks(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=pending_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting pending tasks: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get pending tasks: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_pending_tasks(instance_name={instance_name})"


class ElasticsearchThreadPoolStatsTool(Tool):
    """Tool to get Elasticsearch/OpenSearch thread pool statistics"""
    
    name: str = "elasticsearch_thread_pool_stats"
    description: str = "Retrieve thread pool statistics for all nodes including queue size, active threads, and rejections"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting thread pool stats for Elasticsearch/OpenSearch instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            stats_data = self.toolset.infrainsights_client.get_elasticsearch_thread_pool_stats(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=stats_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting thread pool stats: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get thread pool stats: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_thread_pool_stats(instance_name={instance_name})"


class ElasticsearchIndexMappingTool(Tool):
    """Tool to get Elasticsearch/OpenSearch index mapping"""
    
    name: str = "elasticsearch_index_mapping"
    description: str = "Retrieve the mapping details of an index to analyze its structure and field types"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        ),
        "index_name": ToolParameter(
            description="Name of the index to get mapping for",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            index_name = params.get('index_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
                
            if not index_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="index_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting index mapping for Elasticsearch/OpenSearch instance: {instance_name}, index: {index_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            mapping_data = self.toolset.infrainsights_client.get_elasticsearch_index_mapping(instance, index_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=mapping_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting index mapping: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get index mapping: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        index_name = params.get('index_name', 'unknown')
        return f"elasticsearch_index_mapping(instance_name={instance_name}, index_name={index_name})"


class ElasticsearchIndexSettingsTool(Tool):
    """Tool to get Elasticsearch/OpenSearch index settings"""
    
    name: str = "elasticsearch_index_settings"
    description: str = "Retrieve the settings of an index including replication factor and refresh interval"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        ),
        "index_name": ToolParameter(
            description="Name of the index to get settings for",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            index_name = params.get('index_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
                
            if not index_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="index_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting index settings for Elasticsearch/OpenSearch instance: {instance_name}, index: {index_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            settings_data = self.toolset.infrainsights_client.get_elasticsearch_index_settings(instance, index_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=settings_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting index settings: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get index settings: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        index_name = params.get('index_name', 'unknown')
        return f"elasticsearch_index_settings(instance_name={instance_name}, index_name={index_name})"


class ElasticsearchHotThreadsTool(Tool):
    """Tool to analyze hot threads on Elasticsearch/OpenSearch nodes"""
    
    name: str = "elasticsearch_hot_threads"
    description: str = "Analyze hot threads on nodes to diagnose performance bottlenecks"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        ),
        "node_name": ToolParameter(
            description="Name of the specific node (optional - if not provided, returns for all nodes)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            node_name = params.get('node_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting hot threads for Elasticsearch/OpenSearch instance: {instance_name}, node: {node_name or 'all'}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            hot_threads_data = self.toolset.infrainsights_client.get_elasticsearch_hot_threads(instance, node_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=hot_threads_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting hot threads: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get hot threads: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        node_name = params.get('node_name', 'all')
        return f"elasticsearch_hot_threads(instance_name={instance_name}, node_name={node_name})"


class ElasticsearchSnapshotStatusTool(Tool):
    """Tool to get Elasticsearch/OpenSearch snapshot status"""
    
    name: str = "elasticsearch_snapshot_status"
    description: str = "Fetch the status of ongoing snapshots in the cluster"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Elasticsearch or OpenSearch instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting snapshot status for Elasticsearch/OpenSearch instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "elasticsearch", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch/OpenSearch instance '{instance_name}' not found",
                    params=params
                )
            
            snapshot_data = self.toolset.infrainsights_client.get_elasticsearch_snapshot_status(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=snapshot_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting snapshot status: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get snapshot status: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"elasticsearch_snapshot_status(instance_name={instance_name})"


class ElasticsearchEnhancedToolset(Toolset):
    """Enhanced Elasticsearch/OpenSearch toolset with InfraInsights integration"""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2
        from .base_toolset_v2 import InfraInsightsConfig
        
        logger.info("🚀🚀🚀 CREATING ENHANCED ELASTICSEARCH TOOLSET 🚀🚀🚀")
        
        # Create comprehensive tools
        tools = [
            # Basic operations
            ElasticsearchHealthCheckTool(toolset=None),
            ElasticsearchListIndicesTool(toolset=None),
            
            # Cluster and node monitoring
            ElasticsearchClusterStatsTool(toolset=None),
            ElasticsearchNodeStatsTool(toolset=None),
            ElasticsearchThreadPoolStatsTool(toolset=None),
            
            # Index operations
            ElasticsearchIndexStatsTool(toolset=None),
            ElasticsearchIndexMappingTool(toolset=None),
            ElasticsearchIndexSettingsTool(toolset=None),
            ElasticsearchShardAllocationTool(toolset=None),
            
            # Task management and performance
            ElasticsearchTasksTool(toolset=None),
            ElasticsearchPendingTasksTool(toolset=None),
            ElasticsearchHotThreadsTool(toolset=None),
            
            # Backup and maintenance
            ElasticsearchSnapshotStatusTool(toolset=None),
        ]
        
        # Initialize Toolset with required parameters
        super().__init__(
            name="infrainsights_elasticsearch_enhanced",
            description="Enhanced Elasticsearch/OpenSearch toolset with InfraInsights instance management",
            enabled=True,
            tools=tools,
            tags=[ToolsetTag.CLUSTER],
            prerequisites=[]  # Remove prerequisites during initialization
        )
        
        # Initialize InfraInsights client with default config
        self.infrainsights_config = InfraInsightsConfig(
            base_url="http://localhost:3000",  # Default backend URL
            api_key=None,  # Will be set from environment or config
            username=None,
            password=None,
            timeout=30,
            enable_name_lookup=True,
            use_v2_api=True
        )
        self.infrainsights_client = InfraInsightsClientV2(self.infrainsights_config)
        
        logger.info(f"🔧 Initialized with default URL: {self.infrainsights_config.base_url}")
        
        # Set toolset reference for tools
        for tool in self.tools:
            tool.toolset = self
        
        # Set config to None initially
        self.config = None
        
        logger.info("✅✅✅ ENHANCED ELASTICSEARCH TOOLSET CREATED SUCCESSFULLY ✅✅✅")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with the provided configuration"""
        logger.info(f"🚀🚀🚀 CONFIGURING ENHANCED ELASTICSEARCH TOOLSET 🚀🚀🚀")
        logger.info(f"🔧 Config received: {config}")
        
        # Store the config
        self.config = config
        
        # Extract InfraInsights configuration - handle both nested and flat structures
        if isinstance(config, dict) and 'config' in config:
            # Nested structure: { "config": { "infrainsights_url": "...", ... } }
            infrainsights_config = config['config']
            logger.info(f"🔧 Using nested config structure: {infrainsights_config}")
        elif isinstance(config, dict):
            # Flat structure: { "infrainsights_url": "...", ... }
            infrainsights_config = config
            logger.info(f"🔧 Using flat config structure: {infrainsights_config}")
        else:
            logger.warning(f"🔧 Unexpected config type: {type(config)}, using defaults")
            infrainsights_config = {}
        
        # Update InfraInsights client configuration
        base_url = infrainsights_config.get('infrainsights_url', 'http://localhost:3000')
        api_key = infrainsights_config.get('api_key')
        timeout = infrainsights_config.get('timeout', 30)
        enable_name_lookup = infrainsights_config.get('enable_name_lookup', True)
        use_v2_api = infrainsights_config.get('use_v2_api', True)
        
        logger.info(f"🔧 Extracted configuration:")
        logger.info(f"🔧   base_url: {base_url}")
        logger.info(f"🔧   api_key: {'***' if api_key else 'None'}")
        logger.info(f"🔧   timeout: {timeout}")
        logger.info(f"🔧   enable_name_lookup: {enable_name_lookup}")
        logger.info(f"🔧   use_v2_api: {use_v2_api}")
        
        # Update the InfraInsights config
        self.infrainsights_config.base_url = base_url
        self.infrainsights_config.api_key = api_key
        self.infrainsights_config.timeout = timeout
        self.infrainsights_config.enable_name_lookup = enable_name_lookup
        self.infrainsights_config.use_v2_api = use_v2_api
        
        # Reinitialize the client with updated config
        from .infrainsights_client_v2 import InfraInsightsClientV2
        self.infrainsights_client = InfraInsightsClientV2(self.infrainsights_config)
        
        # Now add prerequisites after configuration is complete
        self.prerequisites = [CallablePrerequisite(callable=self._check_prerequisites)]
        
        logger.info(f"✅✅✅ ENHANCED ELASTICSEARCH TOOLSET CONFIGURED WITH URL: {base_url} ✅✅✅")
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if InfraInsights client can connect to the backend"""
        try:
            logger.info(f"🔍 Checking prerequisites for InfraInsights client")
            logger.info(f"🔍 Current base_url: {self.infrainsights_config.base_url}")
            logger.info(f"🔍 API key configured: {'Yes' if self.infrainsights_config.api_key else 'No'}")
            
            # Try to connect to InfraInsights backend
            logger.info(f"🔍 Attempting health check to: {self.infrainsights_config.base_url}/api/health")
            if self.infrainsights_client.health_check():
                logger.info("✅ InfraInsights backend health check passed")
                return True, f"InfraInsights backend is accessible at {self.infrainsights_config.base_url}"
            else:
                logger.warning("❌ InfraInsights backend health check failed")
                return False, f"InfraInsights backend at {self.infrainsights_config.base_url} is not accessible"
        except Exception as e:
            logger.error(f"🔍 Prerequisites check failed: {str(e)}")
            # Still allow toolset to load even if health check fails
            return True, f"InfraInsights backend health check failed: {str(e)} (toolset still enabled)"
    
    def get_example_config(self) -> Dict[str, Any]:
        """Return example configuration for this toolset"""
        return {
            "config": {
                "infrainsights_url": "http://k8s-ui-service.monitoring:5000",
                "api_key": "your-api-key-here",
                "timeout": 30,
                "enable_name_lookup": True,
                "use_v2_api": True
            }
        } 
