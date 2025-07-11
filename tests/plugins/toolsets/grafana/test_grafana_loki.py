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
from tests.plugins.toolsets.grafana.conftest import check_grafana_connectivity

# Use pytest.mark.skip (not skipif) to show a single grouped skip line for the entire module
# Will show: "SKIPPED [4] module.py: reason" instead of 4 separate skip lines
skip_reason = check_grafana_connectivity()
if skip_reason:
    pytestmark = pytest.mark.skip(reason=skip_reason)

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
    # All checks done at module level - env vars and connectivity guaranteed
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


def test_grafana_loki_health_check(loki_config):
    success, error_message = grafana_health_check(loki_config)

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
