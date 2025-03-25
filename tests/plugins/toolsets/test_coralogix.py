import os
import pytest
from pathlib import Path

from holmes.plugins.toolsets.coralogix.utils import format_logs

THIS_DIR = os.path.dirname(__file__)
FIXTURES_DIR = os.path.join(THIS_DIR, "fixtures", "test_coralogix")


def read_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read().strip()


def write_file(file_path: Path, content: str):
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)


@pytest.fixture()
def raw_logs_result():
    file_path = os.path.join(FIXTURES_DIR, "raw_logs_response.txt")
    return read_file(Path(file_path))


@pytest.fixture()
def formatted_logs():
    file_path = os.path.join(FIXTURES_DIR, "formatted_logs.txt")
    return read_file(Path(file_path))


def test_format_logs(raw_logs_result, formatted_logs):
    actual_output = format_logs(
        raw_logs_result, add_namespace_tag=False, add_pod_tag=False
    )
    logs_match = actual_output.strip() == formatted_logs.strip()
    actual_file_path_for_debugging = os.path.join(
        FIXTURES_DIR, "formatted_logs.txt.actual"
    )
    print("** actual_output v")
    print(actual_output)
    print("** actual_output ^")
    if not logs_match:
        write_file(Path(actual_file_path_for_debugging), actual_output)

    assert logs_match, f"Values mismatch. Run the following command to compare expected with actual: `diff {os.path.join(FIXTURES_DIR, 'formatted_logs.txt')} {actual_file_path_for_debugging}`"
