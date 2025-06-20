"""
This is a set of integration tests intended to be run manually
Change the TEST_** variables defined below based on the content in opensearch to validate that the implementation is working as expected
"""

import os
import pytest

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.coralogix.api import health_check
from holmes.plugins.toolsets.coralogix.toolset_coralogix_logs import (
    CoralogixLogsToolset,
)
from holmes.plugins.toolsets.coralogix.utils import CoralogixConfig
from holmes.plugins.toolsets.logging_utils.logging_api import FetchPodLogsParams


REQUIRED_ENV_VARS = [
    "CORALOGIX_API_KEY",
    "CORALOGIX_DOMAIN",
    "CORALOGIX_TEAM_HOSTNAME",
]

missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]

pytestmark = pytest.mark.skipif(
    len(missing_vars) > 0,
    reason=f"Missing required environment variables: {', '.join(missing_vars)}",
)

CORALOGIX_API_KEY = os.environ.get("CORALOGIX_API_KEY", "")
CORALOGIX_DOMAIN = os.environ.get("CORALOGIX_DOMAIN", "")
CORALOGIX_TEAM_HOSTNAME = os.environ.get("CORALOGIX_TEAM_HOSTNAME", "")


TEST_NAMESPACE = "default"
TEST_POD_NAME = "curl-deployment-6c67b4656-hlbw8"
TEST_SEARCH_TERM = "Checking endpoint"

# the date range below combined with the search term is expected to return a single log line
TEST_START_TIME = "2025-05-19T08:55:09Z"
TEST_END_TIME = "2025-05-19T08:55:20Z"


@pytest.fixture
def coralogix_config() -> CoralogixConfig:
    # All required env vars should be present due to the pytestmark skipif
    # This is defensive programming in case the test is run directly
    for var in REQUIRED_ENV_VARS:
        if os.environ.get(var) is None:
            pytest.skip(f"Missing required environment variable: {var}")

    return CoralogixConfig(
        api_key=CORALOGIX_API_KEY,
        domain=CORALOGIX_DOMAIN,
        team_hostname=CORALOGIX_TEAM_HOSTNAME,
    )


@pytest.fixture
def coralogix_logs_toolset(coralogix_config) -> CoralogixLogsToolset:
    """Create an OpenSearchLogsToolset with the test configuration"""
    toolset = CoralogixLogsToolset()
    toolset.config = coralogix_config
    return toolset


def test_health_check_api():
    """Tests the health_check function directly against the API."""
    ready, message = health_check(domain=CORALOGIX_DOMAIN, api_key=CORALOGIX_API_KEY)
    assert ready, f"Health check failed: {message}"
    assert message == ""


def test_health_check_api_invalid_key():
    """Tests the health_check function with a known invalid key."""
    ready, message = health_check(domain=CORALOGIX_DOMAIN, api_key="invalid-key")
    assert not ready
    assert (
        "Failed with status_code=403" in message or "Unauthorized" in message
    )  # Check for 4.3 Unauthorized


def test_integration_toolset_prerequisites(coralogix_config):
    toolset = CoralogixLogsToolset()
    ready, message = toolset.prerequisites_callable(coralogix_config.model_dump())
    assert ready, f"Toolset prerequisites failed: {message}"
    assert not message


def test_basic_query(coralogix_logs_toolset):
    result = coralogix_logs_toolset.fetch_pod_logs(
        FetchPodLogsParams(namespace=TEST_NAMESPACE, pod_name=TEST_POD_NAME)
    )
    print(result.data)
    assert result.status == ToolResultStatus.SUCCESS, result.error
    assert not result.error
    assert TEST_SEARCH_TERM in result.data


def test_search_term(coralogix_logs_toolset):
    result = coralogix_logs_toolset.fetch_pod_logs(
        FetchPodLogsParams(
            namespace=TEST_NAMESPACE, pod_name=TEST_POD_NAME, filter=TEST_SEARCH_TERM
        )
    )

    print(result.data)
    assert result.status == ToolResultStatus.SUCCESS, result.error
    assert not result.error
    lines = result.data.split("\n")[2:]  # skips headers lines for "link" and "query"
    # print(lines)
    for line in lines:
        assert TEST_SEARCH_TERM in line, line


def test_search_term_with_dates(coralogix_logs_toolset):
    result = coralogix_logs_toolset.fetch_pod_logs(
        FetchPodLogsParams(
            namespace=TEST_NAMESPACE,
            pod_name=TEST_POD_NAME,
            filter=TEST_SEARCH_TERM,
            start_time=TEST_START_TIME,
            end_time=TEST_END_TIME,
        )
    )

    assert result.status == ToolResultStatus.SUCCESS, result.error
    assert not result.error
    print(result.data)
    lines = result.data.split("\n")
    # first two lines are headers lines for "link" and "query"
    # The last line is the log line we're looking for
    assert len(lines) == 3
    assert TEST_SEARCH_TERM in lines[2]
