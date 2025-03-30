import logging
from pydantic import BaseModel, ConfigDict
import yaml
from typing import Any, Dict, List, Optional, Union, Tuple
from holmes.core.tools import (
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
)
<<<<<<< HEAD
from holmes.plugins.toolsets.grafana.common import get_param_or_raise
=======
from holmes.plugins.toolsets.utils import (
    TOOLSET_CONFIG_MISSING_ERROR,
    get_param_or_raise,
)
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
from confluent_kafka.admin import (
    AdminClient,
    BrokerMetadata,
    ClusterMetadata,
    ConfigResource,
    GroupMember,
    GroupMetadata,
    KafkaError,
    ListConsumerGroupsResult,
    MemberAssignment,
    MemberDescription,
    ConsumerGroupDescription,
    PartitionMetadata,
    TopicMetadata,
    _TopicPartition as TopicPartition,
)
import sys # Import sys for stdout.flush

class KafkaClusterConfig(BaseModel):
    name: str
    kafka_broker: str
    kafka_security_protocol: Optional[str] = None
    kafka_sasl_mechanism: Optional[str] = None
    kafka_username: Optional[str] = None
    kafka_password: Optional[str] = None
    kafka_client_id: Optional[str] = "holmes-kafka-client"


class KafkaConfig(BaseModel):
    kafka_clusters: List[KafkaClusterConfig]


class KafkaClusterConfig(BaseModel):
    name: str
    kafka_broker: str
    kafka_security_protocol: Optional[str] = None
    kafka_sasl_mechanism: Optional[str] = None
    kafka_username: Optional[str] = None
    kafka_password: Optional[str] = None
    kafka_client_id: Optional[str] = "holmes-kafka-client"


class KafkaConfig(BaseModel):
    kafka_clusters: List[KafkaClusterConfig]


def convert_to_dict(obj: Any) -> Union[str, Dict]:
    if isinstance(
        obj,
        (
            ClusterMetadata,
            BrokerMetadata,
            TopicMetadata,
            PartitionMetadata,
            GroupMember,
            GroupMetadata,
            ConsumerGroupDescription,
            MemberDescription,
            MemberAssignment,
        ),
    ):
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
    if isinstance(obj, TopicPartition):
        return str(obj)
    if isinstance(obj, KafkaError):
        return str(obj)
    return obj


def format_list_consumer_group_errors(errors: Optional[List]) -> str:
    errors_text = ""
    if errors:
        if len(errors) > 1:
            errors_text = "# Some errors happened while listing consumer groups:\n\n"
        errors_text = errors_text + "\n\n".join(
            [f"## Error:\n{str(error)}" for error in errors]
        )

    return errors_text


class BaseKafkaTool(Tool):
    toolset: "KafkaToolset"

    def get_kafka_client(self, cluster_name: Optional[str]) -> AdminClient:
        """
        Retrieves the correct Kafka AdminClient based on the cluster name.
        """
<<<<<<< HEAD
        print(f"BaseKafkaTool.get_kafka_client: cluster_name={cluster_name}") # Print input
        sys.stdout.flush()
        if len(self.toolset.clients) == 1:
            print("BaseKafkaTool.get_kafka_client: Single client found, returning it.") # Print client selection
            sys.stdout.flush()
=======
        if len(self.toolset.clients) == 1:
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
            return next(
                iter(self.toolset.clients.values())
            )  # Return the only available client

        if not cluster_name:
<<<<<<< HEAD
            error_msg = "BaseKafkaTool.get_kafka_client: Missing cluster name to resolve Kafka client"
            print(error_msg) # Print error
            sys.stdout.flush()
            raise Exception(error_msg)

        if cluster_name in self.toolset.clients:
            print(f"BaseKafkaTool.get_kafka_client: Found client for cluster '{cluster_name}'.") # Print client found
            sys.stdout.flush()
            return self.toolset.clients[cluster_name]

        error_msg = f"BaseKafkaTool.get_kafka_client: Failed to resolve Kafka client. No matching cluster: {cluster_name}"
        print(error_msg) # Print error
        sys.stdout.flush()
        raise Exception(error_msg)
=======
            raise Exception("Missing cluster name to resolve Kafka client")

        if cluster_name in self.toolset.clients:
            return self.toolset.clients[cluster_name]

        raise Exception(
            f"Failed to resolve Kafka client. No matching cluster: {cluster_name}"
        )
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80


class ListKafkaConsumers(BaseKafkaTool):
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="list_kafka_consumers",
            description="Lists all Kafka consumer groups in the cluster",
            parameters={
                "kafka_cluster_name": ToolParameter(
                    description="The name of the kafka cluster to investigate",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict) -> str:
        print("ListKafkaConsumers._invoke: started, params=", params) # Print entry and params
        sys.stdout.flush()
        try:
            kafka_cluster_name = get_param_or_raise(params, "kafka_cluster_name")
            client = self.get_kafka_client(kafka_cluster_name)
            if client is None:
<<<<<<< HEAD
                error_msg = "ListKafkaConsumers._invoke: No admin_client on toolset. This toolset is misconfigured."
                print(error_msg) # Print error
                sys.stdout.flush()
                return error_msg

            print("ListKafkaConsumers._invoke: Calling client.list_consumer_groups()") # Print API call start
            sys.stdout.flush()
=======
                return "No admin_client on toolset. This toolset is misconfigured."

>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
            futures = client.list_consumer_groups()
            list_groups_result: ListConsumerGroupsResult = futures.result()
            print("ListKafkaConsumers._invoke: client.list_consumer_groups() result=", list_groups_result) # Print API call result
            sys.stdout.flush()

            groups_text = ""
            if list_groups_result.valid and len(list_groups_result.valid) > 0:
                groups = []
                for group in list_groups_result.valid:
                    groups.append(
                        {
                            "group_id": group.group_id,
                            "is_simple_consumer_group": group.is_simple_consumer_group,
                            "state": str(group.state),
                            "type": str(group.type),
                        }
                    )
                groups_text = yaml.dump({"consumer_groups": groups})
            else:
                groups_text = "No consumer group was found"

            errors_text = format_list_consumer_group_errors(list_groups_result.errors)

            result_text = groups_text
            if errors_text:
                result_text = result_text + "\n\n" + errors_text
            print("ListKafkaConsumers._invoke: returning result_text=", result_text) # Print final result
            sys.stdout.flush()
            return result_text
        except Exception as e:
            error_msg = f"ListKafkaConsumers._invoke: Failed to list consumer groups: {str(e)}"
            print(error_msg) # Print error
            sys.stdout.flush()
            logging.error(error_msg)
            return error_msg
        finally:
            print("ListKafkaConsumers._invoke: finished") # Print exit
            sys.stdout.flush()

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Listed all Kafka consumer groups in the cluster {params['kafka_cluster_name']}"


class DescribeConsumerGroup(BaseKafkaTool):
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="describe_consumer_group",
            description="Describes a specific Kafka consumer group",
            parameters={
                "kafka_cluster_name": ToolParameter(
                    description="The name of the kafka cluster to investigate",
                    type="string",
                    required=True,
                ),
                "group_id": ToolParameter(
                    description="The ID of the consumer group to describe",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict) -> str:
        group_id = params["group_id"]
        print(f"DescribeConsumerGroup._invoke: started, group_id={group_id}, params={params}") # Print entry and params
        sys.stdout.flush()
        try:
            kafka_cluster_name = get_param_or_raise(params, "kafka_cluster_name")
            client = self.get_kafka_client(kafka_cluster_name)
            if client is None:
<<<<<<< HEAD
                error_msg = "DescribeConsumerGroup._invoke: No admin_client on toolset. This toolset is misconfigured."
                print(error_msg) # Print error
                sys.stdout.flush()
                return error_msg

            print(f"DescribeConsumerGroup._invoke: Calling client.describe_consumer_groups([group_id={group_id}])") # Print API call start
            sys.stdout.flush()
=======
                return "No admin_client on toolset. This toolset is misconfigured."

>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
            futures = client.describe_consumer_groups([group_id])

            if futures.get(group_id):
                group_metadata = futures.get(group_id).result()
                print("DescribeConsumerGroup._invoke: client.describe_consumer_groups() result=", group_metadata) # Print API call result
                sys.stdout.flush()
                return yaml.dump(convert_to_dict(group_metadata))
            else:
                return "Group not found"
        except Exception as e:
            error_msg = f"DescribeConsumerGroup._invoke: Failed to describe consumer group {group_id}: {str(e)}"
            print(error_msg) # Print error
            sys.stdout.flush()
            logging.error(error_msg)
            return error_msg
        finally:
            print("DescribeConsumerGroup._invoke: finished") # Print exit
            sys.stdout.flush()


    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Described consumer group: {params['group_id']} in cluster {params['kafka_cluster_name']}"


class ListTopics(BaseKafkaTool):
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="list_topics",
            description="Lists all Kafka topics in the cluster",
            parameters={
                "kafka_cluster_name": ToolParameter(
                    description="The name of the kafka cluster to investigate",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict) -> str:
        print("ListTopics._invoke: started, params=", params) # Print entry and params
        sys.stdout.flush()
        try:
            kafka_cluster_name = get_param_or_raise(params, "kafka_cluster_name")
            client = self.get_kafka_client(kafka_cluster_name)
            if client is None:
<<<<<<< HEAD
                error_msg = "ListTopics._invoke: No admin_client on toolset. This toolset is misconfigured."
                print(error_msg) # Print error
                sys.stdout.flush()
                return error_msg

            print("ListTopics._invoke: Calling client.list_topics()") # Print API call start
            sys.stdout.flush()
            topics = client.list_topics()
            print("ListTopics._invoke: client.list_topics() result=", topics) # Print API call result
            sys.stdout.flush()
=======
                return "No admin_client on toolset. This toolset is misconfigured."

            topics = client.list_topics()
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
            return yaml.dump(convert_to_dict(topics))
        except Exception as e:
            error_msg = f"ListTopics._invoke: Failed to list topics: {str(e)}"
            print(error_msg) # Print error
            sys.stdout.flush()
            logging.error(error_msg)
            return error_msg
        finally:
            print("ListTopics._invoke: finished") # Print exit
            sys.stdout.flush()


    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Listed all Kafka topics in the cluster {params['kafka_cluster_name']}"


class DescribeTopic(BaseKafkaTool):
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="describe_topic",
            description="Describes details of a specific Kafka topic",
            parameters={
                "kafka_cluster_name": ToolParameter(
                    description="The name of the kafka cluster to investigate",
                    type="string",
                    required=True,
                ),
                "topic_name": ToolParameter(
                    description="The name of the topic to describe",
                    type="string",
                    required=True,
                ),
                "fetch_configuration": ToolParameter(
                    description="If true, also fetches the topic configuration. defaults to false",
                    type="boolean",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict) -> str:
        topic_name = params["topic_name"]
        print(f"DescribeTopic._invoke: started, topic_name={topic_name}, params={params}") # Print entry and params
        sys.stdout.flush()
        try:
            kafka_cluster_name = get_param_or_raise(params, "kafka_cluster_name")
            client = self.get_kafka_client(kafka_cluster_name)
            if client is None:
<<<<<<< HEAD
                error_msg = "DescribeTopic._invoke: No admin_client on toolset. This toolset is misconfigured."
                print(error_msg) # Print error
                sys.stdout.flush()
                return error_msg
=======
                return "No admin_client on toolset. This toolset is misconfigured."
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
            config_future = None
            fetch_config = str(params.get("fetch_configuration", False)).lower() == "true"
            print(f"DescribeTopic._invoke: fetch_configuration parameter = {fetch_config}") # Print fetch_configuration param
            sys.stdout.flush()

            if fetch_config:
                resource = ConfigResource("topic", topic_name)
<<<<<<< HEAD
                print(f"DescribeTopic._invoke: Calling client.describe_configs([resource={resource}])") # Print API call start
                sys.stdout.flush()
=======
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
                configs = client.describe_configs([resource])
                config_future = next(iter(configs.values()))
                print("DescribeTopic._invoke: client.describe_configs() result=", configs) # Print API call result
                sys.stdout.flush()


            print(f"DescribeTopic._invoke: Calling client.list_topics(topic_name={topic_name})") # Print API call start
            sys.stdout.flush()
            topic_metadata_result = client.list_topics(topic_name)
            print("DescribeTopic._invoke: client.list_topics() result=", topic_metadata_result) # Print API call result
            sys.stdout.flush()
            metadata = topic_metadata_result.topics[topic_name]

<<<<<<< HEAD
=======
            metadata = client.list_topics(topic_name).topics[topic_name]
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80

            metadata = convert_to_dict(metadata)
            result: dict = {"metadata": metadata}

            if config_future:
                config = config_future.result()
                result["configuration"] = convert_to_dict(config)

            print("DescribeTopic._invoke: returning result=", result) # Print final result
            sys.stdout.flush()
            return yaml.dump(result)
        except Exception as e:
            error_msg = f"DescribeTopic._invoke: Failed to describe topic {topic_name}: {str(e)}"
            print(error_msg) # Print error
            sys.stdout.flush()
            logging.error(error_msg, exc_info=True)
            return error_msg
        finally:
            print("DescribeTopic._invoke: finished") # Print exit
            sys.stdout.flush()


    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Described topic: {params['topic_name']} in cluster {params['kafka_cluster_name']}"


def group_has_topic(
    consumer_group_description: ConsumerGroupDescription, topic_name: str
):
    for member in consumer_group_description.members:
        if len(member.assignment.topic_partitions) > 0:
            member_topic_name = member.assignment.topic_partitions[0].topic
            if topic_name == member_topic_name:
                return True
    return False


class FindConsumerGroupsByTopic(BaseKafkaTool):
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="find_consumer_groups_by_topic",
            description="Finds all consumer groups consuming from a specific topic",
            parameters={
                "kafka_cluster_name": ToolParameter(
                    description="The name of the kafka cluster to investigate",
                    type="string",
                    required=True,
                ),
                "topic_name": ToolParameter(
                    description="The name of the topic to find consumers for",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict) -> str:
        topic_name = params["topic_name"]
        print(f"FindConsumerGroupsByTopic._invoke: started, topic_name={topic_name}, params={params}") # Print entry and params
        sys.stdout.flush()
        try:
            kafka_cluster_name = get_param_or_raise(params, "kafka_cluster_name")
            client = self.get_kafka_client(kafka_cluster_name)
            if client is None:
<<<<<<< HEAD
                error_msg = "FindConsumerGroupsByTopic._invoke: No admin_client on toolset. This toolset is misconfigured."
                print(error_msg) # Print error
                sys.stdout.flush()
                return error_msg

            print("FindConsumerGroupsByTopic._invoke: Calling client.list_consumer_groups()") # Print API call start
            sys.stdout.flush()
=======
                return "No admin_client on toolset. This toolset is misconfigured."

>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
            groups_future = client.list_consumer_groups()
            groups: ListConsumerGroupsResult = groups_future.result()
            print("FindConsumerGroupsByTopic._invoke: client.list_consumer_groups() result=", groups) # Print API call result
            sys.stdout.flush()


            consumer_groups = []
            group_ids_to_evaluate = []
            if groups.valid:
                group_ids_to_evaluate = group_ids_to_evaluate + [
                    group.group_id for group in groups.valid
                ]

            if len(group_ids_to_evaluate) > 0:
<<<<<<< HEAD
                print(f"FindConsumerGroupsByTopic._invoke: Calling client.describe_consumer_groups(group_ids_to_evaluate={group_ids_to_evaluate})") # Print API call start
                sys.stdout.flush()
=======
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
                consumer_groups_futures = client.describe_consumer_groups(
                    group_ids_to_evaluate
                )
                print("FindConsumerGroupsByTopic._invoke: client.describe_consumer_groups() result=", consumer_groups_futures) # Print API call result
                sys.stdout.flush()


                for (
                    group_id,
                    consumer_group_description_future,
                ) in consumer_groups_futures.items():
                    consumer_group_description = (
                        consumer_group_description_future.result()
                    )
                    if group_has_topic(consumer_group_description, topic_name):
                        consumer_groups.append(
                            convert_to_dict(consumer_group_description)
                        )

            errors_text = format_list_consumer_group_errors(groups.errors)

            result_text = None
            if len(consumer_groups) > 0:
                result_text = yaml.dump(consumer_groups)
            else:
                result_text = f"No consumer group were found for topic {topic_name}"

            if errors_text:
                result_text = result_text + "\n\n" + errors_text

            print("FindConsumerGroupsByTopic._invoke: returning result_text=", result_text) # Print final result
            sys.stdout.flush()
            return result_text
        except Exception as e:
            error_msg = (
                f"FindConsumerGroupsByTopic._invoke: Failed to find consumer groups for topic {topic_name}: {str(e)}"
            )
            print(error_msg) # Print error
            sys.stdout.flush()
            logging.error(error_msg)
            return error_msg
        finally:
            print("FindConsumerGroupsByTopic._invoke: finished") # Print exit
            sys.stdout.flush()


    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Found consumer groups for topic: {params['topic_name']} in cluster {params['kafka_cluster_name']}"


class ListKafkaClusters(BaseKafkaTool):
    def __init__(self, toolset: "KafkaToolset"):
        super().__init__(
            name="list_kafka_clusters",
            description="Lists all available Kafka clusters configured in HolmesGPT",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Dict) -> str:
<<<<<<< HEAD
        print("ListKafkaClusters._invoke: started, params=", params) # Print entry and params
        sys.stdout.flush()
        cluster_names = list(self.toolset.clients.keys())
        result_text = "Available Kafka Clusters:\n" + "\n".join(cluster_names)
        print("ListKafkaClusters._invoke: returning result_text=", result_text) # Print final result
        sys.stdout.flush()
        return result_text
=======
        cluster_names = list(self.toolset.clients.keys())
        return "Available Kafka Clusters:\n" + "\n".join(cluster_names)
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Listed all available Kafka clusters"


class KafkaToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    clients: Dict[str, AdminClient] = {}

    def __init__(self):
        super().__init__(
            name="kafka/admin",
            description="Fetches metadata from multiple Kafka clusters",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/kafka.html",
            icon_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT-cR1JrBgJxB_SPVKUIRwtiHnR8qBvLeHXjQ&s",
            tags=[ToolsetTag.CORE],
            tools=[
                ListKafkaClusters(self),
                ListKafkaConsumers(self),
                DescribeConsumerGroup(self),
                ListTopics(self),
                DescribeTopic(self),
                FindConsumerGroupsByTopic(self),
            ],
        )

<<<<<<< HEAD
    def prerequisites_callable(self, config: Dict[str, Any]) -> bool:
        print("KafkaToolset.prerequisites_callable: started, config=", config) # Print entry and config
        sys.stdout.flush()
        if not config:
            print("KafkaToolset.prerequisites_callable: No config provided, returning False") # Print no config
            sys.stdout.flush()
            return False

        try:
            kafka_config = KafkaConfig(**config)
            print("KafkaToolset.prerequisites_callable: KafkaConfig parsed successfully=", kafka_config) # Print parsed config
            sys.stdout.flush()
=======
    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR
        errors = []
        try:
            kafka_config = KafkaConfig(**config)
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80

            for cluster in kafka_config.kafka_clusters:
                try:
                    logging.info(f"Setting up Kafka client for cluster: {cluster.name}")
<<<<<<< HEAD
                    print(f"KafkaToolset.prerequisites_callable: Setting up Kafka client for cluster: {cluster.name}") # Print cluster setup start
                    sys.stdout.flush()
=======
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80
                    admin_config = {
                        "bootstrap.servers": cluster.kafka_broker,
                        "client.id": cluster.kafka_client_id,
                    }

                    if cluster.kafka_security_protocol:
                        admin_config["security.protocol"] = (
                            cluster.kafka_security_protocol
                        )
                    if cluster.kafka_sasl_mechanism:
                        admin_config["sasl.mechanisms"] = cluster.kafka_sasl_mechanism
                    if cluster.kafka_username and cluster.kafka_password:
                        admin_config["sasl.username"] = cluster.kafka_username
                        admin_config["sasl.password"] = cluster.kafka_password

<<<<<<< HEAD
                    print(f"KafkaToolset.prerequisites_callable: AdminClient config=", admin_config) # Print AdminClient config
                    sys.stdout.flush()
                    client = AdminClient(admin_config)
                    self.clients[cluster.name] = client  # Store in dictionary
                    print(f"KafkaToolset.prerequisites_callable: AdminClient created and stored for cluster {cluster.name}") # Print client creation success
                    sys.stdout.flush()

                except Exception as e:
                    logging.error(
                        f"Failed to set up Kafka client for {cluster.name}: {str(e)}"
                    )
                    print(f"KafkaToolset.prerequisites_callable: Failed to set up Kafka client for {cluster.name}: {str(e)}") # Print client creation failure
                    sys.stdout.flush()

            is_success = len(self.clients) > 0
            print(f"KafkaToolset.prerequisites_callable: returning {is_success}, clients count={len(self.clients)}") # Print final result of prerequisite check
            sys.stdout.flush()
            return is_success
        except Exception as e:
            logging.exception("KafkaToolset.prerequisites_callable: Failed to set up Kafka toolset")
            print(f"KafkaToolset.prerequisites_callable: Exception during setup: {str(e)}") # Print general setup failure
            sys.stdout.flush()
            return False
        finally:
            print("KafkaToolset.prerequisites_callable: finished") # Print exit
            sys.stdout.flush()

=======
                    client = AdminClient(admin_config)
                    self.clients[cluster.name] = client  # Store in dictionary
                except Exception as e:
                    message = (
                        f"Failed to set up Kafka client for {cluster.name}: {str(e)}"
                    )
                    logging.error(message)
                    errors.append(message)

            return len(self.clients) > 0, "\n".join(errors)
        except Exception as e:
            logging.exception("Failed to set up Kafka toolset")
            return False, str(e)
>>>>>>> 1e9d049effcd2d4964590f830ae1d3970f080a80

    def get_example_config(self) -> Dict[str, Any]:
        example_config = KafkaConfig(
            kafka_clusters=[
                KafkaClusterConfig(
                    name="us-west-kafka",
                    kafka_broker="broker1.example.com:9092,broker2.example.com:9092",
                    kafka_security_protocol="SASL_SSL",
                    kafka_sasl_mechanism="PLAIN",
                    kafka_username="{{ env.KAFKA_USERNAME }}",
                    kafka_password="{{ env.KAFKA_PASSWORD }}",
                ),
                KafkaClusterConfig(
                    name="eu-central-kafka",
                    kafka_broker="broker3.example.com:9092",
                    kafka_security_protocol="SSL",
                ),
            ]
        )
        return example_config.model_dump()
