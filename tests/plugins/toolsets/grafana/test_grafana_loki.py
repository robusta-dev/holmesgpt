import os
import time

import pytest

from holmes.core.tools import ToolsetStatusEnum
from holmes.plugins.toolsets.grafana.grafana_api import get_health
from holmes.plugins.toolsets.grafana.toolset_grafana_loki import (
    GetLokiLogsForResource,
    GrafanaLokiConfig,
    GrafanaLokiToolset,
)

GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "")
GRAFANA_LOKI_DATASOURCE_UID = os.environ.get("GRAFANA_LOKI_DATASOURCE_UID", "")


@pytest.mark.skipif(
    not GRAFANA_URL,
    reason="'GRAFANA_URL' must be set to run Grafana tests",
)
def test_grafana_query_loki_logs_by_pod():
    config = {
        "api_key": GRAFANA_API_KEY,
        "headers": {},
        "url": GRAFANA_URL,
        "grafana_datasource_uid": GRAFANA_LOKI_DATASOURCE_UID,
    }

    if not GRAFANA_LOKI_DATASOURCE_UID:
        config["headers"]["X-Scope-OrgID"] = (
            "1"  # standalone loki likely requires an orgid
        )

    toolset = GrafanaLokiToolset()
    toolset.config = config
    toolset.check_prerequisites()

    assert toolset.error is None
    assert toolset.status == ToolsetStatusEnum.ENABLED

    tool = GetLokiLogsForResource(toolset)
    # just tests that this does not throw
    tool.invoke(
        params={
            "resource_type": "pod",
            "resource_name": "robusta-runner",
            "namespace": "default",
            "limit": 10,
            "start_timestamp": int(time.time()) - 3600,
            "end_timestamp": int(time.time()),
        }
    )


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

    success, error_message = get_health(config)

    assert not error_message
    assert success
