import os
import pytest
from pathlib import Path

from holmes.plugins.toolsets.coralogix.utils import format_logs, normalize_datetime

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


@pytest.mark.parametrize(
    "input_date,expected_output",
    [
        ("", "UNKNOWN_TIMESTAMP"),
        (None, "UNKNOWN_TIMESTAMP"),
        # Invalid inputs should be returned as-is
        ("not a date", "not a date"),
        ("2023/01/01", "2023/01/01"),
        ("01-01-2023", "01-01-2023"),
        ("12:30:45", "12:30:45"),
        # Basic ISO format
        ("2023-01-01T12:30:45", "2023-01-01T12:30:45.000000Z"),
        # With microseconds
        ("2023-01-01T12:30:45.123456", "2023-01-01T12:30:45.123456Z"),
        # With Z suffix
        ("2023-01-01T12:30:45Z", "2023-01-01T12:30:45.000000Z"),
        ("2023-01-01T12:30:45.123456Z", "2023-01-01T12:30:45.123456Z"),
        # Truncating microseconds beyond 6 digits
        ("2023-01-01T12:30:45.1234567", "2023-01-01T12:30:45.123456Z"),
        ("2023-01-01T12:30:45.1234567890Z", "2023-01-01T12:30:45.123456Z"),
    ],
)
def test_normalize_datetime_valid_inputs(input_date, expected_output):
    assert normalize_datetime(input_date) == expected_output
