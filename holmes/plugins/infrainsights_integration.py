"""
InfraInsights Integration for HolmesGPT

This module provides the integration layer that connects the Smart Router and InfraInsights Plugin
with HolmesGPT's tool execution system, enabling automatic instance resolution and routing.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from holmes.plugins.smart_router import get_smart_router, parse_prompt_for_routing, RouteInfo
from holmes.plugins.infrainsights_plugin import (
    get_infrainsights_plugin, 
    resolve_instance_for_toolset, 
    InstanceResolutionResult
)

logger = logging.getLogger(__name__)

@dataclass
class IntegrationResult:
    """Result of integration processing"""
    success: bool
    route_info: Optional[RouteInfo] = None
    resolution_result: Optional[InstanceResolutionResult] = None
    error_message: str = ""
    should_proceed: bool = True

class InfraInsightsIntegration:
    """
    Integration layer for automatic instance resolution and tool routing.
    """
    
    def __init__(self):
        """Initialize the integration layer"""
        self.router = get_smart_router()
        self.plugin = None  # Will be initialized lazily
        logger.info("🔗 InfraInsights Integration initialized")
    
    def _get_plugin(self, config: Dict[str, Any] = None):
        """Get or initialize the InfraInsights plugin"""
        if self.plugin is None:
            self.plugin = get_infrainsights_plugin(config)
        return self.plugin
    
    def pre_execution_hook(self, 
                         tool_name: str, 
                         params: Dict[str, Any], 
                         prompt: str = "", 
                         user_id: str = None, 
                         config: Dict[str, Any] = None) -> IntegrationResult:
        """
        Pre-execution hook for tool calls.
        
        This method is called before any tool execution to:
        1. Parse the prompt for service type and instance hints
        2. Resolve the appropriate instance
        3. Set up environment variables for generic toolsets
        
        Args:
            tool_name: Name of the tool being executed
            params: Tool parameters
            prompt: Original user prompt
            user_id: User ID for context
            config: InfraInsights configuration
            
        Returns:
            IntegrationResult: Result of the integration processing
        """
        logger.info(f"🔄 Pre-execution hook for tool: {tool_name}")
        
        try:
            # Check if this tool needs InfraInsights integration
            if not self._needs_infrainsights_integration(tool_name):
                logger.info(f"⏭️ Tool {tool_name} doesn't need InfraInsights integration")
                return IntegrationResult(
                    success=True,
                    should_proceed=True
                )
            
            # Parse the prompt for routing information
            route_info = parse_prompt_for_routing(prompt)
            
            # If we have service type information, try to resolve instance
            if route_info.service_type:
                logger.info(f"🎯 Detected service: {route_info.service_type}, instance hint: {route_info.instance_hint}")
                
                # Get the plugin
                plugin = self._get_plugin(config)
                
                # Try to resolve the instance
                instance_hint = route_info.instance_hint or self._extract_instance_from_params(params)
                if not instance_hint:
                    instance_hint = "default"  # Fallback
                
                resolution_result = plugin.resolve_and_set_instance(
                    route_info.service_type, 
                    instance_hint, 
                    user_id
                )
                
                if resolution_result.success:
                    logger.info(f"✅ Instance resolved: {resolution_result.instance.name}")
                    return IntegrationResult(
                        success=True,
                        route_info=route_info,
                        resolution_result=resolution_result,
                        should_proceed=True
                    )
                else:
                    logger.warning(f"⚠️ Instance resolution failed: {resolution_result.error_message}")
                    
                    # For now, let the tool handle the error gracefully
                    # In the future, we could provide better error handling here
                    return IntegrationResult(
                        success=False,
                        route_info=route_info,
                        resolution_result=resolution_result,
                        error_message=resolution_result.error_message,
                        should_proceed=True  # Let tool handle the error
                    )
            else:
                # No service type detected, but that's okay for non-service tools
                logger.info(f"📝 No specific service type detected for tool: {tool_name}")
                return IntegrationResult(
                    success=True,
                    route_info=route_info,
                    should_proceed=True
                )
                
        except Exception as e:
            logger.error(f"❌ Pre-execution hook failed: {str(e)}")
            return IntegrationResult(
                success=False,
                error_message=f"Integration error: {str(e)}",
                should_proceed=True  # Don't block tool execution on integration errors
            )
    
    def _needs_infrainsights_integration(self, tool_name: str) -> bool:
        """
        Check if a tool needs InfraInsights integration.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            bool: True if the tool needs integration
        """
        # Define patterns for tools that need integration
        infrainsights_patterns = [
            'elasticsearch',
            'kafka',
            'mongodb', 
            'redis',
            'kubernetes',
            'kafkaconnect',
            'infrainsights'
        ]
        
        tool_lower = tool_name.lower()
        return any(pattern in tool_lower for pattern in infrainsights_patterns)
    
    def _extract_instance_from_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Extract instance hint from tool parameters"""
        instance_keys = [
            'instance_name',
            'instance_id', 
            'cluster_name',
            'cluster_id',
            'environment',
            'instance'
        ]
        
        for key in instance_keys:
            if key in params and params[key]:
                return str(params[key])
        
        return None
    
    def post_execution_hook(self, 
                          tool_name: str, 
                          params: Dict[str, Any], 
                          result: Any, 
                          integration_result: IntegrationResult) -> Any:
        """
        Post-execution hook for tool calls.
        
        This method can be used to:
        1. Log successful executions
        2. Clean up resources
        3. Modify results if needed
        
        Args:
            tool_name: Name of the executed tool
            params: Tool parameters
            result: Tool execution result
            integration_result: Result from pre-execution hook
            
        Returns:
            Any: Potentially modified result
        """
        if integration_result.resolution_result and integration_result.resolution_result.success:
            logger.info(f"✅ Tool {tool_name} executed successfully with instance: {integration_result.resolution_result.instance.name}")
        
        return result
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get diagnostic information about the integration"""
        plugin = self._get_plugin()
        
        return {
            "integration_status": "active",
            "router_status": "active",
            "plugin_info": plugin.get_diagnostic_info() if plugin else "not_initialized"
        }

# Global integration instance
_infrainsights_integration = None

def get_infrainsights_integration() -> InfraInsightsIntegration:
    """Get the global InfraInsights integration instance"""
    global _infrainsights_integration
    if _infrainsights_integration is None:
        _infrainsights_integration = InfraInsightsIntegration()
    return _infrainsights_integration

def integrate_with_tool_execution(tool_executor_class):
    """
    Decorator/function to integrate InfraInsights with tool execution.
    
    This can be used to modify HolmesGPT's tool executor to include
    automatic instance resolution.
    
    Usage:
        @integrate_with_tool_execution
        class MyToolExecutor:
            def execute_tool(self, tool_name, params, prompt=None, user_id=None):
                # Will automatically include pre/post hooks
                pass
    """
    
    integration = get_infrainsights_integration()
    
    # Store original execute method
    original_execute = tool_executor_class.execute_tool
    
    def enhanced_execute_tool(self, tool_name: str, params: Dict, prompt: str = "", user_id: str = None, config: Dict = None):
        """Enhanced tool execution with InfraInsights integration"""
        
        # Pre-execution hook
        integration_result = integration.pre_execution_hook(
            tool_name, params, prompt, user_id, config
        )
        
        if not integration_result.should_proceed:
            # Return error result if integration says not to proceed
            return {
                "status": "error",
                "error": integration_result.error_message
            }
        
        # Execute the original tool
        result = original_execute(self, tool_name, params)
        
        # Post-execution hook
        enhanced_result = integration.post_execution_hook(
            tool_name, params, result, integration_result
        )
        
        return enhanced_result
    
    # Replace the execute method
    tool_executor_class.execute_tool = enhanced_execute_tool
    
    return tool_executor_class

# Convenience functions for manual integration
def resolve_and_execute_tool(tool_name: str, 
                           params: Dict[str, Any], 
                           prompt: str = "", 
                           user_id: str = None, 
                           config: Dict[str, Any] = None):
    """
    Manually resolve instance and prepare for tool execution.
    
    This function can be used when you want to manually handle
    the integration without modifying HolmesGPT's core.
    
    Usage:
        # Before calling any Elasticsearch tool
        resolve_and_execute_tool(
            "elasticsearch_health",
            {},
            "Check health of my staging elasticsearch cluster",
            user_id="user123"
        )
        
        # Now the tool can execute with proper instance context
    """
    integration = get_infrainsights_integration()
    return integration.pre_execution_hook(tool_name, params, prompt, user_id, config)

def test_integration(prompt: str, service_type: str = None, instance_hint: str = None) -> Dict[str, Any]:
    """
    Test the integration with a given prompt.
    
    Useful for debugging and testing the routing and resolution logic.
    
    Args:
        prompt: Test prompt
        service_type: Optional override for service type
        instance_hint: Optional override for instance hint
        
    Returns:
        dict: Test results with routing and resolution information
    """
    integration = get_infrainsights_integration()
    
    # Parse the prompt
    route_info = parse_prompt_for_routing(prompt)
    
    # Override if provided
    if service_type:
        route_info.service_type = service_type
    if instance_hint:
        route_info.instance_hint = instance_hint
    
    # Test resolution
    resolution_result = None
    if route_info.service_type and route_info.instance_hint:
        plugin = integration._get_plugin()
        resolution_result = plugin.resolve_and_set_instance(
            route_info.service_type, 
            route_info.instance_hint
        )
    
    return {
        "prompt": prompt,
        "route_info": {
            "service_type": route_info.service_type,
            "instance_hint": route_info.instance_hint,
            "confidence": route_info.confidence,
            "extraction_method": route_info.extraction_method
        },
        "resolution_result": {
            "success": resolution_result.success if resolution_result else False,
            "instance_name": resolution_result.instance.name if resolution_result and resolution_result.success else None,
            "error": resolution_result.error_message if resolution_result else None,
            "strategy": resolution_result.resolution_strategy if resolution_result else None
        } if resolution_result else None,
        "diagnostic_info": integration.get_diagnostic_info()
    } 