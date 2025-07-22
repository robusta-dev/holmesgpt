"""
InfraInsights Plugin for HolmesGPT

Provides centralized instance resolution, credential management, and environment configuration
for generic toolsets. This plugin bridges HolmesGPT with the InfraInsights multi-instance platform.
"""

import os
import logging
import re
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

# Import the existing InfraInsights client
from .toolsets.infrainsights.infrainsights_client import InfraInsightsClient, InfraInsightsConfig

logger = logging.getLogger(__name__)

@dataclass
class InstanceResolutionResult:
    """Result of instance resolution attempt"""
    success: bool
    instance: Any = None
    error_message: str = ""
    resolution_strategy: str = ""

class InfraInsightsPlugin:
    """
    Central plugin for InfraInsights integration.
    Handles instance discovery, credential management, and context setting.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the InfraInsights plugin.
        
        Args:
            config: Configuration dictionary with InfraInsights connection details
        """
        self.config = config
        self.client = self._create_client(config)
        self.active_instances = {}  # Cache for active instances
        
        # Instance name patterns for fuzzy matching
        self.instance_patterns = [
            # Environment-based patterns
            r'(\w+(?:-\w+)*?)[-_]?(staging|stage|prod|production|dev|development|test|testing)',
            # Direct instance references
            r'([\w-]+)(?:\s+(?:instance|cluster|environment))',
            r'(?:instance|cluster)\s+([\w-]+)',
            r'my\s+([\w-]+)\s+(?:instance|cluster)',
            # Service-specific patterns
            r'(\w+(?:-\w+)*?)[-_]?(elasticsearch|kafka|mongodb|redis|k8s|kubernetes)',
            # General word patterns (fallback)
            r'(\w+(?:-\w+){2,})',  # Words with multiple hyphens
        ]
        
        logger.info("🔌 InfraInsights Plugin initialized")
    
    def _create_client(self, config: Dict[str, Any]) -> InfraInsightsClient:
        """Create InfraInsights client from config"""
        infrainsights_config = InfraInsightsConfig(
            base_url=config.get('infrainsights_url', 'http://localhost:3000'),
            api_key=config.get('api_key'),
            username=config.get('username'),
            password=config.get('password'),
            timeout=config.get('timeout', 30)
        )
        return InfraInsightsClient(infrainsights_config)
    
    def resolve_and_set_instance(self, service_type: str, instance_hint: str, user_id: str = None) -> InstanceResolutionResult:
        """
        Resolve instance from hint and set environment variables for generic toolsets.
        
        Args:
            service_type: elasticsearch, kafka, mongodb, redis, kubernetes, kafkaconnect
            instance_hint: Instance name hint from user prompt
            user_id: User ID for context (optional)
            
        Returns:
            InstanceResolutionResult: Result of the resolution attempt
        """
        logger.info(f"🔍 Resolving {service_type} instance from hint: '{instance_hint}'")
        
        try:
            # Strategy 1: Try exact match first
            result = self._find_instance_exact(service_type, instance_hint)
            if result.success:
                self._set_toolset_environment(service_type, result.instance)
                self.active_instances[service_type] = result.instance
                logger.info(f"✅ Exact match found for {service_type}: {result.instance.name}")
                return result
            
            # Strategy 2: Try fuzzy matching
            result = self._find_instance_fuzzy(service_type, instance_hint)
            if result.success:
                self._set_toolset_environment(service_type, result.instance)
                self.active_instances[service_type] = result.instance
                logger.info(f"✅ Fuzzy match found for {service_type}: {result.instance.name}")
                return result
            
            # Strategy 3: Try user context if available
            if user_id:
                result = self._get_user_default_instance(service_type, user_id)
                if result.success:
                    self._set_toolset_environment(service_type, result.instance)
                    self.active_instances[service_type] = result.instance
                    logger.info(f"✅ User default found for {service_type}: {result.instance.name}")
                    return result
            
            # Strategy 4: Fall back to first available instance
            result = self._get_first_available_instance(service_type)
            if result.success:
                self._set_toolset_environment(service_type, result.instance)
                self.active_instances[service_type] = result.instance
                logger.info(f"✅ First available instance used for {service_type}: {result.instance.name}")
                return result
            
            # All strategies failed
            error_msg = f"No {service_type} instance found for hint: '{instance_hint}'"
            logger.error(f"❌ {error_msg}")
            return InstanceResolutionResult(
                success=False,
                error_message=error_msg,
                resolution_strategy="all_failed"
            )
                
        except Exception as e:
            error_msg = f"Failed to resolve {service_type} instance: {str(e)}"
            logger.error(error_msg)
            return InstanceResolutionResult(
                success=False,
                error_message=error_msg,
                resolution_strategy="exception"
            )
    
    def _find_instance_exact(self, service_type: str, instance_hint: str) -> InstanceResolutionResult:
        """Find instance by exact name match"""
        try:
            instances = self.client.get_service_instances(service_type)
            exact_match = next((i for i in instances if i.name == instance_hint), None)
            
            if exact_match:
                return InstanceResolutionResult(
                    success=True,
                    instance=exact_match,
                    resolution_strategy="exact_match"
                )
            else:
                return InstanceResolutionResult(
                    success=False,
                    error_message=f"No exact match found for '{instance_hint}'",
                    resolution_strategy="exact_match"
                )
        except Exception as e:
            return InstanceResolutionResult(
                success=False,
                error_message=f"Error in exact matching: {str(e)}",
                resolution_strategy="exact_match"
            )
    
    def _find_instance_fuzzy(self, service_type: str, instance_hint: str) -> InstanceResolutionResult:
        """Find instance by fuzzy matching (contains, environment, etc.)"""
        try:
            instances = self.client.get_service_instances(service_type)
            hint_lower = instance_hint.lower()
            
            # Try various fuzzy matching strategies
            strategies = [
                # Strategy 1: Contains match
                ("contains_name", lambda i: hint_lower in i.name.lower()),
                # Strategy 2: Environment match
                ("environment_match", lambda i: hint_lower in i.environment.lower()),
                # Strategy 3: Tags match
                ("tags_match", lambda i: any(hint_lower in tag.lower() for tag in (i.tags or []))),
                # Strategy 4: Reversed contains (instance name contains hint)
                ("reverse_contains", lambda i: i.name.lower() in hint_lower),
                # Strategy 5: Pattern matching
                ("pattern_match", lambda i: self._pattern_match(hint_lower, i.name.lower())),
            ]
            
            for strategy_name, matcher in strategies:
                matches = [i for i in instances if matcher(i)]
                if matches:
                    # Prefer active instances
                    active_matches = [i for i in matches if i.status == 'active']
                    best_match = active_matches[0] if active_matches else matches[0]
                    
                    return InstanceResolutionResult(
                        success=True,
                        instance=best_match,
                        resolution_strategy=f"fuzzy_{strategy_name}"
                    )
            
            return InstanceResolutionResult(
                success=False,
                error_message=f"No fuzzy match found for '{instance_hint}'",
                resolution_strategy="fuzzy_match"
            )
            
        except Exception as e:
            return InstanceResolutionResult(
                success=False,
                error_message=f"Error in fuzzy matching: {str(e)}",
                resolution_strategy="fuzzy_match"
            )
    
    def _pattern_match(self, hint: str, instance_name: str) -> bool:
        """Check if hint matches instance name using patterns"""
        for pattern in self.instance_patterns:
            # Extract the main part from both hint and instance name
            hint_match = re.search(pattern, hint, re.IGNORECASE)
            instance_match = re.search(pattern, instance_name, re.IGNORECASE)
            
            if hint_match and instance_match:
                # Compare the extracted parts
                hint_part = hint_match.group(1).lower()
                instance_part = instance_match.group(1).lower()
                
                if hint_part in instance_part or instance_part in hint_part:
                    return True
        
        return False
    
    def _get_user_default_instance(self, service_type: str, user_id: str) -> InstanceResolutionResult:
        """Get user's default instance for service type"""
        try:
            instance = self.client.get_user_default_instance(service_type, user_id)
            if instance:
                return InstanceResolutionResult(
                    success=True,
                    instance=instance,
                    resolution_strategy="user_default"
                )
            else:
                return InstanceResolutionResult(
                    success=False,
                    error_message=f"No user default instance for {service_type}",
                    resolution_strategy="user_default"
                )
        except Exception as e:
            return InstanceResolutionResult(
                success=False,
                error_message=f"Error getting user default: {str(e)}",
                resolution_strategy="user_default"
            )
    
    def _get_first_available_instance(self, service_type: str) -> InstanceResolutionResult:
        """Get first available active instance"""
        try:
            instances = self.client.get_service_instances(service_type)
            active_instances = [i for i in instances if i.status == 'active']
            
            if active_instances:
                return InstanceResolutionResult(
                    success=True,
                    instance=active_instances[0],
                    resolution_strategy="first_available"
                )
            elif instances:  # Fall back to any instance
                return InstanceResolutionResult(
                    success=True,
                    instance=instances[0],
                    resolution_strategy="first_any"
                )
            else:
                return InstanceResolutionResult(
                    success=False,
                    error_message=f"No {service_type} instances available",
                    resolution_strategy="first_available"
                )
        except Exception as e:
            return InstanceResolutionResult(
                success=False,
                error_message=f"Error getting available instances: {str(e)}",
                resolution_strategy="first_available"
            )
    
    def _set_toolset_environment(self, service_type: str, instance: Any):
        """Set environment variables for generic toolsets to use"""
        
        try:
            connection_details = getattr(instance, 'connection_details', {}) or {}
            
            if service_type == 'elasticsearch':
                os.environ['ELASTICSEARCH_URL'] = connection_details.get('url', '')
                os.environ['ELASTICSEARCH_USERNAME'] = connection_details.get('username', '')
                os.environ['ELASTICSEARCH_PASSWORD'] = connection_details.get('password', '')
                os.environ['ELASTICSEARCH_API_KEY'] = connection_details.get('api_key', '')
                
            elif service_type == 'kafka':
                os.environ['KAFKA_BOOTSTRAP_SERVERS'] = connection_details.get('bootstrap_servers', '')
                os.environ['KAFKA_USERNAME'] = connection_details.get('username', '')
                os.environ['KAFKA_PASSWORD'] = connection_details.get('password', '')
                os.environ['KAFKA_SECURITY_PROTOCOL'] = connection_details.get('security_protocol', 'PLAINTEXT')
                os.environ['KAFKA_SASL_MECHANISM'] = connection_details.get('sasl_mechanism', 'PLAIN')
                
            elif service_type == 'mongodb':
                os.environ['MONGODB_URI'] = connection_details.get('connection_string', '')
                os.environ['MONGODB_USERNAME'] = connection_details.get('username', '')
                os.environ['MONGODB_PASSWORD'] = connection_details.get('password', '')
                os.environ['MONGODB_HOST'] = connection_details.get('host', '')
                os.environ['MONGODB_PORT'] = str(connection_details.get('port', 27017))
                
            elif service_type == 'redis':
                os.environ['REDIS_HOST'] = connection_details.get('host', '')
                os.environ['REDIS_PORT'] = str(connection_details.get('port', 6379))
                os.environ['REDIS_PASSWORD'] = connection_details.get('password', '')
                os.environ['REDIS_DB'] = str(connection_details.get('database', 0))
                os.environ['REDIS_USERNAME'] = connection_details.get('username', '')
                
            elif service_type == 'kubernetes':
                os.environ['KUBECONFIG'] = connection_details.get('kubeconfig_path', '')
                os.environ['KUBERNETES_CLUSTER_URL'] = connection_details.get('cluster_url', '')
                os.environ['KUBERNETES_TOKEN'] = connection_details.get('token', '')
                os.environ['KUBERNETES_NAMESPACE'] = connection_details.get('namespace', 'default')
                
            elif service_type == 'kafkaconnect':
                os.environ['KAFKA_CONNECT_URL'] = connection_details.get('url', '')
                os.environ['KAFKA_CONNECT_USERNAME'] = connection_details.get('username', '')
                os.environ['KAFKA_CONNECT_PASSWORD'] = connection_details.get('password', '')
            
            # Set common instance metadata
            os.environ['CURRENT_INSTANCE_NAME'] = getattr(instance, 'name', 'unknown')
            os.environ['CURRENT_INSTANCE_ENVIRONMENT'] = getattr(instance, 'environment', 'unknown')
            os.environ['CURRENT_INSTANCE_ID'] = getattr(instance, 'id', 'unknown')
            os.environ['CURRENT_SERVICE_TYPE'] = service_type
            
            logger.info(f"🔧 Environment configured for {service_type} toolset with instance: {instance.name}")
            
        except Exception as e:
            logger.error(f"Failed to set environment for {service_type}: {str(e)}")
            raise
    
    def get_active_instance(self, service_type: str) -> Optional[Any]:
        """Get the currently active instance for a service type"""
        return self.active_instances.get(service_type)
    
    def clear_instance(self, service_type: str):
        """Clear the active instance for a service type"""
        if service_type in self.active_instances:
            del self.active_instances[service_type]
        
        # Clear related environment variables
        env_prefixes = {
            'elasticsearch': 'ELASTICSEARCH_',
            'kafka': 'KAFKA_',
            'mongodb': 'MONGODB_',
            'redis': 'REDIS_',
            'kubernetes': 'KUBERNETES_',
            'kafkaconnect': 'KAFKA_CONNECT_'
        }
        
        prefix = env_prefixes.get(service_type, '')
        if prefix:
            keys_to_remove = [key for key in os.environ.keys() if key.startswith(prefix)]
            for key in keys_to_remove:
                del os.environ[key]
        
        # Clear common metadata
        for key in ['CURRENT_INSTANCE_NAME', 'CURRENT_INSTANCE_ENVIRONMENT', 'CURRENT_INSTANCE_ID', 'CURRENT_SERVICE_TYPE']:
            if key in os.environ:
                del os.environ[key]
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get diagnostic information about the plugin state"""
        return {
            "plugin_status": "active",
            "infrainsights_url": self.config.get('infrainsights_url'),
            "active_instances": {
                service: {
                    "name": instance.name,
                    "environment": instance.environment,
                    "status": instance.status
                }
                for service, instance in self.active_instances.items()
            },
            "environment_variables": {
                key: "***" if any(secret in key.lower() for secret in ['password', 'token', 'key']) else value
                for key, value in os.environ.items()
                if any(key.startswith(prefix) for prefix in ['ELASTICSEARCH_', 'KAFKA_', 'MONGODB_', 'REDIS_', 'KUBERNETES_', 'KAFKA_CONNECT_', 'CURRENT_'])
            }
        }

# Global plugin instance
_infrainsights_plugin = None

def get_infrainsights_plugin(config: Dict[str, Any] = None) -> InfraInsightsPlugin:
    """Get the global InfraInsights plugin instance"""
    global _infrainsights_plugin
    
    if _infrainsights_plugin is None and config:
        _infrainsights_plugin = InfraInsightsPlugin(config)
    elif _infrainsights_plugin is None:
        # Try to get config from environment or default
        default_config = {
            'infrainsights_url': os.getenv('INFRAINSIGHTS_URL', 'http://k8s-ui-service.monitoring:5000'),
            'api_key': os.getenv('INFRAINSIGHTS_API_KEY'),
            'timeout': int(os.getenv('INFRAINSIGHTS_TIMEOUT', '30'))
        }
        _infrainsights_plugin = InfraInsightsPlugin(default_config)
    
    return _infrainsights_plugin

def resolve_instance_for_toolset(service_type: str, instance_hint: str, user_id: str = None, config: Dict[str, Any] = None) -> InstanceResolutionResult:
    """
    Convenience function for toolsets to resolve and set instance context.
    
    Usage in generic toolsets:
        from holmes.plugins.infrainsights_plugin import resolve_instance_for_toolset
        
        result = resolve_instance_for_toolset('elasticsearch', 'dock-atlantic-staging')
        if not result.success:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Could not resolve Elasticsearch instance: {result.error_message}"
            )
    
    Args:
        service_type: The service type (elasticsearch, kafka, etc.)
        instance_hint: Instance name hint from prompt
        user_id: User ID for context (optional)
        config: Plugin configuration (optional, uses default if not provided)
    
    Returns:
        InstanceResolutionResult: Result of the resolution attempt
    """
    plugin = get_infrainsights_plugin(config)
    return plugin.resolve_and_set_instance(service_type, instance_hint, user_id)

def get_active_instance_info(service_type: str) -> Optional[Dict[str, str]]:
    """
    Get information about the currently active instance for a service type.
    
    Returns:
        dict: Instance information or None if no active instance
    """
    plugin = get_infrainsights_plugin()
    instance = plugin.get_active_instance(service_type)
    
    if instance:
        return {
            "name": getattr(instance, 'name', 'unknown'),
            "environment": getattr(instance, 'environment', 'unknown'),
            "status": getattr(instance, 'status', 'unknown'),
            "id": getattr(instance, 'id', 'unknown')
        }
    
    return None

def clear_active_instance(service_type: str):
    """Clear the active instance for a service type"""
    plugin = get_infrainsights_plugin()
    plugin.clear_instance(service_type) 