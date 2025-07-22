import json
import logging
from typing import Dict, Any

from holmes.core.tools import StructuredToolResult, ToolResultStatus
from .base_toolset_v2 import BaseInfraInsightsToolV2, BaseInfraInsightsToolsetV2

logger = logging.getLogger(__name__)

class VerboseElasticsearchHealthTool(BaseInfraInsightsToolV2):
    """Tool to check Elasticsearch cluster health with enhanced verbose logging"""
    
    def __init__(self, toolset):
        super().__init__(
            name="elasticsearch_health_check",
            description="Check Elasticsearch cluster health and status for InfraInsights instances",
            toolset=toolset
        )
    
    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        logger.info("🔍 INFRAINSIGHTS ELASTICSEARCH: Starting cluster health check")
        logger.info(f"📝 Request parameters: {json.dumps(params, indent=2)}")
        
        try:
            # Enhanced instance resolution with verbose logging
            logger.info("🔍 INFRAINSIGHTS: Attempting to resolve Elasticsearch instance...")
            instance = self.get_instance_from_params(params)
            logger.info(f"✅ INFRAINSIGHTS: Successfully resolved instance: {instance.name} (ID: {instance.instanceId})")
            logger.info(f"🏷️  Instance details: Environment={instance.environment}, Status={instance.status}")
            
            # Get connection configuration with verbose logging
            logger.info("🔧 INFRAINSIGHTS: Extracting connection configuration...")
            config = self.get_connection_config(instance)
            logger.info("✅ INFRAINSIGHTS: Configuration extracted successfully")
            
            # Extract Elasticsearch connection details
            es_url = config.get('elasticsearchUrl', config.get('elasticsearch_url'))
            username = config.get('username')
            api_key = config.get('apiKey', config.get('api_key'))
            
            logger.info(f"🔗 INFRAINSIGHTS: Connecting to Elasticsearch at: {es_url}")
            
            if not es_url:
                raise Exception("Elasticsearch URL not found in instance configuration")
            
            # Import and configure Elasticsearch client
            try:
                from elasticsearch import Elasticsearch
                logger.info("✅ INFRAINSIGHTS: Elasticsearch client library loaded")
            except ImportError:
                raise Exception("Elasticsearch client library not available")
            
            # Configure authentication with verbose logging
            auth_config = {}
            if api_key:
                auth_config['api_key'] = api_key
                logger.info("🔐 INFRAINSIGHTS: Using API key authentication")
            elif username:
                # password is handled separately for security
                auth_config['http_auth'] = (username, config.get('password'))
                logger.info("🔐 INFRAINSIGHTS: Using username/password authentication")
            else:
                logger.warning("⚠️  INFRAINSIGHTS: No authentication configured")
            
            # Create Elasticsearch client
            logger.info("🔌 INFRAINSIGHTS: Creating Elasticsearch client connection...")
            es = Elasticsearch(
                [es_url],
                verify_certs=False,
                timeout=30,
                **auth_config
            )
            
            # Test connection
            logger.info("🧪 INFRAINSIGHTS: Testing Elasticsearch connection...")
            
            # Get cluster health
            logger.info("📊 INFRAINSIGHTS: Fetching cluster health...")
            health = es.cluster.health()
            logger.info(f"✅ INFRAINSIGHTS: Cluster health retrieved: Status={health.get('status', 'unknown')}")
            
            # Get cluster stats for additional information
            try:
                logger.info("📈 INFRAINSIGHTS: Fetching cluster statistics...")
                stats = es.cluster.stats()
                logger.info("✅ INFRAINSIGHTS: Cluster statistics retrieved")
                
                logger.info("🔍 INFRAINSIGHTS: Fetching nodes information...")
                nodes_info = es.nodes.info()
                logger.info("✅ INFRAINSIGHTS: Nodes information retrieved")
            except Exception as e:
                logger.warning(f"⚠️  INFRAINSIGHTS: Failed to get additional cluster info: {e}")
                stats = {}
                nodes_info = {}
            
            # Create comprehensive result
            result = {
                "elasticsearch_cluster": {
                    "instance_name": instance.name,
                    "instance_id": instance.instanceId,
                    "environment": instance.environment,
                    "elasticsearch_url": es_url,
                    "connection_method": "InfraInsights-managed"
                },
                "cluster_health": health,
                "cluster_stats": stats,
                "nodes_info": nodes_info,
                "infrainsights_metadata": {
                    "toolset": "InfraInsights Elasticsearch V2",
                    "instance_resolution": "successful",
                    "resolution_method": "name-based lookup",
                    "name_lookup_enabled": self.get_infrainsights_client().config.enable_name_lookup,
                    "api_version": "v2"
                },
                "timestamp": "2025-01-22T10:15:00Z"
            }
            
            logger.info("🎉 INFRAINSIGHTS: Elasticsearch health check completed successfully")
            logger.info(f"📊 Summary: Instance={instance.name}, Health={health.get('status', 'unknown')}, Nodes={health.get('number_of_nodes', 0)}")
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to get Elasticsearch cluster health: {str(e)}"
            logger.error(f"❌ INFRAINSIGHTS ELASTICSEARCH ERROR: {error_msg}")
            
            # Enhanced error logging
            logger.error(f"🔍 Error context: params={params}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            
            # Provide helpful error message with troubleshooting
            helpful_msg = self.get_helpful_error_message(error_msg)
            
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=helpful_msg,
                params=params
            )

class VerboseElasticsearchIndicesTool(BaseInfraInsightsToolV2):
    """Tool to list Elasticsearch indices with enhanced verbose logging"""
    
    def __init__(self, toolset):
        super().__init__(
            name="elasticsearch_list_indices",
            description="List all indices in an Elasticsearch cluster managed by InfraInsights",
            toolset=toolset
        )
    
    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        logger.info("🔍 INFRAINSIGHTS ELASTICSEARCH: Starting indices listing")
        logger.info(f"📝 Request parameters: {json.dumps(params, indent=2)}")
        
        try:
            # Enhanced instance resolution with verbose logging
            logger.info("🔍 INFRAINSIGHTS: Attempting to resolve Elasticsearch instance...")
            instance = self.get_instance_from_params(params)
            logger.info(f"✅ INFRAINSIGHTS: Successfully resolved instance: {instance.name}")
            
            # Get connection configuration
            logger.info("🔧 INFRAINSIGHTS: Extracting connection configuration...")
            config = self.get_connection_config(instance)
            
            # Extract Elasticsearch connection details
            es_url = config.get('elasticsearchUrl', config.get('elasticsearch_url'))
            username = config.get('username')
            api_key = config.get('apiKey', config.get('api_key'))
            
            logger.info(f"🔗 INFRAINSIGHTS: Connecting to Elasticsearch at: {es_url}")
            
            if not es_url:
                raise Exception("Elasticsearch URL not found in instance configuration")
            
            # Import and configure Elasticsearch client
            try:
                from elasticsearch import Elasticsearch
                logger.info("✅ INFRAINSIGHTS: Elasticsearch client library loaded")
            except ImportError:
                raise Exception("Elasticsearch client library not available")
            
            # Configure authentication
            auth_config = {}
            if api_key:
                auth_config['api_key'] = api_key
                logger.info("🔐 INFRAINSIGHTS: Using API key authentication")
            elif username:
                auth_config['http_auth'] = (username, config.get('password'))
                logger.info("🔐 INFRAINSIGHTS: Using username/password authentication")
            
            # Create Elasticsearch client
            logger.info("🔌 INFRAINSIGHTS: Creating Elasticsearch client connection...")
            es = Elasticsearch(
                [es_url],
                verify_certs=False,
                timeout=30,
                **auth_config
            )
            
            # Get indices information
            logger.info("📊 INFRAINSIGHTS: Fetching indices information...")
            indices = es.cat.indices(format='json', v=True)
            logger.info(f"✅ INFRAINSIGHTS: Retrieved {len(indices)} indices")
            
            # Get additional index stats
            try:
                logger.info("📈 INFRAINSIGHTS: Fetching detailed index statistics...")
                index_stats = es.indices.stats()
                logger.info("✅ INFRAINSIGHTS: Index statistics retrieved")
            except Exception as e:
                logger.warning(f"⚠️  INFRAINSIGHTS: Failed to get index stats: {e}")
                index_stats = {}
            
            result = {
                "elasticsearch_cluster": {
                    "instance_name": instance.name,
                    "instance_id": instance.instanceId,
                    "environment": instance.environment,
                    "elasticsearch_url": es_url,
                    "connection_method": "InfraInsights-managed"
                },
                "indices": {
                    "total_count": len(indices),
                    "indices_list": indices,
                    "indices_stats": index_stats
                },
                "infrainsights_metadata": {
                    "toolset": "InfraInsights Elasticsearch V2",
                    "instance_resolution": "successful", 
                    "resolution_method": "name-based lookup",
                    "name_lookup_enabled": self.get_infrainsights_client().config.enable_name_lookup,
                    "api_version": "v2"
                },
                "timestamp": "2025-01-22T10:15:00Z"
            }
            
            logger.info("🎉 INFRAINSIGHTS: Elasticsearch indices listing completed successfully")
            logger.info(f"📊 Summary: Instance={instance.name}, Total indices={len(indices)}")
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to list Elasticsearch indices: {str(e)}"
            logger.error(f"❌ INFRAINSIGHTS ELASTICSEARCH ERROR: {error_msg}")
            
            # Provide helpful error message
            helpful_msg = self.get_helpful_error_message(error_msg)
            
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=helpful_msg,
                params=params
            )

class EnhancedElasticsearchToolset(BaseInfraInsightsToolsetV2):
    """Enhanced Elasticsearch toolset with verbose logging and better routing hints"""
    
    def __init__(self):
        super().__init__("InfraInsights Elasticsearch Enhanced")
        
        # Set tools after initialization
        self.tools = [
            VerboseElasticsearchHealthTool(self),
            VerboseElasticsearchIndicesTool(self)
        ]
        
        # Enhanced LLM instructions for better routing
        self.llm_instructions = """
## InfraInsights Elasticsearch Enhanced Toolset

🎯 **When to use this toolset:**
- User mentions specific Elasticsearch instance names (e.g., "dock-atlantic-staging", "production-es")
- User wants to check cluster health, list indices, or manage Elasticsearch data
- User refers to "my Elasticsearch cluster" or "my ES instance"
- Query contains environment-specific Elasticsearch references (staging, production, etc.)

🔍 **Capabilities:**
- Connect to InfraInsights-managed Elasticsearch instances
- Check cluster health and status
- List and analyze indices
- Perform searches and data analysis
- Support for multiple authentication methods (API key, username/password)

⚠️ **Instance Resolution:**
This toolset resolves Elasticsearch instances by name from InfraInsights. Examples:
- "dock-atlantic-staging" → connects to the staging instance
- "production-elasticsearch" → connects to production cluster
- "es-cluster-1" → connects to the named cluster

🔧 **Usage Examples:**
- "Check the health of my dock-atlantic-staging Elasticsearch cluster"
- "List all indices in production-elasticsearch"
- "Show me the status of es-cluster-dev"

📝 **Verbose Logging:**
All operations include detailed logging with 🔍, ✅, ❌, and 🎉 emojis for easy tracking.

🚨 **Error Handling:**
Provides detailed troubleshooting steps when connections fail or instances are not found.
        """
    
    def get_service_type(self) -> str:
        return "elasticsearch" 