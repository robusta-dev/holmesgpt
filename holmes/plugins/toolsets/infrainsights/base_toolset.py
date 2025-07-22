"""
Base Toolset for InfraInsights Toolsets

This provides common functionality for all InfraInsights toolsets including
instance discovery, credential management, and user context handling.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from abc import abstractmethod

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import TOOLSET_CONFIG_MISSING_ERROR

from .infrainsights_client import InfraInsightsClient, InfraInsightsConfig, ServiceInstance


class BaseInfraInsightsTool(Tool):
    """Base class for all InfraInsights tools"""
    toolset: "BaseInfraInsightsToolset"
    
    def get_instance_from_params(self, params: Dict[str, Any]) -> ServiceInstance:
        """Get service instance from parameters or user context"""
        service_type = self.toolset.get_service_type()
        
        # Check if instance_id is explicitly provided
        instance_id = params.get('instance_id')
        if instance_id:
            try:
                return self.toolset.get_instance_by_id(instance_id)
            except Exception as e:
                logging.warning(f"Failed to get instance by ID {instance_id}: {str(e)}")
        
        # Check if instance_name is provided
        instance_name = params.get('instance_name')
        if instance_name:
            try:
                return self.toolset.get_instance_by_name(instance_name)
            except Exception as e:
                logging.warning(f"Failed to get instance by name {instance_name}: {str(e)}")
        
        # Try to identify from prompt
        prompt = params.get('prompt', '')
        user_id = params.get('user_id')
        if prompt:
            instance = self.toolset.identify_instance_from_prompt(prompt, user_id)
            if instance:
                return instance
        
        # Get current user context
        if user_id:
            instance = self.toolset.get_current_user_instance(user_id)
            if instance:
                return instance
        
        # Fallback to first available instance
        instances = self.toolset.get_available_instances()
        if instances:
            logging.info(f"Using first available {service_type} instance: {instances[0].name}")
            return instances[0]
        
        # More informative error message with suggestions
        error_msg = f"""No {service_type} instance available or specified.
        
Possible solutions:
1. Ensure InfraInsights API is accessible at the configured URL
2. Check that {service_type} instances are configured in InfraInsights
3. Verify authentication credentials are correct
4. Specify instance explicitly using 'instance_id' or 'instance_name' parameter
5. Set user context for {service_type} service type

Debug: Check InfraInsights dashboard for available {service_type} instances."""
        
        raise Exception(error_msg)
    
    def get_connection_config(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get connection configuration for a service instance"""
        return self.toolset.get_connection_config(instance.instanceId)
    
    def get_infrainsights_client(self) -> InfraInsightsClient:
        """Get InfraInsights client from toolset config"""
        config = self.toolset.infrainsights_config or {}
        infrainsights_config = InfraInsightsConfig(
            base_url=config.get('infrainsights_url', 'http://localhost:3000'),
            api_key=config.get('api_key'),
            username=config.get('username'),
            password=config.get('password'),
            timeout=config.get('timeout', 30)
        )
        return InfraInsightsClient(infrainsights_config)
    
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
    
    def get_helpful_error_message(self, original_error: str) -> str:
        """Get a helpful error message for users when investigation fails"""
        service_type = self.toolset.get_service_type()
        config = self.toolset.infrainsights_config or {}
        api_url = config.get('infrainsights_url', 'Not configured')
        
        return f"""Investigation failed for {service_type} service: {original_error}

This typically means one of the following:

🔍 **Troubleshooting Steps:**

1. **Check InfraInsights API Status**
   - URL: {api_url}
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


class BaseInfraInsightsToolset(Toolset):
    """Base class for all InfraInsights toolsets"""
    
    # Declare as a proper Pydantic field to avoid "no field" error
    infrainsights_config: Optional[Dict[str, Any]] = None
    
    def __init__(self):
        # Initialize with required fields
        super().__init__(
            name=f"InfraInsights {self.get_service_type().title()}",
            description=f"Tools for investigating {self.get_service_type()} instances managed by InfraInsights",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[],  # Will be set by subclasses
            enabled=True,
            tags=[ToolsetTag.CLUSTER],
        )
    
    @abstractmethod
    def get_service_type(self) -> str:
        """Return the service type this toolset handles"""
        pass
    
    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if the toolset prerequisites are met"""
        print("DEBUG: InfraInsights toolset config received:", config)
        
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR
            
        try:
            # Store config for later use
            self.infrainsights_config = config
            
            # Basic config validation - don't make network calls during initialization
            infrainsights_url = config.get('infrainsights_url')
            api_key = config.get('api_key')
            username = config.get('username')
            password = config.get('password')
            
            # Check that we have either API key or username/password
            has_api_key = bool(api_key)
            has_credentials = bool(username and password)
            
            if not infrainsights_url:
                return False, "InfraInsights URL is required"
            
            if not (has_api_key or has_credentials):
                return False, "Either API key or username/password is required"
            
            # Don't check API accessibility during initialization
            # This will be checked lazily when tools are actually invoked
            logging.info(f"✅ Toolset {self.name}: Configuration validated (will check connectivity when needed)")
            return True, "Configuration validated"
            
        except Exception as e:
            return False, f"Failed to validate configuration: {str(e)}"
    
    def get_available_instances(self) -> List[ServiceInstance]:
        """Get all available instances for this service type"""
        # This method will be called from tools, so we need to create a client
        if not self.tools:
            return []
        
        try:
            # Use the first tool to get the client
            first_tool = self.tools[0]
            if hasattr(first_tool, 'get_infrainsights_client'):
                client = first_tool.get_infrainsights_client()
                service_type = self.get_service_type()
                return client.get_service_instances(service_type)
        except Exception as e:
            logging.warning(f"Failed to get available instances for {self.get_service_type()}: {str(e)}")
            # Return empty list instead of failing - tools can handle this gracefully
        return []
    
    def get_instance_by_id(self, instance_id: str) -> ServiceInstance:
        """Get a specific instance by ID"""
        instances = self.get_available_instances()
        for instance in instances:
            if instance.instanceId == instance_id:
                return instance
        raise Exception(f"Instance {instance_id} not found")
    
    def get_instance_by_name(self, instance_name: str) -> ServiceInstance:
        """Get a specific instance by name"""
        instances = self.get_available_instances()
        for instance in instances:
            if instance.name == instance_name:
                return instance
        raise Exception(f"Instance {instance_name} not found")
    
    def get_current_user_instance(self, user_id: str) -> Optional[ServiceInstance]:
        """Get the current user's selected instance for this service type"""
        if not self.tools:
            return None
        
        # Use the first tool to get the client
        first_tool = self.tools[0]
        if hasattr(first_tool, 'get_infrainsights_client'):
            client = first_tool.get_infrainsights_client()
            service_type = self.get_service_type()
            context = client.get_user_context(user_id, service_type)
            if context and context.get('instanceId'):
                try:
                    return self.get_instance_by_id(context['instanceId'])
                except Exception:
                    return None
        return None
    
    def identify_instance_from_prompt(self, prompt: str, user_id: Optional[str] = None) -> Optional[ServiceInstance]:
        """Identify which instance the user is referring to in their prompt"""
        if not self.tools:
            return None
        
        try:
            # Use the first tool to get the client
            first_tool = self.tools[0]
            if hasattr(first_tool, 'get_infrainsights_client'):
                client = first_tool.get_infrainsights_client()
                service_type = self.get_service_type()
                return client.identify_instance_from_prompt(prompt, service_type, user_id)
        except Exception as e:
            logging.warning(f"Failed to identify instance from prompt for {self.get_service_type()}: {str(e)}")
        return None
    
    def get_connection_config(self, instance_id: str) -> Dict[str, Any]:
        """Get connection configuration for a service instance"""
        if not self.tools:
            return {}
        
        # Use the first tool to get the client
        first_tool = self.tools[0]
        if hasattr(first_tool, 'get_infrainsights_client'):
            client = first_tool.get_infrainsights_client()
            return client.get_connection_config(instance_id)
        return {}
    
    def set_user_context(self, user_id: str, instance_id: str) -> Dict[str, Any]:
        """Set the current user's context for this service type"""
        if not self.tools:
            return {}
        
        # Use the first tool to get the client
        first_tool = self.tools[0]
        if hasattr(first_tool, 'get_infrainsights_client'):
            client = first_tool.get_infrainsights_client()
            service_type = self.get_service_type()
            return client.set_user_context(user_id, service_type, instance_id)
        return {}
    
    def get_example_config(self) -> Dict[str, Any]:
        """Get example configuration for this toolset"""
        return {
            "infrainsights_url": "http://localhost:3000",
            "api_key": "your-api-key-here",
            "username": "your-username",
            "password": "your-password",
            "timeout": 30
        }
    
    def get_llm_instructions(self) -> str:
        """Get LLM instructions for this toolset"""
        instances = self.get_available_instances()
        instance_names = [inst.name for inst in instances] if instances else ["No instances available"]
        service_type = self.get_service_type()
        
        return f"""
        This toolset provides tools for interacting with {service_type} instances managed by InfraInsights.
        
        Key features:
        - Automatic instance discovery and selection
        - Multi-instance support with context switching
        - Secure credential management
        - User-specific access control
        
        When using these tools:
        1. If an instance is not explicitly specified, the tool will try to identify the appropriate instance from the user's prompt
        2. If no instance can be identified, it will use the user's current context
        3. If no context is set, it will use the first available instance
        
        Available instances: {instance_names}
        """ 