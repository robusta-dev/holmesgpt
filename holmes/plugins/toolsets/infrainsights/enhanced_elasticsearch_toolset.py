import json
import logging
from typing import Dict, Any
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult

logger = logging.getLogger(__name__)


class ElasticsearchHealthCheckTool(Tool):
    """Tool to check Elasticsearch cluster health"""
    
    name = "elasticsearch_health_check"
    description = "Check the health status of an Elasticsearch cluster"
    parameters = {
        "instance_name": {
            "type": "string",
            "description": "Name of the Elasticsearch instance to check",
            "required": True
        }
    }
    
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
            
            logger.info(f"🔍 Checking health for Elasticsearch instance: {instance_name}")
            
            # Get instance configuration from toolset
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Resolve instance
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                instance_name, "elasticsearch"
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch instance '{instance_name}' not found",
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
    """Tool to list Elasticsearch indices"""
    
    name = "elasticsearch_list_indices"
    description = "List all indices in an Elasticsearch cluster"
    parameters = {
        "instance_name": {
            "type": "string", 
            "description": "Name of the Elasticsearch instance",
            "required": True
        }
    }
    
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
            
            logger.info(f"🔍 Listing indices for Elasticsearch instance: {instance_name}")
            
            # Get instance configuration from toolset
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Resolve instance
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                instance_name, "elasticsearch"
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Elasticsearch instance '{instance_name}' not found",
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


class EnhancedElasticsearchToolset:
    """Enhanced Elasticsearch toolset with InfraInsights integration"""
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2
        from .base_toolset_v2 import InfraInsightsConfig
        
        # Initialize InfraInsights client
        self.infrainsights_config = InfraInsightsConfig()
        self.infrainsights_client = InfraInsightsClientV2(self.infrainsights_config)
        
        # Create tools
        self.tools = [
            ElasticsearchHealthCheckTool(toolset=self),
            ElasticsearchListIndicesTool(toolset=self)
        ]
        
        # Toolset metadata
        self.name = "infrainsights_elasticsearch_enhanced"
        self.description = "Enhanced Elasticsearch toolset with InfraInsights instance management"
        self.enabled = True
        self.tags = ["cluster"]
        self.prerequisites = []
        self.config = None 
