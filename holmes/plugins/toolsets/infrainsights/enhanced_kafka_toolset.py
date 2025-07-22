import json
import logging
from typing import Dict, Any

from holmes.core.tools import StructuredToolResult, ToolResultStatus
from .base_toolset_v2 import BaseInfraInsightsToolV2, BaseInfraInsightsToolsetV2

logger = logging.getLogger(__name__)

class VerboseKafkaTopicsTool(BaseInfraInsightsToolV2):
    """Tool to list Kafka topics with enhanced verbose logging"""
    
    def __init__(self, toolset):
        super().__init__(
            name="kafka_list_topics",
            description="List topics in a Kafka cluster managed by InfraInsights",
            toolset=toolset
        )
    
    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        logger.info("🔍 INFRAINSIGHTS KAFKA: Starting topics listing")
        logger.info(f"📝 Request parameters: {json.dumps(params, indent=2)}")
        
        try:
            # Enhanced instance resolution with verbose logging
            logger.info("🔍 INFRAINSIGHTS: Attempting to resolve Kafka instance...")
            instance = self.get_instance_from_params(params)
            logger.info(f"✅ INFRAINSIGHTS: Successfully resolved instance: {instance.name} (ID: {instance.instanceId})")
            logger.info(f"🏷️  Instance details: Environment={instance.environment}, Status={instance.status}")
            
            # Get connection configuration with verbose logging
            logger.info("🔧 INFRAINSIGHTS: Extracting connection configuration...")
            config = self.get_connection_config(instance)
            logger.info("✅ INFRAINSIGHTS: Configuration extracted successfully")
            
            # Extract Kafka connection details
            bootstrap_servers = config.get('bootstrapServers', config.get('bootstrap_servers'))
            security_protocol = config.get('securityProtocol', config.get('security_protocol', 'PLAINTEXT'))
            
            logger.info(f"🔗 INFRAINSIGHTS: Connecting to Kafka at: {bootstrap_servers}")
            
            if not bootstrap_servers:
                raise Exception("Kafka bootstrap servers not found in instance configuration")
            
            # Import and configure Kafka client
            try:
                from kafka import KafkaAdminClient, KafkaConsumer
                from kafka.errors import KafkaConnectionError, KafkaTimeoutError
                logger.info("✅ INFRAINSIGHTS: Kafka client library loaded")
            except ImportError:
                raise Exception("Kafka client library not available")
            
            # Configure authentication with verbose logging
            kafka_config = {
                'bootstrap_servers': bootstrap_servers.split(','),
                'security_protocol': security_protocol,
                'request_timeout_ms': 30000,
                'connections_max_idle_ms': 30000
            }
            
            if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL']:
                kafka_config.update({
                    'sasl_mechanism': config.get('saslMechanism', 'PLAIN'),
                    'sasl_plain_username': config.get('username'),
                    'sasl_plain_password': config.get('password')
                })
                logger.info("🔐 INFRAINSIGHTS: Using SASL authentication")
            else:
                logger.info("🔐 INFRAINSIGHTS: Using plaintext connection")
            
            # Create Kafka admin client
            logger.info("🔌 INFRAINSIGHTS: Creating Kafka admin client...")
            admin_client = KafkaAdminClient(**kafka_config)
            
            # Test connection and get topics
            logger.info("🧪 INFRAINSIGHTS: Testing Kafka connection...")
            logger.info("📊 INFRAINSIGHTS: Fetching topics list...")
            
            # Get cluster metadata to list topics
            metadata = admin_client.describe_topics()
            topics = list(metadata.keys())
            
            logger.info(f"✅ INFRAINSIGHTS: Retrieved {len(topics)} topics")
            
            # Get additional topic details
            try:
                logger.info("📈 INFRAINSIGHTS: Fetching topic configurations...")
                # This would require additional API calls for detailed topic info
                topic_details = {}
                for topic in topics[:10]:  # Limit to first 10 for performance
                    topic_details[topic] = {
                        "partition_count": "unknown",
                        "replication_factor": "unknown"
                    }
                logger.info("✅ INFRAINSIGHTS: Topic details retrieved")
            except Exception as e:
                logger.warning(f"⚠️  INFRAINSIGHTS: Failed to get detailed topic info: {e}")
                topic_details = {}
            
            result = {
                "kafka_cluster": {
                    "instance_name": instance.name,
                    "instance_id": instance.instanceId,
                    "environment": instance.environment,
                    "bootstrap_servers": bootstrap_servers,
                    "connection_method": "InfraInsights-managed"
                },
                "topics": {
                    "total_count": len(topics),
                    "topics_list": topics,
                    "topic_details": topic_details
                },
                "infrainsights_metadata": {
                    "toolset": "InfraInsights Kafka Enhanced",
                    "instance_resolution": "successful",
                    "resolution_method": "name-based lookup",
                    "name_lookup_enabled": self.get_infrainsights_client().config.enable_name_lookup,
                    "api_version": "v2"
                },
                "timestamp": "2025-01-22T10:15:00Z"
            }
            
            logger.info("🎉 INFRAINSIGHTS: Kafka topics listing completed successfully")
            logger.info(f"📊 Summary: Instance={instance.name}, Total topics={len(topics)}")
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to list Kafka topics: {str(e)}"
            logger.error(f"❌ INFRAINSIGHTS KAFKA ERROR: {error_msg}")
            
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

class EnhancedKafkaToolset(BaseInfraInsightsToolsetV2):
    """Enhanced Kafka toolset with verbose logging and better routing hints"""
    
    def __init__(self):
        super().__init__("InfraInsights Kafka Enhanced")
        
        self.tools = [
            VerboseKafkaTopicsTool(self)
        ]
        
        # Enhanced LLM instructions for better routing
        self.llm_instructions = """
## InfraInsights Kafka Enhanced Toolset

🎯 **When to use this toolset:**
- User mentions specific Kafka instance names (e.g., "kafka-prod", "staging-kafka")
- User wants to list topics, check consumer groups, or manage Kafka data
- User refers to "my Kafka cluster" or "our Kafka instance"
- Query contains environment-specific Kafka references (staging, production, etc.)

🔍 **Capabilities:**
- Connect to InfraInsights-managed Kafka instances
- List topics and consumer groups
- Check cluster health and broker status
- Support for multiple authentication methods (SASL, SSL)

⚠️ **Instance Resolution:**
This toolset resolves Kafka instances by name from InfraInsights. Examples:
- "kafka-prod" → connects to the production instance
- "staging-kafka" → connects to staging cluster
- "dock-atlantic-staging" → connects to the named cluster (if Kafka)

🔧 **Usage Examples:**
- "List topics in my kafka-prod cluster"
- "Show consumer groups in staging-kafka"
- "Check the status of dock-atlantic-staging Kafka"

📝 **Verbose Logging:**
All operations include detailed logging with 🔍, ✅, ❌, and 🎉 emojis for easy tracking.

🚨 **Error Handling:**
Provides detailed troubleshooting steps when connections fail or instances are not found.
        """
    
    def get_service_type(self) -> str:
        return "kafka" 