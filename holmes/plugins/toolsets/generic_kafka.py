import os
import json
import logging
from typing import Dict, Any, List
from kafkajs import Kafka, KafkaConfig
from kafkajs.errors import KafkaConnectionError, KafkaTimeoutError, KafkaAuthenticationError

from holmes.core.tools import StructuredTool, StructuredToolResult, ToolResultStatus
from holmes.plugins.infrainsights_plugin import resolve_instance_for_toolset
from holmes.plugins.smart_router import parse_prompt_for_routing

logger = logging.getLogger(__name__)

class BaseKafkaTool(StructuredTool):
    """Base class for all Kafka tools"""
    
    def _get_kafka_client(self) -> Kafka:
        """Create and return a Kafka client using environment variables"""
        brokers = os.getenv('KAFKA_BROKERS')
        username = os.getenv('KAFKA_USERNAME')
        password = os.getenv('KAFKA_PASSWORD')
        ssl_enabled = os.getenv('KAFKA_SSL_ENABLED', 'false').lower() == 'true'
        sasl_mechanism = os.getenv('KAFKA_SASL_MECHANISM', 'SCRAM-SHA-512')
        security_protocol = os.getenv('KAFKA_SECURITY_PROTOCOL', 'PLAINTEXT')
        
        if not brokers:
            raise Exception("Kafka connection not configured. No KAFKA_BROKERS environment variable found.")
        
        # Parse brokers string (comma-separated)
        broker_list = [broker.strip() for broker in brokers.split(',')]
        
        try:
            # Build Kafka configuration
            config = KafkaConfig(
                brokers=broker_list,
                client_id='infrainsights-holmesgpt',
                connection_timeout=10000,
                request_timeout=10000,
                retry_backoff=1000,
                max_retries=3
            )
            
            # Configure SSL if enabled
            if ssl_enabled or security_protocol in ['SSL', 'SASL_SSL']:
                config.ssl = {
                    'rejectUnauthorized': False  # For self-signed certificates
                }
            
            # Configure SASL authentication if credentials provided
            if username and password:
                config.sasl = {
                    'mechanism': sasl_mechanism,
                    'username': username,
                    'password': password
                }
            
            client = Kafka(config)
            
            # Test connection
            admin = client.admin()
            admin.listTopics()  # This will fail if connection is bad
            
            return client
            
        except Exception as e:
            raise Exception(f"Failed to create Kafka client: {str(e)}")
    
    def _ensure_instance_resolved(self, params: Dict[str, Any], prompt: str = "") -> bool:
        """Ensure Kafka instance is resolved and environment variables are set"""
        # Check if environment variables are already set
        if os.getenv('KAFKA_BROKERS'):
            return True
        
        # Try to extract instance hint from parameters or prompt
        instance_hint = (
            params.get('instance_name') or 
            params.get('instance_id') or 
            params.get('cluster_name')
        )
        
        if not instance_hint and prompt:
            route_info = parse_prompt_for_routing(prompt)
            if route_info.instance_hint:
                instance_hint = route_info.instance_hint
        
        # Use default if no hint found
        if not instance_hint:
            instance_hint = "default"
        
        # Resolve instance using InfraInsights plugin
        result = resolve_instance_for_toolset('kafka', instance_hint, params.get('user_id'))
        
        if not result.success:
            logger.error(f"Failed to resolve Kafka instance: {result.error_message}")
            return False
        
        logger.info(f"✅ Resolved Kafka instance: {result.instance.name}")
        return True
    
    def _get_instance_info(self) -> Dict[str, Any]:
        """Get current instance information from environment variables"""
        return {
            'name': os.getenv('CURRENT_INSTANCE_NAME', 'Unknown'),
            'environment': os.getenv('CURRENT_INSTANCE_ENVIRONMENT', 'Unknown'),
            'id': os.getenv('CURRENT_INSTANCE_ID', 'Unknown'),
            'brokers': os.getenv('KAFKA_BROKERS', 'Not configured'),
            'sasl_mechanism': os.getenv('KAFKA_SASL_MECHANISM', 'None'),
            'ssl_enabled': os.getenv('KAFKA_SSL_ENABLED', 'false'),
            'security_protocol': os.getenv('KAFKA_SECURITY_PROTOCOL', 'PLAINTEXT')
        }

class KafkaTopicsTool(BaseKafkaTool):
    """Tool to list Kafka topics"""
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        try:
            # Ensure instance is resolved
            if not self._ensure_instance_resolved(params, params.get('prompt', '')):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not resolve Kafka instance. Please specify instance name or check InfraInsights configuration.",
                    params=params
                )
            
            instance_info = self._get_instance_info()
            kafka = self._get_kafka_client()
            admin = kafka.admin()
            
            # List topics
            topics = admin.listTopics()
            
            # Get topic metadata for additional details
            topic_metadata = {}
            for topic in topics:
                try:
                    metadata = admin.describeTopics([topic])
                    topic_metadata[topic] = metadata.get(topic, {})
                except Exception as e:
                    logger.warning(f"Failed to get metadata for topic {topic}: {str(e)}")
                    topic_metadata[topic] = {"error": str(e)}
            
            result = {
                "kafka_cluster": {
                    "instance_name": instance_info['name'],
                    "instance_id": instance_info['id'],
                    "environment": instance_info['environment'],
                    "brokers": instance_info['brokers']
                },
                "topics": {
                    "total_count": len(topics),
                    "topic_list": topics,
                    "topic_details": topic_metadata
                },
                "timestamp": "2025-01-22T09:40:00Z"
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except KafkaConnectionError as e:
            error_msg = f"Failed to connect to Kafka cluster: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=self._get_helpful_error_message(error_msg),
                params=params
            )
            
        except KafkaAuthenticationError as e:
            error_msg = f"Kafka authentication failed: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=self._get_helpful_error_message(error_msg),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to list Kafka topics: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=self._get_helpful_error_message(error_msg),
                params=params
            )
    
    def _get_helpful_error_message(self, original_error: str) -> str:
        """Generate helpful error message for Kafka connection issues"""
        instance_info = self._get_instance_info()
        
        return f"""Failed to list Kafka topics: {original_error}

🔍 **Troubleshooting Steps:**

1. **Check Kafka Cluster Status**
   - Instance: {instance_info['name']} ({instance_info['environment']})
   - Brokers: {instance_info['brokers']}
   - Verify that Kafka brokers are running and accessible

2. **Authentication Issues**
   - SASL Mechanism: {instance_info['sasl_mechanism']}
   - SSL Enabled: {instance_info['ssl_enabled']}
   - Check username/password credentials in InfraInsights

3. **Network Connectivity**
   - Ensure HolmesGPT can reach Kafka brokers
   - Check firewall/security group settings
   - Verify broker endpoints are correct

4. **Instance Configuration**
   - Check InfraInsights dashboard for Kafka instance status
   - Verify broker list and authentication settings

💡 **Quick Test:** Access InfraInsights dashboard and test Kafka instance connectivity.

Once resolved, try your query again."""

class KafkaConsumerGroupsTool(BaseKafkaTool):
    """Tool to list Kafka consumer groups"""
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        try:
            # Ensure instance is resolved
            if not self._ensure_instance_resolved(params, params.get('prompt', '')):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not resolve Kafka instance. Please specify instance name or check InfraInsights configuration.",
                    params=params
                )
            
            instance_info = self._get_instance_info()
            kafka = self._get_kafka_client()
            admin = kafka.admin()
            
            # List consumer groups
            consumer_groups = admin.listGroups()
            
            # Get detailed information for each consumer group
            group_details = {}
            for group in consumer_groups:
                try:
                    group_info = admin.describeGroups([group])
                    offsets = admin.fetchOffsets({
                        'groupId': group,
                        'topics': []  # Get all topics
                    })
                    
                    group_details[group] = {
                        "info": group_info.get(group, {}),
                        "offsets": offsets
                    }
                except Exception as e:
                    logger.warning(f"Failed to get details for consumer group {group}: {str(e)}")
                    group_details[group] = {"error": str(e)}
            
            result = {
                "kafka_cluster": {
                    "instance_name": instance_info['name'],
                    "instance_id": instance_info['id'],
                    "environment": instance_info['environment'],
                    "brokers": instance_info['brokers']
                },
                "consumer_groups": {
                    "total_count": len(consumer_groups),
                    "group_list": consumer_groups,
                    "group_details": group_details
                },
                "timestamp": "2025-01-22T09:40:00Z"
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to list Kafka consumer groups: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=self._get_helpful_error_message(error_msg),
                params=params
            )

class KafkaClusterInfoTool(BaseKafkaTool):
    """Tool to get Kafka cluster information"""
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        try:
            # Ensure instance is resolved
            if not self._ensure_instance_resolved(params, params.get('prompt', '')):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not resolve Kafka instance. Please specify instance name or check InfraInsights configuration.",
                    params=params
                )
            
            instance_info = self._get_instance_info()
            kafka = self._get_kafka_client()
            admin = kafka.admin()
            
            # Get cluster metadata
            metadata = admin.fetchMetadata()
            
            # Get broker information
            brokers = metadata.get('brokers', [])
            
            # Get cluster configuration
            try:
                cluster_config = admin.describeConfigs({
                    'resources': [{'type': 'BROKER', 'name': str(broker['nodeId'])} for broker in brokers]
                })
            except Exception as e:
                logger.warning(f"Failed to get cluster configuration: {str(e)}")
                cluster_config = {"error": str(e)}
            
            result = {
                "kafka_cluster": {
                    "instance_name": instance_info['name'],
                    "instance_id": instance_info['id'],
                    "environment": instance_info['environment'],
                    "cluster_id": metadata.get('clusterId', 'Unknown'),
                    "controller_id": metadata.get('controllerId', 'Unknown')
                },
                "brokers": {
                    "count": len(brokers),
                    "broker_list": brokers
                },
                "configuration": cluster_config,
                "metadata": metadata,
                "timestamp": "2025-01-22T09:40:00Z"
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to get Kafka cluster information: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=self._get_helpful_error_message(error_msg),
                params=params
            )

# Register tools with HolmesGPT
def get_tools():
    """Return list of available Kafka tools for HolmesGPT registration"""
    return [
        KafkaTopicsTool(),
        KafkaConsumerGroupsTool(), 
        KafkaClusterInfoTool()
    ]

# Tool metadata for HolmesGPT
TOOLSET_NAME = "Generic Kafka"
TOOLSET_DESCRIPTION = "Generic Kafka toolset that works with InfraInsights multi-instance architecture"
TOOLSET_VERSION = "1.0.0" 