import json
import logging
from typing import Dict, Any, Optional
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite, ToolParameter

logger = logging.getLogger(__name__)


class RedisHealthCheckTool(Tool):
    """Tool to check Redis instance health and server information"""
    
    name: str = "redis_health_check"
    description: str = "Check the health status of a Redis instance including server info, memory usage, and connectivity"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to check",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    additional_instructions: str = ""
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
        self.additional_instructions = ""
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Checking health for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            health_data = self.toolset.infrainsights_client.get_redis_health(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=health_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error checking Redis health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Redis health: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_health_check(instance_name={instance_name})"


class EnhancedRedisToolset(Toolset):
    """Enhanced Redis toolset with InfraInsights integration for comprehensive database monitoring and analysis."""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2, InfraInsightsConfig
        
        logger.info("🚀🚀🚀 CREATING ENHANCED REDIS TOOLSET 🚀🚀🚀")

        # 1. Create the list of Tool objects first, initializing toolset to None.
        tools = [
            RedisHealthCheckTool(toolset=None),
            # You can add other Redis tools here in the future
            # e.g., RedisPerformanceMetricsTool(toolset=None)
        ]

        # 2. Initialize the parent Toolset with the list of tools.
        super().__init__(
            name="infrainsights_redis_enhanced",
            description="Enhanced Redis toolset with InfraInsights instance management.",
            enabled=True,
            tools=tools,  # Pass the list of Tool objects here
            tags=[ToolsetTag.CLUSTER],
            prerequisites=[]
        )
        
        # 3. Initialize the InfraInsights client with a default configuration.
        self.infrainsights_config = InfraInsightsConfig(
            base_url="http://localhost:3000",
            api_key=None,
            username=None,
            password=None,
            timeout=30,
            enable_name_lookup=True,
            use_v2_api=True
        )
        self.infrainsights_client = InfraInsightsClientV2(self.infrainsights_config)
        
        logger.info(f"🔧 Initialized with default URL: {self.infrainsights_config.base_url}")
        
        # 4. Now, assign the toolset instance to each tool.
        for tool in self.tools:
            tool.toolset = self
            
        # 5. Set the toolset's main config to None initially.
        self.config = None
        
        logger.info("✅✅✅ ENHANCED REDIS TOOLSET CREATED SUCCESSFULLY ✅✅✅")

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with the provided configuration"""
        logger.info(f"🚀🚀🚀 CONFIGURING ENHANCED REDIS TOOLSET 🚀🚀🚀")
        logger.info(f"🔧 Config received: {config}")
        
        self.config = config
        
        if isinstance(config, dict) and 'config' in config:
            infrainsights_config = config['config']
            logger.info(f"🔧 Using nested config structure: {infrainsights_config}")
        elif isinstance(config, dict):
            infrainsights_config = config
            logger.info(f"🔧 Using flat config structure: {infrainsights_config}")
        else:
            logger.warning(f"🔧 Unexpected config type: {type(config)}, using defaults")
            infrainsights_config = {}
        
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
        
        self.infrainsights_config.base_url = base_url
        self.infrainsights_config.api_key = api_key
        self.infrainsights_config.timeout = timeout
        self.infrainsights_config.enable_name_lookup = enable_name_lookup
        self.infrainsights_config.use_v2_api = use_v2_api
        
        from .infrainsights_client_v2 import InfraInsightsClientV2
        self.infrainsights_client = InfraInsightsClientV2(self.infrainsights_config)
        
        self.prerequisites = [CallablePrerequisite(callable=self._check_prerequisites)]
        
        logger.info(f"✅✅✅ ENHANCED REDIS TOOLSET CONFIGURED WITH URL: {base_url} ✅✅✅")
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if InfraInsights client can connect to the backend"""
        try:
            logger.info(f"🔍 Checking prerequisites for InfraInsights Redis client")
            logger.info(f"🔍 Current base_url: {self.infrainsights_config.base_url}")
            logger.info(f"🔍 API key configured: {'Yes' if self.infrainsights_config.api_key else 'No'}")
            
            if self.infrainsights_client.health_check():
                logger.info("✅ InfraInsights backend health check passed")
                return True, f"InfraInsights backend is accessible at {self.infrainsights_config.base_url}"
            else:
                logger.warning("❌ InfraInsights backend health check failed")
                return False, f"InfraInsights backend at {self.infrainsights_config.base_url} is not accessible"
        except Exception as e:
            logger.error(f"🔍 Prerequisites check failed: {str(e)}")
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