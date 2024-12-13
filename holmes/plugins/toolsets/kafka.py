
import logging
from pydantic import BaseModel
import yaml
from typing import Any, Dict, List, Optional
from holmes.core.tools import StaticPrerequisite, Tool, ToolParameter, Toolset, ToolsetTag
from confluent_kafka.admin import AdminClient, BrokerMetadata, ClusterMetadata, ConfigResource, GroupMember, GroupMetadata, ListConsumerGroupsResult, MemberAssignment, MemberDescription, ConsumerGroupDescription, PartitionMetadata, TopicMetadata
from confluent_kafka import KafkaException

def convert_to_dict(obj:Any):
    if isinstance(obj, (ClusterMetadata, BrokerMetadata, TopicMetadata,
                        PartitionMetadata, GroupMember, GroupMetadata,
                        ConsumerGroupDescription, MemberDescription,
                        MemberAssignment)):
        result = {}
        for key, value in vars(obj).items():
            if value is not None and value != -1 and value != []:
                if isinstance(value, dict):
                    result[key] = {k: convert_to_dict(v) for k, v in value.items()}
                elif isinstance(value, list):
                    result[key] = [convert_to_dict(item) for item in value]
                else:
                    result[key] = convert_to_dict(value)
        return result
    return obj

class KafkaConfig(BaseModel):
    brokers: List[str]
    security_protocol: Optional[str] = None
    sasl_mechanism: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None

class ListKafkaConsumers(Tool):
    def __init__(self, admin_client: AdminClient):
        super().__init__(
            name="list_kafka_consumers",
            description="Lists all Kafka consumer groups in the cluster",
            parameters={},
        )
        self._admin_client = admin_client

    def invoke(self, params: Dict) -> str:
        try:
            futures = self._admin_client.list_consumer_groups()
            groups:ListConsumerGroupsResult = futures.result()
            return yaml.dump(groups)
        except KafkaException as e:
            error_msg = f"Failed to list consumer groups: {str(e)}"
            logging.error(error_msg)
            raise e

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Listed all Kafka consumer groups in the cluster"

class DescribeConsumerGroup(Tool):
    def __init__(self, admin_client: AdminClient):
        super().__init__(
            name="describe_consumer_group",
            description="Describes a specific Kafka consumer group",
            parameters={
                "group_id": ToolParameter(
                    description="The ID of the consumer group to describe",
                    type="string",
                    required=True,
                )
            },
        )
        self._admin_client = admin_client

    def invoke(self, params: Dict) -> str:
        print(params)
        group_id = params["group_id"]
        try:
            futures = self._admin_client.describe_consumer_groups([group_id])
            print(futures)
            print(futures.get(group_id))
            if futures.get(group_id):
                group_metadata = futures.get(group_id).result()
                return yaml.dump(convert_to_dict(group_metadata))
            else:
                return "Group not found"
        except KafkaException as e:
            error_msg = f"Failed to describe consumer group {group_id}: {str(e)}"
            logging.error(error_msg)
            return error_msg

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Described consumer group: {params['group_id']}"

class ListTopics(Tool):
    def __init__(self, admin_client: AdminClient):
        super().__init__(
            name="list_topics",
            description="Lists all Kafka topics in the cluster",
            parameters={},
        )
        self._admin_client = admin_client

    def invoke(self, params: Dict) -> str:
        try:
            topics = self._admin_client.list_topics()
            return yaml.dump(convert_to_dict(topics))
        except KafkaException as e:
            error_msg = f"Failed to list topics: {str(e)}"
            logging.error(error_msg)
            return error_msg

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Listed all Kafka topics in the cluster"

class DescribeTopic(Tool):
    def __init__(self, admin_client: AdminClient):
        super().__init__(
            name="describe_topic",
            description="Describes details of a specific Kafka topic",
            parameters={
                "topic_name": ToolParameter(
                    description="The name of the topic to describe",
                    type="string",
                    required=True,
                ),
                "fetch_configuration": ToolParameter(
                    description="If true, also fetches the topic configuration. defaults to false",
                    type="boolean",
                    required=False,
                )
            },
        )
        self._admin_client = admin_client

    def invoke(self, params: Dict) -> str:
        topic_name = params["topic_name"]
        try:
            config_future = None
            if str(params.get("fetch_configuration", False)).lower() == "true":
                resource = ConfigResource('topic', topic_name)
                configs = self._admin_client.describe_configs([resource])
                config_future = next(iter(configs.values()))

            metadata = self._admin_client.list_topics(topic_name).topics[topic_name]
            result = convert_to_dict(metadata)

            if config_future:
                config = config_future.result()
                result["configuration"] = convert_to_dict(config)

            return yaml.dump(result)
        except KafkaException as e:
            error_msg = f"Failed to describe topic {topic_name}: {str(e)}"
            logging.error(error_msg)
            return error_msg

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Described topic: {params['topic_name']}"

def group_has_topic(consumer_group_description:ConsumerGroupDescription, topic_name:str):
    print(convert_to_dict(consumer_group_description))
    for member in consumer_group_description.members:
        if len(member.assignment.topic_partitions) > 0:
            member_topic_name = member.assignment.topic_partitions[0].topic
            if topic_name == member_topic_name:
                return True
    return False

class FindConsumerGroupsByTopic(Tool):
    def __init__(self, admin_client: AdminClient):
        super().__init__(
            name="find_consumer_groups_by_topic",
            description="Finds all consumer groups consuming from a specific topic",
            parameters={
                "topic_name": ToolParameter(
                    description="The name of the topic to find consumers for",
                    type="string",
                    required=True,
                )
            },
        )
        self._admin_client = admin_client

    def invoke(self, params: Dict) -> str:
        topic_name = params["topic_name"]
        try:
            groups_future = self._admin_client.list_consumer_groups()
            groups:ListConsumerGroupsResult = groups_future.result()

            consumer_groups = []
            group_ids_to_evaluate = []
            if groups.valid:
                group_ids_to_evaluate = group_ids_to_evaluate + [group.group_id for group in groups.valid]
            if groups.errors:
                group_ids_to_evaluate = group_ids_to_evaluate + [group.group_id for group in groups.errors]

            if len(group_ids_to_evaluate) > 0:
                consumer_groups_futures = self._admin_client.describe_consumer_groups(group_ids_to_evaluate)

                for group_id, consumer_group_description_future in consumer_groups_futures.items():
                    consumer_group_description = consumer_group_description_future.result()
                    if group_has_topic(consumer_group_description, topic_name):
                        consumer_groups.append(convert_to_dict(consumer_group_description))

            if len(consumer_groups) == 0:
                return f"No consumer group were found for topic {topic_name}"
            return yaml.dump(consumer_groups)
        except KafkaException as e:
            error_msg = f"Failed to find consumer groups for topic {topic_name}: {str(e)}"
            logging.error(error_msg)
            return error_msg

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Found consumer groups for topic: {params['topic_name']}"

class KafkaToolset(Toolset):
    def __init__(
        self,
        config: Optional[KafkaConfig] = None
    ):
        try:
            if config:
                admin_config = {
                    'bootstrap.servers': config.brokers,
                    'client.id': config.client_id or "holmes-kafka-core-toolset",
                    'security.protocol': config.security_protocol,
                    'sasl.mechanisms': config.sasl_mechanism,
                    'sasl.username': config.username,
                    'sasl.password': config.password
                }

                admin_client = AdminClient(admin_config)

                kafka_prereq = StaticPrerequisite(
                    enabled=True,
                    disabled_reason="Kafka admin client is available"
                )
            else:
                admin_client = None
                kafka_prereq = StaticPrerequisite(
                    enabled=False,
                    disabled_reason=f"Kafka client not configured"
                )
        except Exception as e:
            admin_client = None
            kafka_prereq = StaticPrerequisite(
                enabled=False,
                disabled_reason=f"Failed to initialize Kafka admin client: {str(e)}"
            )

        super().__init__(
            name="kafka_tools",
            description="Fetches metadata from Kafka",
            prerequisites=[kafka_prereq],
            icon_url="https://en.wikipedia.org/wiki/Apache_Kafka#/media/File:Apache_Kafka_logo.svg",
            tags=[ToolsetTag.CORE],
            tools=[
                ListKafkaConsumers(admin_client),
                DescribeConsumerGroup(admin_client),
                ListTopics(admin_client),
                DescribeTopic(admin_client),
                FindConsumerGroupsByTopic(admin_client),
            ],
        )
