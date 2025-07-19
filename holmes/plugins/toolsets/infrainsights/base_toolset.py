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
        # Check if instance_id is explicitly provided
        instance_id = params.get('instance_id')
        if instance_id:
            return self.toolset.get_instance_by_id(instance_id)
        
        # Check if instance_name is provided
        instance_name = params.get('instance_name')
        if instance_name:
            return self.toolset.get_instance_by_name(instance_name)
        
        # Try to identify from prompt
        prompt = params.get('prompt', '')
        if prompt:
            instance = self.toolset.identify_instance_from_prompt(prompt)
            if instance:
                return instance
        
        # Get current user context
        user_id = params.get('user_id')
        if user_id:
            instance = self.toolset.get_current_user_instance(user_id)
            if instance:
                return instance
        
        # Fallback to first available instance
        instances = self.toolset.get_available_instances()
        if instances:
            return instances[0]
        
        raise Exception("No service instance available or specified")
    
    def get_connection_config(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get connection configuration for a service instance"""
        return self.toolset.get_connection_config(instance.instanceId)
    
    def get_infrainsights_client(self) -> InfraInsightsClient:
        """Get InfraInsights client from toolset config"""
        config = self.toolset.config or {}
        infrainsights_config = InfraInsightsConfig(
            base_url=config.get('infrainsights_url', 'http://localhost:3000'),
            api_key=config.get('api_key'),
            username=config.get('username'),
            password=config.get('password'),
            timeout=config.get('timeout', 30)
        )
        return InfraInsightsClient(infrainsights_config)


class BaseInfraInsightsToolset(Toolset):
    """Base class for all InfraInsights toolsets"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if not config:
            config = {}
        
        # Initialize with required fields
        super().__init__(
            name=f"InfraInsights {self.get_service_type().title()}",
            description=f"Tools for investigating {self.get_service_type()} instances managed by InfraInsights",
            tools=[],  # Will be set by subclasses
            enabled=True,
            tags=[ToolsetTag.CLUSTER],
            config=config
        )
        
        self.service_type = self.get_service_type()
        self._instances_cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    @abstractmethod
    def get_service_type(self) -> str:
        """Return the service type this toolset handles"""
        pass
    
    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if the toolset prerequisites are met"""
        try:
            # Create a temporary client to check prerequisites
            infrainsights_config = InfraInsightsConfig(
                base_url=config.get('infrainsights_url', 'http://localhost:3000'),
                api_key=config.get('api_key'),
                username=config.get('username'),
                password=config.get('password'),
                timeout=config.get('timeout', 30)
            )
            client = InfraInsightsClient(infrainsights_config)
            
            # Check if InfraInsights API is accessible
            if not client.health_check():
                return False, "InfraInsights API is not accessible"
            
            # Check if we can get service instances
            instances = client.get_service_instances(self.service_type)
            if not instances:
                return False, f"No {self.service_type} instances available"
            
            return True, "Prerequisites met"
        except Exception as e:
            return False, f"Failed to check prerequisites: {str(e)}"
    
    def get_available_instances(self) -> List[ServiceInstance]:
        """Get all available instances for this service type"""
        # This method will be called from tools, so we need to create a client
        if not self.tools:
            return []
        
        # Use the first tool to get the client
        first_tool = self.tools[0]
        if hasattr(first_tool, 'get_infrainsights_client'):
            client = first_tool.get_infrainsights_client()
            return client.get_service_instances(self.service_type)
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
            context = client.get_user_context(user_id, self.service_type)
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
        
        # Use the first tool to get the client
        first_tool = self.tools[0]
        if hasattr(first_tool, 'get_infrainsights_client'):
            client = first_tool.get_infrainsights_client()
            return client.identify_instance_from_prompt(prompt, self.service_type, user_id)
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
            return client.set_user_context(user_id, self.service_type, instance_id)
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
        
        return f"""
        This toolset provides tools for interacting with {self.service_type} instances managed by InfraInsights.
        
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