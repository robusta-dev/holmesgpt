"""Tests for the health check API endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from holmes.checks import CheckResult, CheckStatus


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    # Import here to avoid circular imports
    from server import app

    return TestClient(app)


@pytest.fixture
def mock_config():
    """Mock the config object."""
    config = MagicMock()
    config.create_toolcalling_llm = MagicMock()
    return config


@pytest.fixture
def mock_dal():
    """Mock the DAL object."""
    return MagicMock()


def test_check_execute_endpoint_success(test_client, mock_config, mock_dal):
    """Test successful check execution via API."""

    # Mock the execute_check function
    mock_result = CheckResult(
        check_name="test-check",
        status=CheckStatus.PASS,
        message="Check passed. All systems operational",
        query="Is everything healthy?",
        duration=2.5,
        rationale="All systems operational",
    )

    with patch("server.config", mock_config):
        with patch("server.dal", mock_dal):
            with patch("holmes.checks.execute_check", return_value=mock_result):
                # Make request
                response = test_client.post(
                    "/api/check/execute",
                    json={
                        "query": "Is everything healthy?",
                        "timeout": 30,
                        "mode": "monitor",
                        "destinations": [],
                    },
                    headers={"X-Check-Name": "test-check"},
                )

    # Verify response
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "pass"
    assert "Check passed" in data["message"]
    assert data["duration"] == 2.5
    assert data["rationale"] == "All systems operational"
    assert data["error"] is None


def test_check_execute_endpoint_failure(test_client, mock_config, mock_dal):
    """Test failed check execution via API."""

    # Mock the execute_check function
    mock_result = CheckResult(
        check_name="test-check",
        status=CheckStatus.FAIL,
        message="Check failed. Database connection error",
        query="Can connect to database?",
        duration=1.2,
        rationale="Database connection refused",
    )

    with patch("server.config", mock_config):
        with patch("server.dal", mock_dal):
            with patch("holmes.checks.execute_check", return_value=mock_result):
                # Make request
                response = test_client.post(
                    "/api/check/execute",
                    json={
                        "query": "Can connect to database?",
                        "timeout": 15,
                        "mode": "alert",
                        "destinations": [
                            {"type": "slack", "config": {"channel": "#alerts"}}
                        ],
                    },
                )

    # Verify response
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "fail"
    assert "Check failed" in data["message"]
    assert data["rationale"] == "Database connection refused"


def test_check_execute_endpoint_error(test_client, mock_config, mock_dal):
    """Test error handling in check execution."""

    # Mock the execute_check function
    mock_result = CheckResult(
        check_name="test-check",
        status=CheckStatus.ERROR,
        message="Check errored: Timeout",
        query="Is service responsive?",
        duration=30.0,
        error="TimeoutError",
    )

    with patch("server.config", mock_config):
        with patch("server.dal", mock_dal):
            with patch("holmes.checks.execute_check", return_value=mock_result):
                # Make request
                response = test_client.post(
                    "/api/check/execute",
                    json={
                        "query": "Is service responsive?",
                        "timeout": 30,
                    },
                )

    # Verify response
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "error"
    assert "Check errored" in data["message"]
    assert data["error"] == "TimeoutError"


def test_check_execute_endpoint_no_header(test_client, mock_config, mock_dal):
    """Test check execution without X-Check-Name header."""

    mock_result = CheckResult(
        check_name="api-check",  # Default name
        status=CheckStatus.PASS,
        message="Check passed",
        query="Test query",
        duration=1.0,
    )

    with patch("server.config", mock_config):
        with patch("server.dal", mock_dal):
            with patch("holmes.checks.execute_check", return_value=mock_result):
                # Make request without header
                response = test_client.post(
                    "/api/check/execute",
                    json={
                        "query": "Test query",
                    },
                )

    # Should still work with default name
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pass"


def test_check_execute_endpoint_invalid_mode(test_client, mock_config, mock_dal):
    """Test check execution with invalid mode."""

    with patch("server.config", mock_config):
        with patch("server.dal", mock_dal):
            # Make request with invalid mode
            response = test_client.post(
                "/api/check/execute",
                json={
                    "query": "Test query",
                    "mode": "invalid_mode",
                },
            )

    # Should return 500 error
    assert response.status_code == 500
    assert "detail" in response.json()
