import logging
from abc import abstractmethod
from typing import Dict, Any, Tuple, Optional, TYPE_CHECKING
from pydantic import Field
from holmes.core.tools import Tool, StructuredToolResult, ToolResultStatus
from .infrainsights_client_v2 import InfraInsightsClientV2, InfraInsightsConfig, ServiceInstance

if TYPE_CHECKING:
    from . import BaseInfraInsightsToolsetV2

logger = logging.getLogger(__name__)

class BaseInfraInsightsToolV2(Tool):
    """Base class for all InfraInsights tools with V2 API support"""
    
    # Define toolset as a proper Pydantic field
    toolset: Optional[Any] = Field(default=None, exclude=True)
    
    def __init__(self, name: str, description: str, toolset, **kwargs):
        super().__init__(name=name, description=description, toolset=toolset, **kwargs)
    
    @abstractmethod
    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        """Override this method to implement tool-specific logic"""
        pass
    
    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        """Return a one-liner description of the tool execution"""
        return f"{self.name} with params: {params}"
        
    def get_infrainsights_client(self) -> InfraInsightsClientV2:
        """Get configured InfraInsights client"""
        return self.toolset.infrainsights_client
        
    def check_api_connectivity(self) -> Tuple[bool, str]:
        """Check if InfraInsights API is accessible"""
        try:
            client = self.get_infrainsights_client()
            if client.health_check():
                return True, "API accessible"
            else:
                return False, "InfraInsights API health check failed"
        except Exception as e:
            return False, f"Failed to connect to InfraInsights API: {str(e)}"
            
    def get_instance_from_params(self, params: Dict[str, Any]) -> ServiceInstance:
        """Get service instance from parameters or user context with enhanced resolution"""
        service_type = self.toolset.get_service_type()
        client = self.get_infrainsights_client()
        
        # Extract possible identifiers from parameters
        instance_id = params.get('instance_id')
        instance_name = params.get('instance_name') 
        cluster_name = params.get('cluster_name')
        user_id = params.get('user_id')
        prompt = params.get('prompt', '')
        
        # Try various resolution strategies
        
        # Strategy 1: Direct instance ID
        if instance_id:
            try:
                instance = client.get_instance_by_id(instance_id, include_config=True)
                if instance and instance.serviceType == service_type:
                    logger.info(f"✅ Resolved by instance_id: {instance_id}")
                    return instance
            except Exception as e:
                logger.warning(f"Failed to get instance by ID {instance_id}: {str(e)}")
        
        # Strategy 2: Instance name
        if instance_name:
            try:
                instance = client.resolve_instance(service_type, instance_name, user_id)
                if instance:
                    logger.info(f"✅ Resolved by instance_name: {instance_name}")
                    return instance
            except Exception as e:
                logger.warning(f"Failed to get instance by name {instance_name}: {str(e)}")
        
        # Strategy 3: Cluster name
        if cluster_name:
            try:
                instance = client.resolve_instance(service_type, cluster_name, user_id)
                if instance:
                    logger.info(f"✅ Resolved by cluster_name: {cluster_name}")
                    return instance
            except Exception as e:
                logger.warning(f"Failed to get instance by cluster name {cluster_name}: {str(e)}")
        
        # Strategy 4: Extract from prompt
        if prompt:
            try:
                instance = client.identify_instance_from_prompt(prompt, service_type, user_id)
                if instance:
                    logger.info(f"✅ Resolved from prompt: {prompt}")
                    return instance
            except Exception as e:
                logger.warning(f"Failed to identify instance from prompt: {str(e)}")
        
        # Strategy 5: Get user's current context (if implemented)
        if user_id:
            try:
                # This would be implemented if there's a user context API
                # instance = client.get_user_current_instance(user_id, service_type)
                # if instance:
                #     logger.info(f"✅ Resolved from user context: {user_id}")
                #     return instance
                pass
            except Exception as e:
                logger.warning(f"Failed to get user context: {str(e)}")
        
        # Strategy 6: Get first available instance
        try:
            instances = client.get_service_instances(service_type, user_id)
            if instances:
                instance = instances[0]  # Use first available
                logger.info(f"✅ Using first available {service_type} instance: {instance.name}")
                return instance
        except Exception as e:
            logger.warning(f"Failed to get available instances: {str(e)}")
        
        # Generate helpful error message
        error_msg = self._generate_resolution_error_message(service_type, params)
        raise Exception(error_msg)
    
    def _generate_resolution_error_message(self, service_type: str, params: Dict[str, Any]) -> str:
        """Generate a helpful error message when instance resolution fails"""
        client = self.get_infrainsights_client()
        config = client.config
        
        # Get available instances for reference
        try:
            summary = client.get_service_instance_summary(service_type)
            available_names = summary.get('instance_names', [])
        except:
            available_names = []
        
        attempted_identifiers = []
        if params.get('instance_id'): attempted_identifiers.append(f"ID: {params['instance_id']}")
        if params.get('instance_name'): attempted_identifiers.append(f"name: {params['instance_name']}")
        if params.get('cluster_name'): attempted_identifiers.append(f"cluster: {params['cluster_name']}")
        
        attempted_str = ", ".join(attempted_identifiers) if attempted_identifiers else "No specific identifier provided"
        
        error_msg = f"""No {service_type} instance available or specified.

🔍 **Resolution Attempt Details:**
- Attempted: {attempted_str}
- Available instances: {', '.join(available_names) if available_names else 'None found'}
- API URL: {config.base_url}
- Name lookup enabled: {config.enable_name_lookup}

💡 **Possible Solutions:**

1. **Check Instance Availability**
   - Verify {service_type} instances exist in InfraInsights dashboard
   - Ensure instances are in 'active' status

2. **API Connectivity**
   - Test: curl {config.base_url}/health
   - Verify network connectivity from HolmesGPT to InfraInsights

3. **Authentication**
   - Check API key validity and permissions
   - Verify JWT token hasn't expired

4. **Specify Instance Explicitly**
   - Use exact instance name: "Check my production-elasticsearch instance"
   - Available names: {', '.join(available_names[:5]) if available_names else 'Check InfraInsights dashboard'}

5. **User Context**
   - Set default {service_type} instance in InfraInsights
   - Ensure user has access to the requested instance

🔧 **Debug Steps:**
1. Check InfraInsights dashboard for {service_type} instances
2. Test API: GET {config.base_url}/api/service-instances/{service_type}
3. Verify instance permissions for your user

Once resolved, try your query again with a specific instance name."""

        return error_msg
    
    def get_connection_config(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Extract connection configuration from service instance"""
        if not instance.config:
            raise Exception(f"No configuration available for instance {instance.name}")
            
        return instance.config
    
    def get_helpful_error_message(self, original_error: str) -> str:
        """Get a helpful error message for users when investigation fails"""
        service_type = self.toolset.get_service_type()
        client = self.get_infrainsights_client()
        config = client.config
        
        return f"""Investigation failed for {service_type} service: {original_error}

This typically means one of the following:

🔍 **Troubleshooting Steps:**

1. **Check InfraInsights API Status**
   - URL: {config.base_url}
   - Name lookup enabled: {config.enable_name_lookup}
   - Try accessing the InfraInsights dashboard to verify it's running

2. **Verify Service Instance Configuration**
   - Ensure {service_type} instances are properly configured in InfraInsights
   - Check that instances are in 'active' status

3. **Authentication Issues**
   - Verify your API key/credentials are correct and not expired
   - Check user permissions for {service_type} access

4. **Network Connectivity**
   - Ensure HolmesGPT can reach the InfraInsights API URL
   - Check firewall/proxy settings if applicable

5. **Instance Context**
   - Try specifying an instance explicitly: "Check the production {service_type} cluster"
   - Set your user context for {service_type} in InfraInsights

💡 **Quick Test:** Access InfraInsights dashboard and verify {service_type} instances are visible and accessible.

Once the issue is resolved, try your investigation query again."""


class BaseInfraInsightsToolsetV2:
    """Base class for all InfraInsights toolsets with V2 API support"""
    
    def __init__(self, name: str):
        self.name = name
        self.infrainsights_client = None
        self.infrainsights_config = None
        self.tools = []
        
    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if prerequisites are met for this toolset"""
        try:
            # Store config for later use
            self.infrainsights_config = config
            
            # Basic config validation
            infrainsights_url = config.get('infrainsights_url')
            api_key = config.get('api_key')
            username = config.get('username')
            password = config.get('password')
            enable_name_lookup = config.get('enable_name_lookup', True)
            use_v2_api = config.get('use_v2_api', True)
            
            # Check required fields
            if not infrainsights_url:
                return False, "InfraInsights URL is required"
            
            # Check authentication
            has_api_key = bool(api_key)
            has_credentials = bool(username and password)
            
            if not (has_api_key or has_credentials):
                return False, "Either API key or username/password is required"
            
            # Create client configuration
            infrainsights_config = InfraInsightsConfig(
                base_url=infrainsights_url,
                api_key=api_key,
                username=username,
                password=password,
                timeout=config.get('timeout', 30),
                enable_name_lookup=enable_name_lookup,
                use_v2_api=use_v2_api
            )
            
            # Initialize client
            self.infrainsights_client = InfraInsightsClientV2(infrainsights_config)
            
            # Don't test connectivity during initialization to avoid startup failures
            # This will be checked lazily when tools are actually invoked
            logging.info(f"✅ Toolset {self.name}: V2 client initialized with name lookup: {enable_name_lookup}")
            return True, "Configuration validated (V2 API with name resolution)"
            
        except Exception as e:
            return False, f"Failed to validate configuration: {str(e)}"
    
    def get_service_type(self) -> str:
        """Get the service type for this toolset - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement get_service_type")
    
    def get_available_instances(self) -> list:
        """Get available instances for this service type"""
        if not self.infrainsights_client:
            return []
        
        try:
            service_type = self.get_service_type()
            return self.infrainsights_client.get_service_instances(service_type)
        except Exception as e:
            logging.warning(f"Failed to get available instances for {self.get_service_type()}: {str(e)}")
            return []
    
    def get_instance_by_id(self, instance_id: str) -> ServiceInstance:
        """Get instance by ID"""
        if not self.infrainsights_client:
            raise Exception("InfraInsights client not initialized")
        
        instance = self.infrainsights_client.get_instance_by_id(instance_id, include_config=True)
        if not instance:
            raise Exception(f"Instance {instance_id} not found")
        return instance
    
    def get_instance_by_name(self, instance_name: str) -> ServiceInstance:
        """Get instance by name using the new V2 API"""
        if not self.infrainsights_client:
            raise Exception("InfraInsights client not initialized")
        
        service_type = self.get_service_type()
        instance = self.infrainsights_client.resolve_instance(service_type, instance_name)
        if not instance:
            raise Exception(f"Instance with name '{instance_name}' not found in service type '{service_type}'")
        return instance 