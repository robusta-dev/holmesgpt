import pytest
from unittest.mock import patch

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.coralogix.utils import (
    CoralogixQueryResult,
    FlattenedLog,
    CoralogixConfig,
)
from holmes.plugins.toolsets.coralogix.toolset_coralogix_logs import (
    CoralogixLogsToolset,
)


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
def sample_logs():
    return [
        FlattenedLog(timestamp="2023-04-01T11:00:00.000000Z", log_message="Log line 1"),
        FlattenedLog(
            timestamp="2023-04-01T11:00:01.000000Z", log_message="Error in module XYZ"
        ),
        FlattenedLog(timestamp="2023-04-01T11:00:02.000000Z", log_message="Log line 3"),
    ]


@patch(
    "holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.query_logs_for_all_tiers"
)
@patch("holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.get_start_end")
@patch("holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.build_query_string")
@patch(
    "holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.build_coralogix_link_to_logs"
)
def test_fetch_logs_success(
    mock_build_link,
    mock_build_query,
    mock_get_start_end,
    mock_query_logs,
    coralogix_toolset,
    sample_logs,
):
    # Configure mocks
    mock_query_logs.return_value = CoralogixQueryResult(
        logs=sample_logs, http_status=200, error=None
    )
    mock_get_start_end.return_value = ("2023-04-01T10:00:00Z", "2023-04-01T12:00:00Z")
    mock_build_query.return_value = (
        "source logs | lucene 'kubernetes.pod_name:/test-pod/' | limit 1000"
    )
    mock_build_link.return_value = (
        "https://my-team.app.eu2.coralogix.com/#/query-new/logs?..."
    )

    # Call the fetch_logs method
    result = coralogix_toolset.fetch_logs(
        namespace="default",
        pod_name="test-pod",
        start_time="2023-04-01T10:00:00Z",
        end_time="2023-04-01T12:00:00Z",
        filter_pattern=None,
        limit=1000,
    )

    # Verify results
    assert result.status == ToolResultStatus.SUCCESS
    assert "Log line 1" in result.data
    assert "Error in module XYZ" in result.data
    assert "Log line 3" in result.data

    # Verify API calls
    mock_query_logs.assert_called_once()
    mock_get_start_end.assert_called_once()
    mock_build_query.assert_called_once()
    mock_build_link.assert_called_once()

    # Verify parameters passed to the query
    call_params = mock_query_logs.call_args[1]["params"]
    assert call_params["resource_type"] == "pod"
    assert call_params["resource_name"] == "test-pod"
    assert call_params["namespace_name"] == "default"


@patch(
    "holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.query_logs_for_all_tiers"
)
@patch("holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.get_start_end")
@patch("holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.build_query_string")
@patch(
    "holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.build_coralogix_link_to_logs"
)
def test_fetch_logs_with_filter(
    mock_build_link,
    mock_build_query,
    mock_get_start_end,
    mock_query_logs,
    coralogix_toolset,
    sample_logs,
):
    # Configure mocks
    mock_query_logs.return_value = CoralogixQueryResult(
        logs=sample_logs, http_status=200, error=None
    )
    mock_get_start_end.return_value = ("2023-04-01T10:00:00Z", "2023-04-01T12:00:00Z")
    mock_build_query.return_value = (
        "source logs | lucene 'kubernetes.pod_name:/test-pod/' | limit 1000"
    )
    mock_build_link.return_value = (
        "https://my-team.app.eu2.coralogix.com/#/query-new/logs?..."
    )

    # Call the fetch_logs method with a filter
    result = coralogix_toolset.fetch_logs(
        namespace="default",
        pod_name="test-pod",
        start_time="2023-04-01T10:00:00Z",
        end_time="2023-04-01T12:00:00Z",
        filter_pattern="Error",
        limit=1000,
    )

    # Verify results
    assert result.status == ToolResultStatus.SUCCESS
    assert "Log line 1" not in result.data
    assert "Error in module XYZ" in result.data
    assert "Log line 3" not in result.data


@patch(
    "holmes.plugins.toolsets.coralogix.toolset_coralogix_logs.query_logs_for_all_tiers"
)
def test_fetch_logs_error(mock_query_logs, coralogix_toolset):
    # Configure mock to return error
    mock_query_logs.return_value = CoralogixQueryResult(
        logs=[], http_status=400, error="Invalid query"
    )

    # Call the fetch_logs method
    result = coralogix_toolset.fetch_logs(namespace="default", pod_name="test-pod")

    # Verify error response
    assert result.status == ToolResultStatus.ERROR
    assert result.error == "Invalid query"


def test_fetch_logs_missing_config(coralogix_toolset):
    # Set config to None to simulate missing configuration
    coralogix_toolset.config = None

    # Call the fetch_logs method
    result = coralogix_toolset.fetch_logs(namespace="default", pod_name="test-pod")

    # Verify error response
    assert result.status == ToolResultStatus.ERROR
    assert "toolset is not configured" in result.error
