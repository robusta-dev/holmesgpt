"""Tests for PagerDuty destination plugin."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from holmes.core.issue import Issue
from holmes.core.tool_calling_llm import LLMResult
from holmes.plugins.destinations.pagerduty.plugin import PagerDutyDestination


@pytest.fixture
def pagerduty_destination():
    """Create a PagerDuty destination instance."""
    return PagerDutyDestination(integration_key="test-integration-key")


@pytest.fixture
def sample_issue():
    """Create a sample issue for testing."""
    return Issue(
        id="test-123",
        name="Test Health Check Failed",
        source_type="holmes-check",
        raw={
            "check": "Database Connection",
            "description": "Check database connectivity",
            "query": "Can you connect to the database?",
            "result": "Connection failed",
            "tags": ["critical", "database"],
        },
        source_instance_id="holmes-check",
    )


@pytest.fixture
def sample_llm_result():
    """Create a sample LLM result for testing."""
    return LLMResult(
        result="Database connection failed: Connection timeout after 30 seconds",
        tool_calls=[],
    )


def test_pagerduty_destination_creation():
    """Test PagerDuty destination instance creation."""
    dest = PagerDutyDestination(integration_key="test-key")
    assert dest.integration_key == "test-key"
    assert dest.api_url == "https://events.pagerduty.com/v2/enqueue"

    # Test with custom API URL
    dest_custom = PagerDutyDestination(
        integration_key="test-key", api_url="https://custom.pagerduty.com/api"
    )
    assert dest_custom.api_url == "https://custom.pagerduty.com/api"


def test_create_event_payload(pagerduty_destination, sample_issue, sample_llm_result):
    """Test event payload creation."""
    payload = pagerduty_destination._create_event_payload(
        sample_issue, sample_llm_result
    )

    assert payload["routing_key"] == "test-integration-key"
    assert payload["event_action"] == "trigger"
    assert payload["dedup_key"] == "holmes-check-test-123"

    assert "payload" in payload
    event_payload = payload["payload"]
    assert event_payload["summary"] == "Holmes Check Failed: Test Health Check Failed"
    assert event_payload["severity"] == "critical"  # From tags
    assert event_payload["source"] == "holmes"
    assert event_payload["component"] == "holmes-check"
    assert event_payload["group"] == "health-checks"
    assert event_payload["class"] == "health-check-failure"

    assert "custom_details" in event_payload
    custom_details = event_payload["custom_details"]
    assert custom_details["holmes_analysis"] == sample_llm_result.result
    assert custom_details["source_type"] == "holmes-check"
    assert "check_details" in custom_details


def test_get_severity(pagerduty_destination, sample_issue):
    """Test severity determination from issue."""
    # Test with critical tag
    assert pagerduty_destination._get_severity(sample_issue) == "critical"

    # Test with error tag
    sample_issue.raw["tags"] = ["error", "database"]
    assert pagerduty_destination._get_severity(sample_issue) == "error"

    # Test with warning tag
    sample_issue.raw["tags"] = ["warning"]
    assert pagerduty_destination._get_severity(sample_issue) == "warning"

    # Test with explicit severity field (overrides tags)
    sample_issue.raw["severity"] = "info"
    sample_issue.raw["tags"] = []  # Clear tags to test severity field
    assert pagerduty_destination._get_severity(sample_issue) == "info"

    # Test default severity
    sample_issue.raw = {}
    assert pagerduty_destination._get_severity(sample_issue) == "error"


@patch("requests.post")
def test_send_issue_success(
    mock_post, pagerduty_destination, sample_issue, sample_llm_result
):
    """Test successful issue sending."""
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "status": "success",
        "dedup_key": "holmes-check-test-123",
        "message": "Event processed",
    }
    mock_post.return_value = mock_response

    # Send issue
    pagerduty_destination.send_issue(sample_issue, sample_llm_result)

    # Verify request was made
    mock_post.assert_called_once()
    call_args = mock_post.call_args

    assert call_args[0][0] == "https://events.pagerduty.com/v2/enqueue"
    assert "json" in call_args[1]

    payload = call_args[1]["json"]
    assert payload["routing_key"] == "test-integration-key"
    assert payload["event_action"] == "trigger"


@patch("requests.post")
def test_send_issue_failure(
    mock_post, pagerduty_destination, sample_issue, sample_llm_result
):
    """Test issue sending with API failure."""
    # Mock failed response
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "status": "invalid event",
        "message": "Invalid routing key",
        "errors": ["routing_key not found"],
    }
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=mock_response
    )
    mock_post.return_value = mock_response

    # Send issue (should not raise, just log)
    pagerduty_destination.send_issue(sample_issue, sample_llm_result)

    # Verify request was made
    mock_post.assert_called_once()


@patch("requests.post")
def test_send_issue_network_error(
    mock_post, pagerduty_destination, sample_issue, sample_llm_result
):
    """Test issue sending with network error."""
    # Mock network error
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

    # Send issue (should not raise, just log)
    pagerduty_destination.send_issue(sample_issue, sample_llm_result)

    # Verify request was attempted
    mock_post.assert_called_once()


@patch("requests.post")
def test_resolve_issue(mock_post, pagerduty_destination):
    """Test resolving an issue in PagerDuty."""
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "status": "success",
        "dedup_key": "holmes-check-test-123",
        "message": "Event processed",
    }
    mock_post.return_value = mock_response

    # Resolve issue
    pagerduty_destination.resolve_issue("test-123")

    # Verify request was made
    mock_post.assert_called_once()
    call_args = mock_post.call_args

    payload = call_args[1]["json"]
    assert payload["routing_key"] == "test-integration-key"
    assert payload["event_action"] == "resolve"
    assert payload["dedup_key"] == "holmes-check-test-123"


def test_issue_with_url(pagerduty_destination, sample_issue, sample_llm_result):
    """Test payload creation with issue URL."""
    sample_issue.url = "https://example.com/issue/123"

    payload = pagerduty_destination._create_event_payload(
        sample_issue, sample_llm_result
    )

    assert "links" in payload
    assert len(payload["links"]) == 1
    assert payload["links"][0]["href"] == "https://example.com/issue/123"
    assert payload["links"][0]["text"] == "View in source system"


def test_issue_with_tool_calls(pagerduty_destination, sample_issue):
    """Test payload creation with tool calls."""
    from holmes.core.tool_calling_llm import ToolCallResult
    from holmes.core.tools import StructuredToolResult, ToolResultStatus

    # Create proper ToolCallResult
    tool_call = ToolCallResult(
        tool_call_id="test-call-1",
        tool_name="kubectl_describe",
        description="Describe pod details",
        result=StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data="Pod is in CrashLoopBackOff state",
        ),
    )

    llm_result = LLMResult(
        result="Pod is in CrashLoopBackOff state",
        tool_calls=[tool_call],
    )

    payload = pagerduty_destination._create_event_payload(sample_issue, llm_result)

    custom_details = payload["payload"]["custom_details"]
    assert "tools_used" in custom_details
    assert len(custom_details["tools_used"]) == 1
    assert custom_details["tools_used"][0]["tool"] == "kubectl_describe"
    assert custom_details["tools_used"][0]["description"] == "Describe pod details"
