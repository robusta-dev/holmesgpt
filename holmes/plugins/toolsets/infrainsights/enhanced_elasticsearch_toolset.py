import json
import logging
from typing import Dict, Any, Optional
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite

logger = logging.getLogger(__name__)


class ElasticsearchHealthCheckTool(Tool):
    """Tool to check Elasticsearch cluster health"""
    
    name: str = "elasticsearch_health_check"
    description: str = "Check the health status of an Elasticsearch cluster"
    parameters: Dict[str, Any] = {
        "instance_name": {
            "type": "string",
            "description": "Name of the Elasticsearch instance to check",
            "required": True
        }
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
    
    name: str = "elasticsearch_list_indices"
    description: str = "List all indices in an Elasticsearch cluster"
    parameters: Dict[str, Any] = {
        "instance_name": {
            "type": "string", 
            "description": "Name of the Elasticsearch instance",
            "required": True
        }
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


class EnhancedElasticsearchToolset(Toolset):
    """Enhanced Elasticsearch toolset with InfraInsights integration"""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2
        from .base_toolset_v2 import InfraInsightsConfig
        
        logger.info("🔧 Creating EnhancedElasticsearchToolset instance")
        
        # Create tools first
        tools = [
            ElasticsearchHealthCheckTool(toolset=None),  # Will set toolset after initialization
            ElasticsearchListIndicesTool(toolset=None)
        ]
        
        # Initialize Toolset with required parameters
        super().__init__(
            name="infrainsights_elasticsearch_enhanced",
            description="Enhanced Elasticsearch toolset with InfraInsights instance management",
            enabled=True,
            tools=tools,
            tags=[ToolsetTag.CLUSTER],
            prerequisites=[
                CallablePrerequisite(callable=self._check_prerequisites)
            ]
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
        
        logger.info("✅ EnhancedElasticsearchToolset instance created successfully")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with the provided configuration"""
        logger.info(f"🔧 Configuring EnhancedElasticsearchToolset with config: {config}")
        
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
        
        logger.info(f"✅ EnhancedElasticsearchToolset configured successfully with URL: {base_url}")
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if InfraInsights client can connect to the backend"""
        try:
            logger.info(f"🔍 Checking prerequisites for InfraInsights client")
            logger.info(f"🔍 Current base_url: {self.infrainsights_config.base_url}")
            
            # Skip health check if still using default localhost (configuration not applied yet)
            if self.infrainsights_config.base_url == "http://localhost:3000":
                logger.info("🔍 Using default localhost URL, assuming configuration will be applied later")
                return True, "InfraInsights configuration pending"
            
            # Try to connect to InfraInsights backend
            if self.infrainsights_client.health_check():
                return True, "InfraInsights backend is accessible"
            else:
                return False, "InfraInsights backend is not accessible"
        except Exception as e:
            logger.warning(f"🔍 Prerequisites check failed: {str(e)}")
            # Don't fail completely - allow toolset to load even if health check fails
            return True, f"InfraInsights backend health check failed: {str(e)}"
    
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
