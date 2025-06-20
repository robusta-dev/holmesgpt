import os
import pytest
from pathlib import Path

from holmes.plugins.toolsets.coralogix.api import DEFAULT_LOG_COUNT, build_query_string
from holmes.plugins.toolsets.coralogix.toolset_coralogix_logs import (
    CoralogixLogsToolset,
)
from holmes.plugins.toolsets.coralogix.utils import (
    CoralogixConfig,
    build_coralogix_link_to_logs,
    parse_logs,
    normalize_datetime,
    stringify_flattened_logs,
)
from holmes.plugins.toolsets.logging_utils.logging_api import FetchPodLogsParams

THIS_DIR = os.path.dirname(__file__)
FIXTURES_DIR = os.path.join(THIS_DIR, "fixtures")


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


@pytest.fixture
def coralogix_config():
    return CoralogixConfig(
        api_key="dummy_api_key",
        team_hostname="my-team",
        domain="eu2.coralogix.com",
    )


@pytest.fixture
def coralogix_toolset(coralogix_config):
    toolset = CoralogixLogsToolset()
    # Mock prerequisites check for unit tests
    toolset.config = coralogix_config
    return toolset


def test_format_logs(raw_logs_result, formatted_logs):
    actual_output = stringify_flattened_logs(parse_logs(raw_logs_result))
    logs_match = actual_output.strip() == formatted_logs.strip()
    actual_file_path_for_debugging = os.path.join(
        FIXTURES_DIR, "formatted_logs.txt.actual"
    )
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


@pytest.mark.parametrize(
    "params, expected_query_part",
    [
        (
            {"namespace": "application", "pod_name": "my-app"},
            f'source logs | lucene \'kubernetes.namespace_name:"application" AND kubernetes.pod_name:"my-app"\' | limit {DEFAULT_LOG_COUNT}',
        ),
        (
            {
                "pod_name": "web",
                "namespace": "staging",
                "limit": 20,
            },
            'source logs | lucene \'kubernetes.namespace_name:"staging" AND kubernetes.pod_name:"web"\' | limit 20',
        ),
        (
            {
                "pod_name": "web",
                "namespace": "staging",
                "limit": 30,
                "filter": "foo bar",
            },
            'source logs | lucene \'kubernetes.namespace_name:"staging" AND kubernetes.pod_name:"web" AND log:"foo bar"\' | limit 30',
        ),
    ],
)
def test_build_query_string(coralogix_config, params, expected_query_part):
    query = build_query_string(coralogix_config, FetchPodLogsParams(**params))
    print(f"** EXPECTED: {expected_query_part}")
    print(f"** ACTUAL: {query}")
    assert query == expected_query_part


def test_build_coralogix_link_to_logs(coralogix_config):
    query = "source logs | lucene 'app:test AND level:error' | limit 100"
    start = "2024-05-01T10:00:00Z"
    end = "2024-05-01T11:00:00Z"
    expected_url = f"https://{coralogix_config.team_hostname}.app.{coralogix_config.domain}/#/query-new/logs?query=source+logs+%7C+lucene+%27app%3Atest+AND+level%3Aerror%27+%7C+limit+100&querySyntax=dataprime&time=from:{start},to:{end}"
    actual_url = build_coralogix_link_to_logs(coralogix_config, query, start, end)
    assert actual_url == expected_url
