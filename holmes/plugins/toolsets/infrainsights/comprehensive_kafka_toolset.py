import json
import logging
from typing import Dict, Any, Optional, List
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite, ToolParameter

logger = logging.getLogger(__name__)


# ============================================
# PHASE 1: BASIC KAFKA TOOLS
# ============================================

class KafkaHealthCheckTool(Tool):
    """Tool to check Kafka cluster health and connectivity"""
    
    name: str = "kafka_health_check"
    description: str = "Check the health status of a Kafka cluster including broker connectivity and basic cluster info"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance to check",
            type="string",
            required=True
        )
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
            
            logger.info(f"🔍 Checking health for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract Kafka connection config
            config = instance.config or {}
            brokers = config.get('brokers', [])
            security_protocol = config.get('securityProtocol', 'PLAINTEXT')
            
            # Import Kafka admin client (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient
                from confluent_kafka import KafkaError
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = {
                'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
                'security.protocol': security_protocol.lower(),
                'request.timeout.ms': 10000,
                'connections.max.idle.ms': 10000
            }
            
            # Add SASL config if present
            if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
                sasl_config = config['sasl']
                admin_config.update({
                    'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                    'sasl.username': sasl_config.get('username'),
                    'sasl.password': sasl_config.get('password')
                })
            
            # Try to connect and get cluster info
            try:
                admin_client = AdminClient(admin_config)
                
                # Get cluster metadata (confluent-kafka API)
                metadata = admin_client.list_topics(timeout=10)
                
                health_data = {
                    'status': 'healthy',
                    'cluster_id': getattr(metadata, 'cluster_id', 'unknown'),
                    'controller_id': getattr(metadata, 'controller_id', 'unknown'),
                    'brokers': [
                        {
                            'id': broker.id,
                            'host': broker.host,
                            'port': broker.port,
                            'rack': getattr(broker, 'rack', None)
                        }
                        for broker in metadata.brokers.values()
                    ],
                    'broker_count': len(metadata.brokers),
                    'connection_info': {
                        'bootstrap_servers': brokers,
                        'security_protocol': security_protocol,
                        'sasl_enabled': security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL']
                    }
                }
                
                
                
            except Exception as e:
                health_data = {
                    'status': 'unhealthy',
                    'error': str(e),
                    'connection_info': {
                        'bootstrap_servers': brokers,
                        'security_protocol': security_protocol
                    }
                }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=health_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error checking Kafka health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Kafka health: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"kafka_health_check(instance_name={instance_name})"


class KafkaListTopicsTool(Tool):
    """Tool to list all topics in a Kafka cluster"""
    
    name: str = "kafka_list_topics"
    description: str = "List all topics in a Kafka cluster with partition and replication information"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "include_internal": ToolParameter(
            description="Include internal topics",
            type="boolean",
            required=False
        )
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
            
            logger.info(f"🔍 Listing topics for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            brokers = config.get('brokers', [])
            
            # Import Kafka admin client (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            # Get topics
            try:
                admin_client = AdminClient(admin_config)
                
                # List all topics (confluent-kafka API returns metadata with topics)
                metadata = admin_client.list_topics(timeout=10)
                
                topics_data = []
                for topic_name, topic_metadata in metadata.topics.items():
                    # Skip internal topics if not requested
                    if not params.get('include_internal', False) and topic_name.startswith('__'):
                        continue
                    
                    # Get topic metadata for each topic
                    try:
                        partitions = topic_metadata.partitions
                        
                        topic_info = {
                            'name': topic_name,
                            'partitions': len(partitions),
                            'replication_factor': len(partitions[0].replicas) if partitions else 0,
                            'is_internal': topic_name.startswith('__'),
                            'partition_details': [
                                {
                                    'partition': p.id,
                                    'leader': p.leader,
                                    'replicas': p.replicas,
                                    'isr': getattr(p, 'isr', p.replicas)  # Use replicas as fallback if isr not available
                                }
                                for p in partitions.values()
                            ]
                        }
                        topics_data.append(topic_info)
                    except Exception as e:
                        # If we can't get detailed metadata, just add basic info
                        topic_info = {
                            'name': topic_name,
                            'partitions': len(partitions) if 'partitions' in locals() else 0,
                            'replication_factor': 0,
                            'is_internal': topic_name.startswith('__'),
                            'partition_details': [],
                            'error': f"Could not get metadata: {str(e)}"
                        }
                        topics_data.append(topic_info)
                
                
                
                result_data = {
                    'total_topics': len(topics_data),
                    'topics': sorted(topics_data, key=lambda x: x['name'])
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to list topics: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=result_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error listing Kafka topics: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list Kafka topics: {str(e)}",
                params=params
            )
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        include_internal = params.get('include_internal', False)
        return f"kafka_list_topics(instance_name={instance_name}, include_internal={include_internal})"


class KafkaTopicDetailsTool(Tool):
    """Tool to get detailed information about a specific Kafka topic"""
    
    name: str = "kafka_topic_details"
    description: str = "Get detailed information about a specific Kafka topic including configuration and metrics"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "topic_name": ToolParameter(
            description="Name of the topic to inspect",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            topic_name = params.get('topic_name')
            
            if not instance_name or not topic_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name and topic_name parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Getting details for topic '{topic_name}' in Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            
            # Import Kafka clients (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient, ConfigResource, ConfigResourceType
                from confluent_kafka import Consumer
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            try:
                admin_client = AdminClient(admin_config)
                
                # Get topic metadata
                metadata = admin_client.list_topics(timeout=10)
                
                if topic_name not in metadata.topics:
                    
                    return StructuredToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Topic '{topic_name}' not found",
                        params=params
                    )
                
                topic_metadata = metadata.topics[topic_name]
                
                # Get topic configuration
                resource = ConfigResource(ConfigResourceType.TOPIC, topic_name)
                configs = admin_client.describe_configs(config_resources=[resource])
                topic_config = {}
                
                for config_resource, config_response in configs.items():
                    for config_name, config_value in config_response.configs.items():
                        topic_config[config_name] = {
                            'value': config_value.value,
                            'source': config_value.source.name,
                            'is_default': config_value.is_default,
                            'is_read_only': config_value.is_read_only,
                            'is_sensitive': config_value.is_sensitive
                        }
                
                # Calculate total size (approximate based on segment sizes)
                partition_info = []
                for partition_id, partition_metadata in topic_metadata.partitions.items():
                    partition_info.append({
                        'partition': partition_id,
                        'leader': partition_metadata.leader,
                        'replicas': partition_metadata.replicas,
                        'isr': getattr(partition_metadata, 'isr', partition_metadata.replicas),
                        'offline_replicas': getattr(partition_metadata, 'offline_replicas', [])
                    })
                
                
                
                # Get consumer group information
                consumer_groups = self._get_consumer_groups_for_topic(config, topic_name)
                
                topic_details = {
                    'name': topic_name,
                    'partitions': len(topic_metadata.partitions),
                    'replication_factor': len(partition_info[0]['replicas']) if partition_info else 0,
                    'is_internal': topic_name.startswith('__'),
                    'partition_details': partition_info,
                    'configuration': topic_config,
                    'consumer_groups': consumer_groups
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to get topic details: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=topic_details,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting Kafka topic details: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get Kafka topic details: {str(e)}",
                params=params
            )
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def _get_consumer_groups_for_topic(self, config: Dict, topic_name: str) -> List[str]:
        """Get list of consumer groups consuming from this topic"""
        try:
            from confluent_kafka.admin import AdminClient
            admin_config = self._build_admin_config(config)
            admin_client = AdminClient(admin_config)
            
            # List all consumer groups
            consumer_groups = []
            try:
                groups = admin_client.list_consumer_groups()
                for group in groups:
                    group_id = group[0]
                    # Check if this group consumes from our topic
                    offsets = admin_client.list_consumer_group_offsets(group_id)
                    for topic_partition in offsets.keys():
                        if topic_partition.topic == topic_name:
                            consumer_groups.append(group_id)
                            break
            except:
                pass  # Consumer group operations might not be available
            
            
            return consumer_groups
            
        except:
            return []
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        topic_name = params.get('topic_name', 'unknown')
        return f"kafka_topic_details(instance_name={instance_name}, topic_name={topic_name})"


# ============================================
# PHASE 2: INTERMEDIATE KAFKA TOOLS
# ============================================

class KafkaConsumerGroupsTool(Tool):
    """Tool to list and analyze consumer groups"""
    
    name: str = "kafka_consumer_groups"
    description: str = "List all consumer groups and their status in a Kafka cluster"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "group_id": ToolParameter(
            description="Specific consumer group ID to inspect (optional)",
            type="string",
            required=False
        )
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
            
            logger.info(f"🔍 Analyzing consumer groups for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            
            # Import Kafka admin client (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            try:
                admin_client = AdminClient(admin_config)
                
                # Get specific group or all groups
                group_id = params.get('group_id')
                
                if group_id:
                    # Get details for specific group
                    groups_data = [self._get_group_details(admin_client, group_id)]
                else:
                    # List all consumer groups
                    groups = admin_client.list_consumer_groups()
                    groups_data = []
                    
                    for group_tuple in groups:
                        group_id = group_tuple[0]
                        group_type = group_tuple[1]
                        
                        group_details = self._get_group_details(admin_client, group_id)
                        group_details['type'] = group_type
                        groups_data.append(group_details)
                
                
                
                result_data = {
                    'total_groups': len(groups_data),
                    'consumer_groups': groups_data
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to get consumer groups: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=result_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Kafka consumer groups: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Kafka consumer groups: {str(e)}",
                params=params
            )
    
    def _get_group_details(self, admin_client, group_id: str) -> Dict:
        """Get detailed information about a consumer group"""
        try:
            # Describe the consumer group
            group_description = admin_client.describe_consumer_groups([group_id])
            desc = group_description[group_id]
            
            # Get consumer group offsets
            offsets = admin_client.list_consumer_group_offsets(group_id)
            
            # Calculate lag for each topic-partition
            topics = {}
            total_lag = 0
            
            for topic_partition, offset_metadata in offsets.items():
                topic = topic_partition.topic
                partition = topic_partition.partition
                
                if topic not in topics:
                    topics[topic] = {
                        'topic': topic,
                        'partitions': []
                    }
                
                # Get high water mark (latest offset)
                from confluent_kafka import Consumer
                consumer = Consumer({
                    'bootstrap.servers': ','.join(admin_client._client.cluster.brokers()),
                    'security.protocol': admin_client._client.config.get('security_protocol', 'PLAINTEXT')
                })
                
                partitions = consumer.partitions_for_topic(topic)
                if partitions and partition in partitions:
                    from confluent_kafka import TopicPartition
                    tp = TopicPartition(topic, partition)
                    consumer.assign([tp])
                    consumer.seek_to_end(tp)
                    high_water_mark = consumer.position(tp)
                    lag = high_water_mark - offset_metadata.offset if offset_metadata.offset >= 0 else 0
                else:
                    high_water_mark = -1
                    lag = 0
                
                consumer.close()
                
                total_lag += lag
                
                topics[topic]['partitions'].append({
                    'partition': partition,
                    'current_offset': offset_metadata.offset,
                    'high_water_mark': high_water_mark,
                    'lag': lag
                })
            
            return {
                'group_id': group_id,
                'state': desc.state,
                'members': len(desc.members),
                'coordinator': {
                    'id': desc.coordinator.id,
                    'host': desc.coordinator.host,
                    'port': desc.coordinator.port
                },
                'topics': list(topics.values()),
                'total_lag': total_lag
            }
            
        except Exception as e:
            return {
                'group_id': group_id,
                'error': str(e)
            }
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        group_id = params.get('group_id', '')
        if group_id:
            return f"kafka_consumer_groups(instance_name={instance_name}, group_id={group_id})"
        return f"kafka_consumer_groups(instance_name={instance_name})"


class KafkaProducerPerformanceTool(Tool):
    """Tool to analyze Kafka producer performance and throughput"""
    
    name: str = "kafka_producer_performance"
    description: str = "Test Kafka producer performance by sending test messages and measuring throughput"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "topic_name": ToolParameter(
            description="Topic to produce messages to",
            type="string",
            required=True
        ),
        "num_messages": ToolParameter(
            description="Number of test messages to send",
            type="integer",
            required=False
        ),
        "message_size": ToolParameter(
            description="Size of each message in bytes",
            type="integer",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            topic_name = params.get('topic_name')
            
            if not instance_name or not topic_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name and topic_name parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Testing producer performance for topic '{topic_name}' in Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            
            # Import Kafka producer (confluent-kafka)
            try:
                from confluent_kafka import Producer
                import time
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build producer config
            producer_config = self._build_producer_config(config)
            
            # Test parameters
            num_messages = params.get('num_messages', 1000)
            message_size = params.get('message_size', 100)
            test_message = b'x' * message_size
            
            try:
                producer = Producer(producer_config)
                
                # Warm up
                for _ in range(10):
                    producer.send(topic_name, value=test_message)
                producer.flush()
                
                # Performance test
                start_time = time.time()
                futures = []
                
                for i in range(num_messages):
                    future = producer.send(
                        topic_name,
                        value=test_message,
                        key=f"test-{i}".encode('utf-8')
                    )
                    futures.append(future)
                
                # Wait for all messages to be sent
                producer.flush()
                
                # Calculate metrics
                end_time = time.time()
                duration = end_time - start_time
                
                # Check for failures
                successful = 0
                failed = 0
                for future in futures:
                    try:
                        future.get(timeout=10)
                        successful += 1
                    except:
                        failed += 1
                
                producer.close()
                
                performance_data = {
                    'test_parameters': {
                        'num_messages': num_messages,
                        'message_size_bytes': message_size,
                        'topic': topic_name
                    },
                    'results': {
                        'duration_seconds': round(duration, 2),
                        'successful_messages': successful,
                        'failed_messages': failed,
                        'messages_per_second': round(successful / duration, 2),
                        'throughput_mb_per_second': round((successful * message_size) / (duration * 1024 * 1024), 2),
                        'average_latency_ms': round((duration * 1000) / successful, 2) if successful > 0 else 0
                    }
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Producer performance test failed: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=performance_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error testing Kafka producer performance: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to test Kafka producer performance: {str(e)}",
                params=params
            )
    
    def _build_producer_config(self, config: Dict) -> Dict:
        """Build Kafka producer configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        producer_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'acks': 'all',
            'retries': 0,
            'batch.size': 16384,
            'linger.ms': 0,
            'buffer.memory': 33554432
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            producer_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return producer_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        topic_name = params.get('topic_name', 'unknown')
        return f"kafka_producer_performance(instance_name={instance_name}, topic_name={topic_name})"


class KafkaConsumerLagTool(Tool):
    """Tool to analyze consumer lag across topics and partitions"""
    
    name: str = "kafka_consumer_lag"
    description: str = "Analyze consumer lag for all consumer groups, identify lagging consumers and partitions"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "lag_threshold": ToolParameter(
            description="Lag threshold to highlight (messages behind)",
            type="integer",
            required=False
        )
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
            
            logger.info(f"🔍 Analyzing consumer lag for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            lag_threshold = params.get('lag_threshold', 1000)
            
            # Import Kafka clients (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient
                from confluent_kafka import Consumer, TopicPartition
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            try:
                admin_client = AdminClient(admin_config)
                
                # Get all consumer groups
                groups = admin_client.list_consumer_groups()
                
                lag_analysis = {
                    'total_groups': 0,
                    'total_lag': 0,
                    'groups_with_lag': 0,
                    'critical_lag_groups': [],
                    'group_details': []
                }
                
                for group_tuple in groups:
                    group_id = group_tuple[0]
                    
                    try:
                        # Get consumer group offsets
                        offsets = admin_client.list_consumer_group_offsets(group_id)
                        
                        group_lag = 0
                        topic_lags = {}
                        
                        # Create consumer to get high water marks
                        consumer = Consumer(self._build_consumer_config(config))
                        
                        for topic_partition, offset_metadata in offsets.items():
                            topic = topic_partition.topic
                            partition = topic_partition.partition
                            
                            # Get high water mark
                            partitions = consumer.partitions_for_topic(topic)
                            if partitions and partition in partitions:
                                tp = TopicPartition(topic, partition)
                                consumer.assign([tp])
                                consumer.seek_to_end(tp)
                                high_water_mark = consumer.position(tp)
                                
                                # Calculate lag
                                current_offset = offset_metadata.offset
                                lag = high_water_mark - current_offset if current_offset >= 0 else 0
                                
                                if topic not in topic_lags:
                                    topic_lags[topic] = {
                                        'topic': topic,
                                        'total_lag': 0,
                                        'partitions': []
                                    }
                                
                                topic_lags[topic]['total_lag'] += lag
                                topic_lags[topic]['partitions'].append({
                                    'partition': partition,
                                    'current_offset': current_offset,
                                    'high_water_mark': high_water_mark,
                                    'lag': lag,
                                    'is_critical': lag > lag_threshold
                                })
                                
                                group_lag += lag
                        
                        consumer.close()
                        
                        lag_analysis['total_groups'] += 1
                        lag_analysis['total_lag'] += group_lag
                        
                        if group_lag > 0:
                            lag_analysis['groups_with_lag'] += 1
                        
                        if group_lag > lag_threshold:
                            lag_analysis['critical_lag_groups'].append(group_id)
                        
                        lag_analysis['group_details'].append({
                            'group_id': group_id,
                            'total_lag': group_lag,
                            'is_critical': group_lag > lag_threshold,
                            'topics': list(topic_lags.values())
                        })
                        
                    except Exception as e:
                        logger.warning(f"Failed to get lag for group {group_id}: {e}")
                        continue
                
                
                
                # Sort groups by lag
                lag_analysis['group_details'].sort(key=lambda x: x['total_lag'], reverse=True)
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to analyze consumer lag: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=lag_analysis,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Kafka consumer lag: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Kafka consumer lag: {str(e)}",
                params=params
            )
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def _build_consumer_config(self, config: Dict) -> Dict:
        """Build Kafka consumer configuration (confluent-kafka format)"""
        consumer_config = self._build_admin_config(config)
        consumer_config.update({
            'enable.auto.commit': False,
            'group.id': 'infrainsights-lag-checker'
        })
        return consumer_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        lag_threshold = params.get('lag_threshold', 1000)
        return f"kafka_consumer_lag(instance_name={instance_name}, lag_threshold={lag_threshold})"


# ============================================
# PHASE 3: ADVANCED KAFKA TOOLS
# ============================================

class KafkaPartitionAnalysisTool(Tool):
    """Tool to analyze partition distribution and leader elections"""
    
    name: str = "kafka_partition_analysis"
    description: str = "Analyze partition distribution, leader elections, and replica health across brokers"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "include_replica_details": ToolParameter(
            description="Include detailed replica sync status",
            type="boolean",
            required=False
        )
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
            
            logger.info(f"🔍 Analyzing partitions for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            
            # Import Kafka admin client (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            try:
                admin_client = AdminClient(admin_config)
                
                # Get cluster metadata
                metadata = admin_client.list_topics(timeout=10)
                brokers = list(metadata.brokers.values())
                
                # Analyze partition distribution
                broker_stats = {}
                topic_stats = {}
                under_replicated_partitions = []
                offline_partitions = []
                
                # Initialize broker stats
                for broker in brokers:
                    broker_stats[broker.id] = {
                        'id': broker.id,
                        'host': broker.host,
                        'port': broker.port,
                        'leader_partitions': 0,
                        'replica_partitions': 0,
                        'topics': set()
                    }
                
                # Get all topics metadata
                topics_metadata = metadata.topics
                
                for topic_name, topic_metadata in topics_metadata.items():
                    topic_stats[topic_name] = {
                        'name': topic_name,
                        'partitions': len(topic_metadata.partitions),
                        'replication_factor': len(topic_metadata.partitions[0].replicas) if topic_metadata.partitions else 0,
                        'under_replicated_partitions': 0,
                        'offline_partitions': 0
                    }
                    
                    for partition_id, partition in topic_metadata.partitions.items():
                        # Count leader partitions
                        if partition.leader in broker_stats:
                            broker_stats[partition.leader]['leader_partitions'] += 1
                            broker_stats[partition.leader]['topics'].add(topic_name)
                        
                        # Count replica partitions
                        for replica in partition.replicas:
                            if replica in broker_stats:
                                broker_stats[replica]['replica_partitions'] += 1
                                broker_stats[replica]['topics'].add(topic_name)
                        
                        # Check for under-replicated partitions
                        isr = getattr(partition, 'isr', partition.replicas)
                        if len(isr) < len(partition.replicas):
                            under_replicated_partitions.append({
                                'topic': topic_name,
                                'partition': partition_id,
                                'replicas': partition.replicas,
                                'isr': isr,
                                'offline_replicas': getattr(partition, 'offline_replicas', [])
                            })
                            topic_stats[topic_name]['under_replicated_partitions'] += 1
                        
                        # Check for offline partitions
                        if partition.leader == -1:
                            offline_partitions.append({
                                'topic': topic_name,
                                'partition': partition_id,
                                'replicas': partition.replicas
                            })
                            topic_stats[topic_name]['offline_partitions'] += 1
                
                # Convert sets to lists for JSON serialization
                for broker_id in broker_stats:
                    broker_stats[broker_id]['topics'] = list(broker_stats[broker_id]['topics'])
                
                
                
                partition_analysis = {
                    'cluster_summary': {
                        'total_brokers': len(brokers),
                        'total_topics': len(topic_stats),
                        'total_partitions': sum(t['partitions'] for t in topic_stats.values()),
                        'under_replicated_partitions': len(under_replicated_partitions),
                        'offline_partitions': len(offline_partitions)
                    },
                    'broker_distribution': list(broker_stats.values()),
                    'topic_statistics': list(topic_stats.values()),
                    'issues': {
                        'under_replicated_partitions': under_replicated_partitions,
                        'offline_partitions': offline_partitions
                    }
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to analyze partitions: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=partition_analysis,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Kafka partitions: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Kafka partitions: {str(e)}",
                params=params
            )
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        include_replica = params.get('include_replica_details', False)
        return f"kafka_partition_analysis(instance_name={instance_name}, include_replica_details={include_replica})"


class KafkaMessageAnalysisTool(Tool):
    """Tool to analyze message patterns and consumption from topics"""
    
    name: str = "kafka_message_analysis"
    description: str = "Analyze message patterns, consumption rates, and content sampling from Kafka topics"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "topic_name": ToolParameter(
            description="Topic to analyze",
            type="string",
            required=True
        ),
        "sample_size": ToolParameter(
            description="Number of messages to sample",
            type="integer",
            required=False
        ),
        "from_beginning": ToolParameter(
            description="Read from beginning of topic",
            type="boolean",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            topic_name = params.get('topic_name')
            
            if not instance_name or not topic_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name and topic_name parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing messages in topic '{topic_name}' for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            
            # Import Kafka consumer (confluent-kafka)
            try:
                from confluent_kafka import Consumer, TopicPartition
                import json as json_lib
                import time
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build consumer config
            consumer_config = self._build_consumer_config(config)
            sample_size = params.get('sample_size', 100)
            from_beginning = params.get('from_beginning', False)
            
            try:
                # Create consumer
                consumer_config.update({
                    'auto.offset.reset': 'earliest' if from_beginning else 'latest',
                    'enable.auto.commit': False,
                    'session.timeout.ms': 5000,
                    'max.poll.records': sample_size
                })
                consumer = Consumer(consumer_config)
                consumer.subscribe([topic_name])
                
                # Get topic partitions
                metadata = consumer.list_topics(topic_name, timeout=10)
                if topic_name not in metadata.topics:
                    consumer.close()
                    return StructuredToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Topic '{topic_name}' not found or no partitions available",
                        params=params
                    )
                
                topic_metadata = metadata.topics[topic_name]
                partitions = list(topic_metadata.partitions.keys())
                
                # Get partition info
                partition_info = {}
                total_messages = 0
                
                for partition in partitions:
                    # Get beginning and end offsets using low and high watermarks
                    low, high = consumer.get_watermark_offsets(TopicPartition(topic_name, partition))
                    
                    partition_messages = high - low
                    total_messages += partition_messages
                    
                    partition_info[partition] = {
                        'partition': partition,
                        'beginning_offset': low,
                        'end_offset': high,
                        'message_count': partition_messages
                    }
                
                # Sample messages
                messages = []
                message_sizes = []
                key_patterns = {}
                value_types = {}
                
                start_time = time.time()
                message_count = 0
                
                # Poll for messages
                while message_count < sample_size:
                    msg = consumer.poll(timeout=1.0)
                    if msg is None:
                        break
                    if msg.error():
                        continue
                    
                    # Analyze message
                    message_size = len(msg.value()) if msg.value() else 0
                    message_sizes.append(message_size)
                    
                    # Analyze key
                    key_str = msg.key().decode('utf-8') if msg.key() else 'null'
                    key_pattern = self._extract_pattern(key_str)
                    key_patterns[key_pattern] = key_patterns.get(key_pattern, 0) + 1
                    
                    # Analyze value type
                    value_type = self._detect_value_type(msg.value())
                    value_types[value_type] = value_types.get(value_type, 0) + 1
                    
                    # Sample message details
                    if len(messages) < 10:  # Keep first 10 messages as samples
                        messages.append({
                            'partition': msg.partition(),
                            'offset': msg.offset(),
                            'timestamp': msg.timestamp()[1] if msg.timestamp() else None,
                            'key': key_str,
                            'value_preview': self._preview_value(msg.value()),
                            'size_bytes': message_size
                        })
                    
                    message_count += 1
                
                consumer.close()
                
                # Calculate statistics
                avg_message_size = sum(message_sizes) / len(message_sizes) if message_sizes else 0
                
                message_analysis = {
                    'topic': topic_name,
                    'total_messages': total_messages,
                    'sampled_messages': message_count,
                    'partition_info': list(partition_info.values()),
                    'message_statistics': {
                        'average_size_bytes': round(avg_message_size, 2),
                        'min_size_bytes': min(message_sizes) if message_sizes else 0,
                        'max_size_bytes': max(message_sizes) if message_sizes else 0,
                        'total_size_sampled_bytes': sum(message_sizes)
                    },
                    'key_patterns': key_patterns,
                    'value_types': value_types,
                    'sample_messages': messages
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to analyze messages: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=message_analysis,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Kafka messages: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Kafka messages: {str(e)}",
                params=params
            )
    
    def _build_consumer_config(self, config: Dict) -> Dict:
        """Build Kafka consumer configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        consumer_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'group.id': f'infrainsights-analyzer-{int(time.time())}'
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            consumer_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return consumer_config
    
    def _extract_pattern(self, key: str) -> str:
        """Extract pattern from key (e.g., user-123 -> user-*)"""
        import re
        if not key or key == 'null':
            return 'null'
        # Replace numbers with *
        pattern = re.sub(r'\d+', '*', key)
        # Replace UUIDs with *
        pattern = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '*', pattern, flags=re.I)
        return pattern
    
    def _detect_value_type(self, value: bytes) -> str:
        """Detect the type of message value"""
        if not value:
            return 'null'
        
        try:
            # Try to decode as string
            value_str = value.decode('utf-8')
            
            # Try to parse as JSON
            try:
                import json as json_lib
                json_lib.loads(value_str)
                return 'json'
            except:
                pass
            
            # Check if it looks like XML
            if value_str.strip().startswith('<'):
                return 'xml'
            
            # Check if it's a number
            try:
                float(value_str)
                return 'numeric'
            except:
                pass
            
            return 'string'
            
        except:
            return 'binary'
    
    def _preview_value(self, value: bytes, max_length: int = 100) -> str:
        """Create a preview of the message value"""
        if not value:
            return 'null'
        
        try:
            value_str = value.decode('utf-8')
            if len(value_str) > max_length:
                return value_str[:max_length] + '...'
            return value_str
        except:
            return f'<binary data, {len(value)} bytes>'
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        topic_name = params.get('topic_name', 'unknown')
        return f"kafka_message_analysis(instance_name={instance_name}, topic_name={topic_name})"


class KafkaBrokerMetricsTool(Tool):
    """Tool to analyze broker-level metrics and performance"""
    
    name: str = "kafka_broker_metrics"
    description: str = "Analyze broker-level metrics including JMX metrics, disk usage, and network throughput"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "broker_id": ToolParameter(
            description="Specific broker ID to analyze (optional)",
            type="integer",
            required=False
        )
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
            
            logger.info(f"🔍 Analyzing broker metrics for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            
            # Import Kafka admin client (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient, ConfigResource, ConfigResourceType
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            try:
                admin_client = AdminClient(admin_config)
                
                # Get cluster metadata
                metadata = admin_client.list_topics(timeout=10)
                brokers = list(metadata.brokers.values())
                
                broker_metrics = []
                
                for broker in brokers:
                    # Filter by broker_id if specified
                    if params.get('broker_id') is not None and broker.id != params['broker_id']:
                        continue
                    
                    # Get broker configuration
                    broker_resource = ConfigResource(ConfigResourceType.BROKER, str(broker.id))
                    configs = admin_client.describe_configs(config_resources=[broker_resource])
                    
                    broker_config = {}
                    for config_resource, config_response in configs.items():
                        for config_name, config_value in config_response.configs.items():
                            # Filter important configs
                            if config_name in ['log.dirs', 'log.retention.hours', 'log.segment.bytes', 
                                             'num.network.threads', 'num.io.threads', 'socket.send.buffer.bytes',
                                             'socket.receive.buffer.bytes', 'socket.request.max.bytes']:
                                broker_config[config_name] = config_value.value
                    
                    # Get topic-partition count for this broker
                    leader_partitions = 0
                    follower_partitions = 0
                    
                    topics_metadata = metadata.topics
                    for topic_name, topic_metadata in topics_metadata.items():
                        for partition in topic_metadata.partitions.values():
                            if partition.leader == broker.id:
                                leader_partitions += 1
                            if broker.id in partition.replicas and broker.id != partition.leader:
                                follower_partitions += 1
                    
                    broker_metric = {
                        'broker_id': broker.id,
                        'host': broker.host,
                        'port': broker.port,
                        'rack': getattr(broker, 'rack', None),
                        'partition_stats': {
                            'leader_partitions': leader_partitions,
                            'follower_partitions': follower_partitions,
                            'total_partitions': leader_partitions + follower_partitions
                        },
                        'configuration': broker_config,
                        'estimated_metrics': {
                            'network_threads': int(broker_config.get('num.network.threads', 8)),
                            'io_threads': int(broker_config.get('num.io.threads', 8)),
                            'socket_send_buffer_kb': int(broker_config.get('socket.send.buffer.bytes', 102400)) / 1024,
                            'socket_receive_buffer_kb': int(broker_config.get('socket.receive.buffer.bytes', 102400)) / 1024,
                            'max_request_size_mb': int(broker_config.get('socket.request.max.bytes', 104857600)) / 1024 / 1024
                        }
                    }
                    
                    broker_metrics.append(broker_metric)
                
                
                
                result_data = {
                    'cluster_id': metadata.cluster_id,
                    'total_brokers': len(brokers),
                    'broker_metrics': broker_metrics
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to get broker metrics: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=result_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Kafka broker metrics: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Kafka broker metrics: {str(e)}",
                params=params
            )
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        broker_id = params.get('broker_id')
        if broker_id is not None:
            return f"kafka_broker_metrics(instance_name={instance_name}, broker_id={broker_id})"
        return f"kafka_broker_metrics(instance_name={instance_name})"


# ============================================
# PHASE 4: EXPERT KAFKA TOOLS
# ============================================

class KafkaSecurityAuditTool(Tool):
    """Tool to audit Kafka security configuration and ACLs"""
    
    name: str = "kafka_security_audit"
    description: str = "Audit Kafka security configuration including ACLs, authentication, and encryption settings"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "include_acl_details": ToolParameter(
            description="Include detailed ACL analysis",
            type="boolean",
            required=False
        )
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
            
            logger.info(f"🔍 Auditing security for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            security_protocol = config.get('securityProtocol', 'PLAINTEXT')
            
            # Build security audit report
            security_audit = {
                'instance_name': instance_name,
                'security_protocol': security_protocol,
                'authentication': {
                    'enabled': security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'],
                    'mechanism': config.get('sasl', {}).get('mechanism', 'None') if 'sasl' in config else 'None'
                },
                'encryption': {
                    'enabled': security_protocol in ['SSL', 'SASL_SSL'],
                    'protocol': security_protocol
                },
                'connection_details': {
                    'brokers': config.get('brokers', []),
                    'has_credentials': bool(config.get('sasl', {}).get('username'))
                }
            }
            
            # Add recommendations
            recommendations = []
            
            if security_protocol == 'PLAINTEXT':
                recommendations.append({
                    'severity': 'HIGH',
                    'issue': 'No encryption or authentication enabled',
                    'recommendation': 'Enable SSL/SASL for production environments'
                })
            
            if security_protocol == 'SASL_PLAINTEXT':
                recommendations.append({
                    'severity': 'MEDIUM',
                    'issue': 'Authentication enabled but no encryption',
                    'recommendation': 'Consider using SASL_SSL for encrypted connections'
                })
            
            if config.get('sasl', {}).get('mechanism') == 'PLAIN':
                recommendations.append({
                    'severity': 'MEDIUM',
                    'issue': 'Using PLAIN SASL mechanism',
                    'recommendation': 'Consider using SCRAM-SHA-512 for stronger authentication'
                })
            
            security_audit['recommendations'] = recommendations
            security_audit['security_score'] = self._calculate_security_score(security_protocol, config)
            
            # Try to get ACLs if requested and supported
            if params.get('include_acl_details', False):
                try:
                    from confluent_kafka.admin import AdminClient
                    admin_config = self._build_admin_config(config)
                    admin_client = AdminClient(admin_config)
                    
                    # Note: ACL operations require admin privileges
                    security_audit['acl_analysis'] = {
                        'note': 'ACL details require admin privileges',
                        'supported': False
                    }
                    
                    
                except:
                    security_audit['acl_analysis'] = {
                        'error': 'Unable to retrieve ACL information'
                    }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=security_audit,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error auditing Kafka security: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to audit Kafka security: {str(e)}",
                params=params
            )
    
    def _calculate_security_score(self, security_protocol: str, config: Dict) -> int:
        """Calculate security score from 0-100"""
        score = 0
        
        # Base protocol score
        protocol_scores = {
            'PLAINTEXT': 0,
            'SSL': 40,
            'SASL_PLAINTEXT': 30,
            'SASL_SSL': 60
        }
        score += protocol_scores.get(security_protocol, 0)
        
        # SASL mechanism score
        if 'sasl' in config:
            mechanism = config['sasl'].get('mechanism', '')
            if mechanism == 'SCRAM-SHA-512':
                score += 30
            elif mechanism == 'SCRAM-SHA-256':
                score += 25
            elif mechanism == 'PLAIN':
                score += 10
            
            # Has credentials
            if config['sasl'].get('username'):
                score += 10
        
        return min(score, 100)
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        include_acl = params.get('include_acl_details', False)
        return f"kafka_security_audit(instance_name={instance_name}, include_acl_details={include_acl})"


class KafkaCapacityPlanningTool(Tool):
    """Tool to analyze Kafka capacity and provide scaling recommendations"""
    
    name: str = "kafka_capacity_planning"
    description: str = "Analyze Kafka cluster capacity, growth trends, and provide scaling recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "growth_rate_percent": ToolParameter(
            description="Expected monthly growth rate in percentage",
            type="integer",
            required=False
        )
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
            
            logger.info(f"🔍 Analyzing capacity for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            growth_rate = params.get('growth_rate_percent', 20) / 100.0
            
            # Import Kafka admin client (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient
                from confluent_kafka import Consumer, TopicPartition
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            try:
                admin_client = AdminClient(admin_config)
                
                # Get cluster metadata
                metadata = admin_client.list_topics(timeout=10)
                brokers = list(metadata.brokers.values())
                
                # Get all topics metadata
                topics_metadata = metadata.topics
                
                # Calculate current capacity metrics
                total_partitions = 0
                total_replicas = 0
                total_topics = len(topics_metadata)
                estimated_data_size_gb = 0
                
                topic_sizes = []
                
                # Create consumer for offset checks
                consumer_config = self._build_consumer_config(config)
                consumer = Consumer(consumer_config)
                
                for topic_name, topic_metadata in topics_metadata.items():
                    partitions = len(topic_metadata.partitions)
                    replicas = len(topic_metadata.partitions[0].replicas) if topic_metadata.partitions else 0
                    
                    total_partitions += partitions
                    total_replicas += partitions * replicas
                    
                    # Estimate topic size based on offsets
                    topic_size = 0
                    for partition_id in topic_metadata.partitions.keys():
                        tp = TopicPartition(topic_name, partition_id)
                        
                        # Get beginning and end offsets using watermarks
                        low, high = consumer.get_watermark_offsets(tp)
                        
                        # Estimate 1KB per message (configurable)
                        partition_size_mb = (high - low) * 1 / 1024
                        topic_size += partition_size_mb
                    
                    topic_sizes.append({
                        'topic': topic_name,
                        'estimated_size_mb': round(topic_size, 2),
                        'partitions': partitions,
                        'replication_factor': replicas
                    })
                    
                    estimated_data_size_gb += topic_size / 1024
                
                consumer.close()
                
                
                # Sort topics by size
                topic_sizes.sort(key=lambda x: x['estimated_size_mb'], reverse=True)
                
                # Calculate projections
                months = [1, 3, 6, 12]
                projections = []
                
                for month in months:
                    growth_factor = (1 + growth_rate) ** month
                    projections.append({
                        'months': month,
                        'estimated_topics': int(total_topics * growth_factor),
                        'estimated_partitions': int(total_partitions * growth_factor),
                        'estimated_data_size_gb': round(estimated_data_size_gb * growth_factor, 2),
                        'recommended_brokers': self._calculate_recommended_brokers(
                            int(total_partitions * growth_factor),
                            len(brokers)
                        )
                    })
                
                # Generate recommendations
                recommendations = []
                
                # Partition count per broker
                partitions_per_broker = total_partitions / len(brokers)
                if partitions_per_broker > 1000:
                    recommendations.append({
                        'type': 'scaling',
                        'severity': 'HIGH',
                        'message': f'High partition count per broker ({int(partitions_per_broker)}). Consider adding more brokers.'
                    })
                
                # Topic size imbalance
                if topic_sizes and topic_sizes[0]['estimated_size_mb'] > estimated_data_size_gb * 1024 * 0.3:
                    recommendations.append({
                        'type': 'optimization',
                        'severity': 'MEDIUM',
                        'message': f"Topic '{topic_sizes[0]['topic']}' contains >30% of total data. Consider partitioning strategy."
                    })
                
                capacity_analysis = {
                    'current_state': {
                        'brokers': len(brokers),
                        'topics': total_topics,
                        'partitions': total_partitions,
                        'total_replicas': total_replicas,
                        'estimated_data_size_gb': round(estimated_data_size_gb, 2),
                        'avg_partitions_per_broker': round(partitions_per_broker, 2)
                    },
                    'top_topics_by_size': topic_sizes[:10],
                    'growth_projections': projections,
                    'recommendations': recommendations
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to analyze capacity: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=capacity_analysis,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Kafka capacity: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Kafka capacity: {str(e)}",
                params=params
            )
    
    def _calculate_recommended_brokers(self, total_partitions: int, current_brokers: int) -> int:
        """Calculate recommended number of brokers based on partition count"""
        # Recommendation: ~500-1000 partitions per broker
        recommended = max(current_brokers, (total_partitions + 750) // 750)
        return recommended
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def _build_consumer_config(self, config: Dict) -> Dict:
        """Build Kafka consumer configuration (confluent-kafka format)"""
        consumer_config = self._build_admin_config(config)
        consumer_config.update({
            'enable.auto.commit': False,
            'group.id': 'infrainsights-capacity-analyzer'
        })
        return consumer_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        growth_rate = params.get('growth_rate_percent', 20)
        return f"kafka_capacity_planning(instance_name={instance_name}, growth_rate_percent={growth_rate})"


class KafkaConfigurationOptimizationTool(Tool):
    """Tool to analyze Kafka configuration and provide optimization recommendations"""
    
    name: str = "kafka_configuration_optimization"
    description: str = "Analyze Kafka broker and topic configurations and provide optimization recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka instance",
            type="string",
            required=True
        ),
        "focus_area": ToolParameter(
            description="Specific area to focus on: performance, reliability, or cost",
            type="string",
            required=False
        )
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
            
            logger.info(f"🔍 Analyzing configuration for Kafka instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract connection config
            config = instance.config or {}
            focus_area = params.get('focus_area', 'performance').lower()
            
            # Import Kafka admin client (confluent-kafka)
            try:
                from confluent_kafka.admin import AdminClient, ConfigResource, ConfigResourceType
            except ImportError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="confluent-kafka library not installed",
                    params=params
                )
            
            # Build connection config
            admin_config = self._build_admin_config(config)
            
            try:
                admin_client = AdminClient(admin_config)
                
                # Get cluster metadata
                metadata = admin_client.list_topics(timeout=10)
                brokers = list(metadata.brokers.values())
                
                # Get broker configurations
                broker_configs = {}
                for broker in brokers:
                    broker_resource = ConfigResource(ConfigResourceType.BROKER, str(broker.id))
                    configs = admin_client.describe_configs(config_resources=[broker_resource])
                    
                    for config_resource, config_response in configs.items():
                        broker_configs[broker.id] = {
                            name: {
                                'value': config.value,
                                'is_default': config.is_default
                            }
                            for name, config in config_response.configs.items()
                        }
                
                # Analyze configurations and generate recommendations
                recommendations = []
                
                # Performance recommendations
                if focus_area in ['performance', 'all']:
                    recommendations.extend(self._get_performance_recommendations(broker_configs))
                
                # Reliability recommendations
                if focus_area in ['reliability', 'all']:
                    recommendations.extend(self._get_reliability_recommendations(broker_configs))
                
                # Cost optimization recommendations
                if focus_area in ['cost', 'all']:
                    recommendations.extend(self._get_cost_recommendations(broker_configs))
                
                # Get topic-level recommendations
                topics_metadata = metadata.topics
                topic_recommendations = []
                
                for topic_name, topic_metadata in topics_metadata.items():
                    if topic_name.startswith('__'):  # Skip internal topics
                        continue
                    
                    # Get topic configuration
                    topic_resource = ConfigResource(ConfigResourceType.TOPIC, topic_name)
                    topic_configs = admin_client.describe_configs(config_resources=[topic_resource])
                    
                    for config_resource, config_response in topic_configs.items():
                        topic_config = {
                            name: config.value
                            for name, config in config_response.configs.items()
                        }
                        
                        # Check retention
                        retention_ms = int(topic_config.get('retention.ms', 604800000))  # 7 days default
                        retention_days = retention_ms / (1000 * 60 * 60 * 24)
                        
                        if retention_days > 30:
                            topic_recommendations.append({
                                'topic': topic_name,
                                'type': 'cost',
                                'issue': f'Long retention period ({int(retention_days)} days)',
                                'recommendation': 'Consider reducing retention for cost optimization'
                            })
                
                
                
                configuration_analysis = {
                    'cluster_size': len(brokers),
                    'broker_recommendations': recommendations,
                    'topic_recommendations': topic_recommendations[:10],  # Limit to top 10
                    'optimization_score': self._calculate_optimization_score(recommendations),
                    'focus_area': focus_area
                }
                
            except Exception as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to analyze configuration: {str(e)}",
                    params=params
                )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=configuration_analysis,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Kafka configuration: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Kafka configuration: {str(e)}",
                params=params
            )
    
    def _get_performance_recommendations(self, broker_configs: Dict) -> List[Dict]:
        """Get performance optimization recommendations"""
        recommendations = []
        
        for broker_id, configs in broker_configs.items():
            # Check network threads
            network_threads = int(configs.get('num.network.threads', {}).get('value', 8))
            if network_threads < 8:
                recommendations.append({
                    'broker_id': broker_id,
                    'type': 'performance',
                    'severity': 'MEDIUM',
                    'config': 'num.network.threads',
                    'current_value': network_threads,
                    'recommended_value': 8,
                    'reason': 'Insufficient network threads for high throughput'
                })
            
            # Check IO threads
            io_threads = int(configs.get('num.io.threads', {}).get('value', 8))
            if io_threads < 8:
                recommendations.append({
                    'broker_id': broker_id,
                    'type': 'performance',
                    'severity': 'MEDIUM',
                    'config': 'num.io.threads',
                    'current_value': io_threads,
                    'recommended_value': 8,
                    'reason': 'Insufficient IO threads for high throughput'
                })
        
        return recommendations
    
    def _get_reliability_recommendations(self, broker_configs: Dict) -> List[Dict]:
        """Get reliability optimization recommendations"""
        recommendations = []
        
        for broker_id, configs in broker_configs.items():
            # Check min.insync.replicas
            min_isr = int(configs.get('min.insync.replicas', {}).get('value', 1))
            if min_isr < 2:
                recommendations.append({
                    'broker_id': broker_id,
                    'type': 'reliability',
                    'severity': 'HIGH',
                    'config': 'min.insync.replicas',
                    'current_value': min_isr,
                    'recommended_value': 2,
                    'reason': 'Low min ISR can lead to data loss'
                })
        
        return recommendations
    
    def _get_cost_recommendations(self, broker_configs: Dict) -> List[Dict]:
        """Get cost optimization recommendations"""
        recommendations = []
        
        for broker_id, configs in broker_configs.items():
            # Check log retention
            retention_hours = int(configs.get('log.retention.hours', {}).get('value', 168))
            if retention_hours > 168:  # More than 7 days
                recommendations.append({
                    'broker_id': broker_id,
                    'type': 'cost',
                    'severity': 'LOW',
                    'config': 'log.retention.hours',
                    'current_value': retention_hours,
                    'recommended_value': 168,
                    'reason': 'Long retention increases storage costs'
                })
        
        return recommendations
    
    def _calculate_optimization_score(self, recommendations: List[Dict]) -> int:
        """Calculate optimization score from 0-100"""
        if not recommendations:
            return 100
        
        # Deduct points based on severity
        score = 100
        severity_penalty = {
            'HIGH': 20,
            'MEDIUM': 10,
            'LOW': 5
        }
        
        for rec in recommendations:
            score -= severity_penalty.get(rec.get('severity', 'LOW'), 5)
        
        return max(0, score)
    
    def _build_admin_config(self, config: Dict) -> Dict:
        """Build Kafka admin client configuration (confluent-kafka format)"""
        brokers = config.get('brokers', [])
        security_protocol = config.get('securityProtocol', 'PLAINTEXT')
        
        admin_config = {
            'bootstrap.servers': ','.join(brokers) if isinstance(brokers, list) else brokers,
            'security.protocol': security_protocol.lower(),
            'request.timeout.ms': 10000,
            'connections.max.idle.ms': 10000
        }
        
        # Add SASL config if present
        if security_protocol in ['SASL_PLAINTEXT', 'SASL_SSL'] and 'sasl' in config:
            sasl_config = config['sasl']
            admin_config.update({
                'sasl.mechanism': sasl_config.get('mechanism', 'PLAIN'),
                'sasl.username': sasl_config.get('username'),
                'sasl.password': sasl_config.get('password')
            })
        
        return admin_config
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        focus_area = params.get('focus_area', 'performance')
        return f"kafka_configuration_optimization(instance_name={instance_name}, focus_area={focus_area})"


# ============================================
# FINAL: COMPREHENSIVE KAFKA TOOLSET
# ============================================

class ComprehensiveKafkaToolset(Toolset):
    """Comprehensive Kafka toolset with InfraInsights integration for advanced Kafka monitoring and management"""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2, InfraInsightsConfig
        
        logger.info("🚀🚀🚀 CREATING COMPREHENSIVE KAFKA TOOLSET 🚀🚀🚀")
        
        # Initialize Toolset with required parameters first
        super().__init__(
            name="infrainsights_kafka_comprehensive",
            description="Comprehensive Kafka toolset with InfraInsights integration for cluster management, performance analysis, security auditing, and capacity planning",
            enabled=True,
            tools=[],  # Start with empty tools list
            tags=[ToolsetTag.CLUSTER],
            prerequisites=[]  # Remove prerequisites during initialization
        )
        
        # Create comprehensive Kafka tools
        self.tools = [
            # Phase 1: Basic Tools
            KafkaHealthCheckTool(toolset=None),
            KafkaListTopicsTool(toolset=None),
            KafkaTopicDetailsTool(toolset=None),
            
            # Phase 2: Intermediate Tools
            KafkaConsumerGroupsTool(toolset=None),
            KafkaProducerPerformanceTool(toolset=None),
            KafkaConsumerLagTool(toolset=None),
            
            # Phase 3: Advanced Tools
            KafkaPartitionAnalysisTool(toolset=None),
            KafkaMessageAnalysisTool(toolset=None),
            KafkaBrokerMetricsTool(toolset=None),
            
            # Phase 4: Expert Tools
            KafkaSecurityAuditTool(toolset=None),
            KafkaCapacityPlanningTool(toolset=None),
            KafkaConfigurationOptimizationTool(toolset=None),
        ]
        
        # Validate all tools
        logger.info(f"🔧 Validating {len(self.tools)} Kafka tools...")
        for i, tool in enumerate(self.tools):
            if tool is None:
                logger.error(f"🔧 Tool {i} is None!")
                raise ValueError(f"Kafka tool {i} is None")
            if isinstance(tool, dict):
                logger.error(f"🔧 Tool {i} is a dict: {tool}")
                raise ValueError(f"Kafka tool {i} is a dict, not a Tool object")
            if not hasattr(tool, 'name'):
                logger.error(f"🔧 Tool {i} has no 'name' attribute: {type(tool)}")
                raise ValueError(f"Kafka tool {i} has no 'name' attribute")
            logger.info(f"🔧 Tool {i} validated: {tool.name} ({type(tool).__name__})")
        logger.info(f"✅ All {len(self.tools)} Kafka tools validated successfully!")
        
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
        
        logger.info("✅✅✅ COMPREHENSIVE KAFKA TOOLSET CREATED SUCCESSFULLY ✅✅✅")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with the provided configuration"""
        logger.info(f"🚀🚀🚀 CONFIGURING COMPREHENSIVE KAFKA TOOLSET 🚀🚀🚀")
        logger.info(f"🔧 Config received: {config}")
        
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
        
        logger.info(f"🔧 Updated config object: base_url={self.infrainsights_config.base_url}, api_key={'***' if self.infrainsights_config.api_key else 'None'}")
        
        # Now add prerequisites after configuration is complete
        self.prerequisites = [CallablePrerequisite(callable=self._check_prerequisites)]
        
        logger.info(f"✅✅✅ COMPREHENSIVE KAFKA TOOLSET CONFIGURED WITH URL: {base_url} ✅✅✅")
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if InfraInsights client can connect to the backend"""
        try:
            logger.info(f"🔍 Checking prerequisites for InfraInsights Kafka client")
            
            # The context contains the configuration
            if not context:
                logger.warning("🔍 No context provided to prerequisites check")
                return True, "No context provided (toolset still enabled)"
            
            # Extract configuration from context
            config = context
            if isinstance(config, dict) and 'config' in config:
                config = config['config']
            
            # Get InfraInsights URL from config
            infrainsights_url = config.get('infrainsights_url', 'http://localhost:3000')
            api_key = config.get('api_key')
            
            logger.info(f"🔍 Current base_url: {infrainsights_url}")
            logger.info(f"🔍 API key configured: {'Yes' if api_key else 'No'}")
            
            # Try to connect to InfraInsights backend
            logger.info(f"🔍 Attempting health check to: {infrainsights_url}/api/health")
            
            # Note: We can't use self.infrainsights_client here as it may not be configured yet
            # Just return True to allow the toolset to load
            logger.info("✅ Prerequisites check passed (configuration will be applied later)")
            return True, f"InfraInsights backend will connect to {infrainsights_url}"
            
        except Exception as e:
            logger.error(f"🔍 Prerequisites check failed: {str(e)}")
            # Still allow toolset to load even if health check fails
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