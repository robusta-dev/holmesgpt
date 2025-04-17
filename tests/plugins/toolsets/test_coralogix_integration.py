import os
import pytest

from holmes.plugins.toolsets.coralogix.api import health_check
from holmes.plugins.toolsets.coralogix.toolset_coralogix_logs import (
    CoralogixLogsToolset,
)


CORALOGIX_API_KEY = os.environ.get("CORALOGIX_API_KEY", "")
CORALOGIX_DOMAIN = os.environ.get("CORALOGIX_DOMAIN", "")
CORALOGIX_TEAM_HOSTNAME = os.environ.get("CORALOGIX_TEAM_HOSTNAME")

SKIP_INTEGRATION_TESTS = not all(
    [CORALOGIX_API_KEY, CORALOGIX_DOMAIN, CORALOGIX_TEAM_HOSTNAME]
)
INTEGRATION_TEST_SKIP_REASON = "Skipping integration tests: CORALOGIX_API_KEY, CORALOGIX_DOMAIN, and CORALOGIX_TEAM_HOSTNAME environment variables must be set."


@pytest.mark.skipif(SKIP_INTEGRATION_TESTS, reason=INTEGRATION_TEST_SKIP_REASON)
def test_integration_health_check_api():
    """Tests the health_check function directly against the API."""
    ready, message = health_check(domain=CORALOGIX_DOMAIN, api_key=CORALOGIX_API_KEY)
    assert ready, f"Health check failed: {message}"
    assert message == ""


@pytest.mark.skipif(SKIP_INTEGRATION_TESTS, reason=INTEGRATION_TEST_SKIP_REASON)
def test_integration_health_check_api_invalid_key():
    """Tests the health_check function with a known invalid key."""
    ready, message = health_check(domain=CORALOGIX_DOMAIN, api_key="invalid-key")
    assert not ready
    assert (
        "Failed with status_code=403" in message or "Unauthorized" in message
    )  # Check for 4.3 Unauthorized


@pytest.mark.skipif(SKIP_INTEGRATION_TESTS, reason=INTEGRATION_TEST_SKIP_REASON)
def test_integration_toolset_prerequisites():
    """Tests the toolset's prerequisite check which calls the health_check."""
    toolset = CoralogixLogsToolset()
    config = {
        "api_key": CORALOGIX_API_KEY,
        "domain": CORALOGIX_DOMAIN,
        "team_hostname": CORALOGIX_TEAM_HOSTNAME,
    }
    ready, message = toolset.prerequisites_callable(config)
    assert ready, f"Toolset prerequisites failed: {message}"
    assert message == ""
    assert toolset.config is not None
    assert toolset.config.api_key == CORALOGIX_API_KEY
