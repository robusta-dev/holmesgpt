
import os
import subprocess
import pytest
import random
import string
from confluent_kafka.admin import AdminClient, NewTopic
from holmes.plugins.toolsets.kafka import (
    ListKafkaConsumers,
    DescribeConsumerGroup,
    ListTopics,
    DescribeTopic,
    FindConsumerGroupsByTopic
)
from tests.utils.kafka import docker_not_available, wait_for_containers, wait_for_kafka_ready

dir_path = os.path.dirname(os.path.realpath(__file__))
FIXTURE_FOLDER = os.path.join(dir_path, "fixtures", "test_tool_kafka")
KAFKA_BOOTSTRAP_SERVER = "localhost:9092"

skip_docker, skip_docker_reason = docker_not_available()
pytestmark = pytest.mark.skipif(
    skip_docker,
    reason=skip_docker_reason
)

@pytest.fixture(scope="module", autouse=True)
def admin_client():
    config = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVER,
        "client.id": 'holmes_kafka_tools_test'
    }
    return AdminClient(config)

@pytest.fixture(scope="module", autouse=True)
def docker_compose(admin_client):
    try:
        subprocess.Popen("docker compose up -d".split(), cwd=FIXTURE_FOLDER, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if not wait_for_containers(FIXTURE_FOLDER):
            raise Exception("Containers failed to start properly")

        if not wait_for_kafka_ready(admin_client):
            raise Exception("Kafka failed to initialize properly")

        yield

    finally:
        subprocess.Popen("docker compose down".split(), cwd=FIXTURE_FOLDER, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

@pytest.fixture(scope="module", autouse=True)
def test_topic(admin_client):
    """Create a test topic and clean it up after the test"""
    random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    topic_name = f"test_topic_{random_string}"
    new_topic = NewTopic(
        topic_name,
        num_partitions=1,
        replication_factor=1
    )
    futures = admin_client.create_topics([new_topic])
    futures[topic_name].result()
    yield topic_name
    admin_client.delete_topics([topic_name])

def test_list_kafka_consumers(admin_client):
    tool = ListKafkaConsumers(admin_client)
    result = tool.invoke({})

    assert "errors: []" in result
    assert "valid:" in result
    assert tool.get_parameterized_one_liner({}) == "Listed all Kafka consumer groups in the cluster"

def test_describe_consumer_group(admin_client):
    tool = DescribeConsumerGroup(admin_client)

    result = tool.invoke({"group_id": "test_group"})
    assert "group_id: test_group" in result
    assert tool.get_parameterized_one_liner({"group_id": "test_group"}) == "Described consumer group: test_group"

def test_list_topics(admin_client, test_topic):
    tool = ListTopics(admin_client)
    result = tool.invoke({})

    assert "topics" in result
    assert test_topic in result

    assert tool.get_parameterized_one_liner({}) == "Listed all Kafka topics in the cluster"

def test_describe_topic(admin_client, test_topic):
    tool = DescribeTopic(admin_client)
    result = tool.invoke({"topic_name": test_topic})

    assert "configuration:" not in result
    assert "partitions:" in result
    assert "topic:" in result

    assert tool.get_parameterized_one_liner({"topic_name": test_topic}) == f"Described topic: {test_topic}"

def test_describe_topic_with_configuration(admin_client, test_topic):
    tool = DescribeTopic(admin_client)
    result = tool.invoke({"topic_name": test_topic, "fetch_configuration": True})

    print(result)
    assert "configuration:" in result
    assert "partitions:" in result
    assert "topic:" in result

    assert tool.get_parameterized_one_liner({"topic_name": test_topic}) == f"Described topic: {test_topic}"

def test_find_consumer_groups_by_topic(admin_client, test_topic):
    tool = FindConsumerGroupsByTopic(admin_client)
    result = tool.invoke({"topic_name": test_topic})

    assert result == f"No consumer group were found for topic {test_topic}"
    assert tool.get_parameterized_one_liner({"topic_name": test_topic}) == f"Found consumer groups for topic: {test_topic}"

def test_tool_error_handling(admin_client):

    tool = DescribeTopic(admin_client)
    result = tool.invoke({"topic_name": "non_existent_topic"})

    print(result)
    assert isinstance(result, str)
    assert "topic: non_existent_topic" in result
