import os

from tests.utils.kafka import wait_for_containers


dir_path = os.path.dirname(os.path.realpath(__file__))
FIXTURE_FOLDER = os.path.join(dir_path, "fixtures", "test_tool_kafka")
wait_for_containers(FIXTURE_FOLDER)
