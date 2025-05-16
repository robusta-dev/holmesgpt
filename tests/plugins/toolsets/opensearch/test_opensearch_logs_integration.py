import pytest
import os

from holmes.plugins.toolsets.opensearch.opensearch_logs import (
    OpenSearchLogsToolset,
)
from holmes.plugins.toolsets.opensearch.opensearch_utils import OpenSearchLoggingConfig

REQUIRED_ENV_VARS = [
    "TEST_OPENSEARCH_URL",
    "TEST_OPENSEARCH_INDEX",
    "TEST_OPENSEARCH_AUTH_HEADER",
]

# Check if any required environment variables are missing
missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]

pytestmark = pytest.mark.skipif(
    len(missing_vars) > 0,
    reason=f"Missing required environment variables: {', '.join(missing_vars)}",
)


@pytest.fixture
def opensearch_config() -> OpenSearchLoggingConfig:
    # All required env vars should be present due to the pytestmark skipif
    # This is defensive programming in case the test is run directly
    for var in REQUIRED_ENV_VARS:
        if os.environ.get(var) is None:
            pytest.skip(f"Missing required environment variable: {var}")

    return OpenSearchLoggingConfig(
        opensearch_url=os.environ["TEST_OPENSEARCH_URL"],
        index_pattern=os.environ["TEST_OPENSEARCH_INDEX"],
        opensearch_auth_header=os.environ["TEST_OPENSEARCH_AUTH_HEADER"],
    )


@pytest.fixture
def opensearch_logs_toolset(opensearch_config) -> OpenSearchLogsToolset:
    """Create an OpenSearchLogsToolset with the test configuration"""
    toolset = OpenSearchLogsToolset()
    print(opensearch_config)
    toolset.config = opensearch_config
    return toolset
