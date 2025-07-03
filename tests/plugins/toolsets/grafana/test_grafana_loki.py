import os
from typing import Any
from holmes.core.tools import ToolResultStatus, ToolsetStatusEnum
from holmes.plugins.toolsets.grafana.grafana_api import grafana_health_check
import pytest

from holmes.plugins.toolsets.grafana.toolset_grafana_loki import GrafanaLokiConfig
from holmes.plugins.toolsets.logging_utils.logging_api import FetchPodLogsParams
from holmes.plugins.toolsets.grafana.toolset_grafana_loki import (
    GrafanaLokiToolset,
)


REQUIRED_ENV_VARS = [
    "GRAFANA_URL",
]

missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]


pytestmark = pytest.mark.skipif(
    len(missing_vars) > 0,
    reason=f"Missing required environment variables: {', '.join(missing_vars)}",
)

TEST_NAMESPACE = "default"
TEST_POD_NAME = "robusta-holmes-7cd886dc86-x5zfd"
TEST_SEARCH_TERM = "WARNING"

# the date range below combined with the search term is expected to return a single log line
TEST_START_TIME = "2025-05-20T05:11:00Z"
TEST_END_TIME = "2025-05-20T05:12:00Z"


GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "")
GRAFANA_LOKI_DATASOURCE_UID = os.environ.get("GRAFANA_LOKI_DATASOURCE_UID")
GRAFANA_LOKI_X_SCOPE_ORGID = os.environ.get("GRAFANA_LOKI_X_SCOPE_ORGID")


@pytest.fixture
def loki_config() -> GrafanaLokiConfig:
    # All required env vars should be present due to the pytestmark skipif
    # This is defensive programming in case the test is run directly
    for var in REQUIRED_ENV_VARS:
        if os.environ.get(var) is None:
            pytest.skip(f"Missing required environment variable: {var}")

    config_dict: dict[str, Any] = {
        "api_key": GRAFANA_API_KEY,
        "url": GRAFANA_URL,
        "grafana_datasource_uid": GRAFANA_LOKI_DATASOURCE_UID,
    }

    if GRAFANA_LOKI_X_SCOPE_ORGID:
        config_dict["headers"] = {"X-Scope-OrgID": GRAFANA_LOKI_X_SCOPE_ORGID}

    return GrafanaLokiConfig(**config_dict)


@pytest.fixture
def loki_toolset(loki_config) -> GrafanaLokiToolset:
    """Create an OpenSearchLogsToolset with the test configuration"""
    toolset = GrafanaLokiToolset()
    toolset.config = loki_config.model_dump()
    toolset.check_prerequisites()

    assert toolset.error is None
    assert toolset.status == ToolsetStatusEnum.ENABLED

    return toolset


@pytest.mark.skipif(
    not GRAFANA_URL,
    reason="'GRAFANA_URL' must be set",
)
def test_grafana_loki_health_check():
    config = GrafanaLokiConfig(
        api_key=GRAFANA_API_KEY,
        headers=None,
        url=GRAFANA_URL,
        grafana_datasource_uid=GRAFANA_LOKI_DATASOURCE_UID,
    )

    success, error_message = grafana_health_check(config)

    assert not error_message
    assert success


def test_basic_query(loki_toolset):
    result = loki_toolset.fetch_pod_logs(
        FetchPodLogsParams(namespace=TEST_NAMESPACE, pod_name=TEST_POD_NAME)
    )
    print(result.data)
    assert result.status == ToolResultStatus.SUCCESS, result.error
    assert not result.error
    assert TEST_SEARCH_TERM in result.data


def test_search_term(loki_toolset):
    result = loki_toolset.fetch_pod_logs(
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


def test_search_term_with_dates(loki_toolset):
    result = loki_toolset.fetch_pod_logs(
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
    assert TEST_SEARCH_TERM in result.data
    assert len(result.data.split("\n")) == 1
