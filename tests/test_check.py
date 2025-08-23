"""Tests for the holmes check command."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from holmes.checks import (
    Check,
    CheckMode,
    CheckResponse,
    CheckResult,
    CheckRunner,
    CheckStatus,
    load_checks_config,
)
from holmes.config import Config


@pytest.fixture
def sample_checks_config():
    """Create a sample checks configuration."""
    return {
        "version": 1,
        "defaults": {
            "timeout": 30,
            "mode": "alert",
        },
        "destinations": {
            "slack": {
                "webhook_url": "https://hooks.slack.com/test",
                "channel": "#alerts",
            }
        },
        "checks": [
            {
                "name": "Test Check 1",
                "description": "First test check",
                "tags": ["test", "critical"],
                "query": "Is everything healthy?",
                "destinations": ["slack"],
            },
            {
                "name": "Test Check 2",
                "description": "Second test check",
                "tags": ["test", "monitoring"],
                "query": "Are all services running?",
                "mode": "monitor",
            },
        ],
    }


@pytest.fixture
def temp_checks_file(sample_checks_config):
    """Create a temporary checks configuration file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_checks_config, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


def test_load_checks_config(temp_checks_file):
    """Test loading checks configuration from YAML."""
    config = load_checks_config(temp_checks_file)

    assert config.version == 1
    assert len(config.checks) == 2
    assert config.checks[0].name == "Test Check 1"
    assert config.checks[0].mode == CheckMode.ALERT


def test_check_model():
    """Test Check model."""
    check = Check(
        name="Test Check",
        query="Is the service healthy?",
        tags=["test"],
        mode=CheckMode.MONITOR,
    )

    assert check.name == "Test Check"
    assert check.mode == CheckMode.MONITOR
    assert check.timeout == 30  # Default


def test_check_result():
    """Test CheckResult model."""
    result = CheckResult(
        check_name="Test Check",
        status=CheckStatus.PASS,
        message="Check passed",
        duration=5.5,
    )

    assert result.check_name == "Test Check"
    assert result.status == CheckStatus.PASS
    assert result.duration == 5.5


def test_check_response():
    """Test CheckResponse model."""
    response = CheckResponse(passed=True, rationale="All systems are operational")

    assert response.passed is True
    assert response.rationale == "All systems are operational"

    response2 = CheckResponse(passed=False, rationale="Database connection failed")

    assert response2.passed is False
    assert response2.rationale == "Database connection failed"


def test_check_runner_single_check_pass():
    """Test running a single check that passes."""
    config = MagicMock(spec=Config)
    config.get_runbook_catalog.return_value = []
    console = MagicMock()

    # Mock AI response with structured JSON
    mock_ai = MagicMock()
    mock_ai.tool_executor = MagicMock()
    mock_response = MagicMock()
    mock_response.result = (
        '{"passed": true, "rationale": "Everything is healthy and operational"}'
    )
    mock_ai.call.return_value = mock_response

    runner = CheckRunner(config, console, CheckMode.MONITOR, verbose=True)
    runner.ai = mock_ai  # Directly set the AI instance

    check = Check(
        name="Test Check",
        query="Is everything healthy?",
    )

    result = runner.run_single_check(check)

    assert result.status == CheckStatus.PASS
    assert "Check passed" in result.message
    assert "Everything is healthy and operational" in result.message


def test_check_runner_single_check_fail():
    """Test running a single check that fails."""
    config = MagicMock(spec=Config)
    config.get_runbook_catalog.return_value = []
    console = MagicMock()

    # Mock AI response with structured JSON
    mock_ai = MagicMock()
    mock_ai.tool_executor = MagicMock()
    mock_response = MagicMock()
    mock_response.result = (
        '{"passed": false, "rationale": "Critical errors detected in the system"}'
    )
    mock_ai.call.return_value = mock_response

    runner = CheckRunner(config, console, CheckMode.MONITOR, verbose=True)
    runner.ai = mock_ai  # Directly set the AI instance

    check = Check(
        name="Test Check",
        query="Is everything healthy?",
    )

    result = runner.run_single_check(check)

    assert result.status == CheckStatus.FAIL
    assert "Check failed" in result.message
    assert "Critical errors detected" in result.message


def test_check_runner_filters():
    """Test filtering checks by name and tags."""
    config = MagicMock(spec=Config)
    config.get_runbook_catalog.return_value = []
    console = MagicMock()

    checks = [
        Check(name="Check1", query="Q1", tags=["critical", "database"]),
        Check(name="Check2", query="Q2", tags=["monitoring", "cpu"]),
        Check(name="Check3", query="Q3", tags=["critical", "network"]),
    ]

    runner = CheckRunner(config, console, CheckMode.MONITOR, verbose=False)

    # Mock run_single_check to avoid actual execution
    def mock_run_single(check):
        return CheckResult(
            check_name=check.name,
            status=CheckStatus.PASS,
            message="Mocked",
        )

    runner.run_single_check = mock_run_single

    # Test name filter
    results = runner.run_checks(checks, name_filter="Check2")
    assert len(results) == 1
    assert results[0].check_name == "Check2"

    # Test tag filter
    results = runner.run_checks(checks, tag_filter=["critical"])
    assert len(results) == 2
    assert all(r.check_name in ["Check1", "Check3"] for r in results)

    # Test combined filters (no matches)
    results = runner.run_checks(checks, name_filter="Check1", tag_filter=["cpu"])
    assert len(results) == 0


def test_check_runner_alert_sending():
    """Test alert sending for failed checks."""
    config = MagicMock(spec=Config)
    config.slack_token = "test-token"
    config.slack_channel = "#alerts"
    console = MagicMock()

    with patch(
        "holmes.plugins.destinations.slack.plugin.SlackDestination"
    ) as mock_slack:
        runner = CheckRunner(config, console, CheckMode.ALERT, verbose=True)

        check = Check(
            name="Test Check",
            query="Is everything healthy?",
            destinations=["slack"],
        )

        result = CheckResult(
            check_name="Test Check",
            status=CheckStatus.FAIL,
            message="Check failed",
        )

        runner._send_alerts(check, result)

        # Verify Slack was called
        mock_slack.assert_called_once_with("test-token", "#alerts")
        mock_slack.return_value.send_issue.assert_called_once()
