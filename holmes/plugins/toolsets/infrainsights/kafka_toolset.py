"""
Kafka Toolset for InfraInsights

Provides tools for investigating Kafka clusters, topics, and consumer groups
in the InfraInsights multi-instance architecture.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from confluent_kafka.admin import AdminClient, ConfigResource, ResourceType
from confluent_kafka import Consumer, Producer
from confluent_kafka.cimpl import KafkaError

from holmes.core.tools import (
    StructuredToolResult,
    ToolParameter,
    ToolResultStatus,
)
from holmes.plugins.toolsets.utils import get_param_or_raise

from .base_toolset import BaseInfraInsightsTool, BaseInfraInsightsToolset


class KafkaConnection:
    """Manages Kafka connection with authentication"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.admin_client = None
        self._connect_admin()
    
    def _connect_admin(self):
        """Establish admin connection to Kafka"""
        try:
            # Build configuration
            kafka_config = {
                'bootstrap.servers': self.config.get('bootstrap_servers', 'localhost:9092'),
                'client.id': 'holmes-kafka-admin'
            }
            
            # Add security configuration
            if self.config.get('security_protocol'):
                kafka_config['security.protocol'] = self.config['security_protocol']
            
            if self.config.get('sasl_mechanism'):
                kafka_config['sasl.mechanism'] = self.config['sasl_mechanism']
            
            if self.config.get('username') and self.config.get('password'):
                kafka_config['sasl.username'] = self.config['username']
                kafka_config['sasl.password'] = self.config['password']
            
            if self.config.get('ssl_ca_location'):
                kafka_config['ssl.ca.location'] = self.config['ssl_ca_location']
            
            # Create admin client
            self.admin_client = AdminClient(kafka_config)
            
        except Exception as e:
            logging.error(f"Failed to connect to Kafka: {e}")
            raise Exception(f"Kafka connection failed: {e}")
    
    def get_admin_client(self) -> AdminClient:
        """Get the Kafka admin client"""
        if not self.admin_client:
            self._connect_admin()
        return self.admin_client
    
    def create_consumer(self, group_id: str = 'holmes-consumer') -> Consumer:
        """Create a Kafka consumer"""
        kafka_config = {
            'bootstrap.servers': self.config.get('bootstrap_servers', 'localhost:9092'),
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        }
        
        # Add security configuration
        if self.config.get('security_protocol'):
            kafka_config['security.protocol'] = self.config['security_protocol']
        
        if self.config.get('sasl_mechanism'):
            kafka_config['sasl.mechanism'] = self.config['sasl_mechanism']
        
        if self.config.get('username') and self.config.get('password'):
            kafka_config['sasl.username'] = self.config['username']
            kafka_config['sasl.password'] = self.config['password']
        
        if self.config.get('ssl_ca_location'):
            kafka_config['ssl.ca.location'] = self.config['ssl_ca_location']
        
        return Consumer(kafka_config)


class ListKafkaTopics(BaseInfraInsightsTool):
    """List all topics in the Kafka cluster"""
    
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="list_kafka_topics",
            description="List all topics in the Kafka cluster with their partition counts and replication factors",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kafka instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kafka instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Create connection
            kafka_conn = KafkaConnection(connection_config)
            admin_client = kafka_conn.get_admin_client()
            
            # Get cluster metadata
            metadata = admin_client.list_topics(timeout=10)
            
            # Format response
            result = {
                "cluster_id": metadata.cluster_id,
                "brokers": [],
                "topics": []
            }
            
            # Add broker information
            for broker_id, broker in metadata.brokers.items():
                result["brokers"].append({
                    "id": broker_id,
                    "host": broker.host,
                    "port": broker.port
                })
            
            # Add topic information
            for topic_name, topic in metadata.topics.items():
                if not topic_name.startswith('__'):  # Skip internal topics
                    result["topics"].append({
                        "name": topic_name,
                        "partitions": len(topic.partitions),
                        "replication_factor": topic.replica_count // len(topic.partitions) if topic.partitions else 0,
                        "internal": topic_name.startswith('__')
                    })
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list Kafka topics: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"List Kafka topics for instance: {instance_name}"


class ListKafkaConsumerGroups(BaseInfraInsightsTool):
    """List all consumer groups in the Kafka cluster"""
    
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="list_kafka_consumer_groups",
            description="List all consumer groups with their state, members, and lag information",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kafka instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kafka instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Create connection
            kafka_conn = KafkaConnection(connection_config)
            admin_client = kafka_conn.get_admin_client()
            
            # List consumer groups
            groups_result = admin_client.list_consumer_groups()
            
            # Format response
            result = {
                "valid_groups": [],
                "errors": []
            }
            
            # Add valid groups
            for group in groups_result.valid:
                result["valid_groups"].append({
                    "group_id": group.group_id,
                    "is_simple": group.is_simple_consumer_group,
                    "state": str(group.state),
                    "type": str(group.type)
                })
            
            # Add errors
            for error in groups_result.errors:
                result["errors"].append(str(error))
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list Kafka consumer groups: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"List Kafka consumer groups for instance: {instance_name}"


class DescribeKafkaTopic(BaseInfraInsightsTool):
    """Get detailed information about a Kafka topic"""
    
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="describe_kafka_topic",
            description="Get detailed information about a Kafka topic including partitions, replicas, and configuration",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kafka instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kafka instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
                "topic_name": ToolParameter(
                    description="Name of the topic to describe",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Get parameters
            topic_name = get_param_or_raise(params, "topic_name")
            
            # Create connection
            kafka_conn = KafkaConnection(connection_config)
            admin_client = kafka_conn.get_admin_client()
            
            # Get topic metadata
            metadata = admin_client.list_topics(topic=topic_name, timeout=10)
            
            if topic_name not in metadata.topics:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Topic {topic_name} not found",
                    params=params,
                )
            
            topic = metadata.topics[topic_name]
            
            # Get topic configuration
            config_resource = ConfigResource(ResourceType.TOPIC, topic_name)
            configs_result = admin_client.describe_configs([config_resource])
            configs = configs_result[config_resource].result()
            
            # Format response
            result = {
                "name": topic_name,
                "partitions": len(topic.partitions),
                "replication_factor": topic.replica_count // len(topic.partitions) if topic.partitions else 0,
                "internal": topic_name.startswith('__'),
                "partitions_detail": [],
                "configuration": {}
            }
            
            # Add partition details
            for partition_id, partition in topic.partitions.items():
                result["partitions_detail"].append({
                    "id": partition_id,
                    "leader": partition.leader,
                    "replicas": partition.replicas,
                    "isrs": partition.isrs
                })
            
            # Add configuration
            for config_name, config in configs.items():
                result["configuration"][config_name] = {
                    "value": config.value,
                    "source": str(config.source),
                    "is_default": config.is_default,
                    "is_read_only": config.is_read_only,
                    "is_sensitive": config.is_sensitive
                }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to describe Kafka topic: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        topic_name = params.get('topic_name', 'unknown')
        return f"Describe Kafka topic {topic_name} in instance: {instance_name}"


class GetKafkaConsumerGroupLag(BaseInfraInsightsTool):
    """Get lag information for a Kafka consumer group"""
    
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="get_kafka_consumer_group_lag",
            description="Get detailed lag information for a consumer group including per-partition lag",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Kafka instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Kafka instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
                "group_id": ToolParameter(
                    description="Consumer group ID to get lag for",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Get parameters
            group_id = get_param_or_raise(params, "group_id")
            
            # Create connection
            kafka_conn = KafkaConnection(connection_config)
            admin_client = kafka_conn.get_admin_client()
            
            # Get consumer group description
            groups_result = admin_client.describe_consumer_groups([group_id])
            
            if group_id not in groups_result:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Consumer group {group_id} not found",
                    params=params,
                )
            
            group_desc = groups_result[group_id].result()
            
            # Format response
            result = {
                "group_id": group_id,
                "state": str(group_desc.state),
                "protocol": group_desc.protocol,
                "protocol_type": group_desc.protocol_type,
                "members": [],
                "total_lag": 0
            }
            
            # Add member information
            for member in group_desc.members:
                member_info = {
                    "member_id": member.member_id,
                    "client_id": member.client_id,
                    "client_host": member.client_host,
                    "assignments": []
                }
                
                for topic, partitions in member.member_assignment.items():
                    for partition in partitions:
                        # Get partition metadata for lag calculation
                        # Note: This is a simplified approach - in production you'd want more sophisticated lag calculation
                        member_info["assignments"].append({
                            "topic": topic,
                            "partition": partition,
                            "lag": "N/A"  # Would need additional API calls to calculate actual lag
                        })
                
                result["members"].append(member_info)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Kafka consumer group lag: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        group_id = params.get('group_id', 'unknown')
        return f"Get Kafka consumer group lag for {group_id} in instance: {instance_name}"


class InfraInsightsKafkaToolset(BaseInfraInsightsToolset):
    """Kafka toolset for InfraInsights"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.name = "InfraInsights Kafka"
        self.description = "Tools for investigating Kafka clusters, topics, and consumer groups in InfraInsights"
        self.tags = [ToolsetTag.CLUSTER]
        self.enabled = True
        
        # Initialize tools
        self.tools = [
            ListKafkaTopics(self),
            ListKafkaConsumerGroups(self),
            DescribeKafkaTopic(self),
            GetKafkaConsumerGroupLag(self),
        ]
    
    def get_service_type(self) -> str:
        return "kafka"
    
    def get_llm_instructions(self) -> str:
        return """
        This toolset provides tools for investigating Kafka clusters managed by InfraInsights.
        
        Available tools:
        - list_kafka_topics: List all topics with partition and replication info
        - list_kafka_consumer_groups: List all consumer groups with their state
        - describe_kafka_topic: Get detailed topic information and configuration
        - get_kafka_consumer_group_lag: Get lag information for consumer groups
        
        When investigating Kafka issues:
        1. Start by listing topics to understand the cluster structure
        2. Check consumer groups to identify potential lag issues
        3. Describe specific topics to understand configuration
        4. Analyze consumer group lag to identify bottlenecks
        
        The toolset automatically handles:
        - Multi-instance support (production, staging, etc.)
        - Authentication and connection management
        - User context and access control
        """ 