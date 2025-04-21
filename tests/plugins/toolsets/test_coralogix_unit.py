import os
import pytest
from pathlib import Path

from holmes.plugins.toolsets.coralogix.toolset_coralogix_logs import (
    CoralogixLogsToolset,
    FetchLogs,
)
from holmes.plugins.toolsets.coralogix.utils import (
    CoralogixConfig,
    build_coralogix_link_to_logs,
    format_kubernetes_info,
    format_logs,
    normalize_datetime,
)

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


@pytest.fixture
def fetch_logs_tool(coralogix_toolset):
    return FetchLogs(toolset=coralogix_toolset)


def test_format_logs(raw_logs_result, formatted_logs):
    actual_output = format_logs(
        raw_logs_result, add_namespace_tag=False, add_pod_tag=False
    )
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
        ({}, "source logs | lucene '' | limit 1000"),
        ({"log_count": 50}, "source logs | lucene '' | limit 50"),
        (
            {"app_name": "my-app"},
            "source logs | lucene 'kubernetes.labels.app:my-app' | limit 1000",
        ),
        (
            {"namespace_name": "prod"},
            "source logs | lucene 'kubernetes.namespace_name:prod' | limit 1000",
        ),
        (
            {"pod_name": "pod-123"},
            "source logs | lucene 'kubernetes.pod_name:pod-123' | limit 1000",
        ),
        (
            {"app_name": "api", "namespace_name": "dev", "pod_name": "api-abc"},
            "source logs | lucene 'kubernetes.namespace_name:dev AND kubernetes.pod_name:api-abc AND kubernetes.labels.app:api' | limit 1000",
        ),
        (
            {"app_name": "web", "namespace_name": "staging", "log_count": 20},
            "source logs | lucene 'kubernetes.namespace_name:staging AND kubernetes.labels.app:web' | limit 20",
        ),
    ],
)
def test_fetch_logs_get_query_string(
    fetch_logs_tool, coralogix_config, params, expected_query_part
):
    query = fetch_logs_tool._get_query_string(coralogix_config, params)
    assert query == expected_query_part


@pytest.mark.parametrize(
    "kubernetes, add_namespace, add_pod, expected",
    [
        (None, True, True, ""),
        ({}, True, True, ""),
        ({"pod_name": "p1"}, True, True, 'pod_name="p1"'),
        ({"namespace_name": "ns1"}, True, True, 'namespace_name="ns1"'),
        (
            {"pod_name": "p1", "namespace_name": "ns1"},
            True,
            True,
            'pod_name="p1" namespace_name="ns1"',
        ),
        ({"pod_name": "p1", "namespace_name": "ns1"}, False, True, 'pod_name="p1"'),
        (
            {"pod_name": "p1", "namespace_name": "ns1"},
            True,
            False,
            'namespace_name="ns1"',
        ),
        ({"pod_name": "p1", "namespace_name": "ns1"}, False, False, ""),
        ({"other_key": "v"}, True, True, ""),
    ],
)
def test_format_kubernetes_info(kubernetes, add_namespace, add_pod, expected):
    assert format_kubernetes_info(kubernetes, add_namespace, add_pod) == expected


def test_build_coralogix_link_to_logs(coralogix_config):
    query = "source logs | lucene 'app:test AND level:error' | limit 100"
    start = "2024-05-01T10:00:00Z"
    end = "2024-05-01T11:00:00Z"
    expected_url = f"https://{coralogix_config.team_hostname}.app.{coralogix_config.domain}/#/query-new/logs?query=source+logs+%7C+lucene+%27app%3Atest+AND+level%3Aerror%27+%7C+limit+100&querySyntax=dataprime&time=from:{start},to:{end}"
    actual_url = build_coralogix_link_to_logs(coralogix_config, query, start, end)
    assert actual_url == expected_url
