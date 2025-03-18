import os
import time
import pytest

from holmes.plugins.toolsets.grafana.toolset_grafana_loki import (
    GetLokiLogsForResource,
    GrafanaLokiToolset,
)
from holmes.plugins.toolsets.grafana.toolset_grafana_loki import GrafanaLokiConfig

GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "")
GRAFANA_DATASOURCE_UID = os.environ.get("GRAFANA_DATASOURCE_UID", "")


@pytest.mark.skipif(
    not GRAFANA_URL or not GRAFANA_DATASOURCE_UID, reason="'GRAFANA_URL' must be set to run Grafana tests"
)
def test_grafana_query_loki_logs_by_pod():
    config = GrafanaLokiConfig(
        api_key=GRAFANA_API_KEY,
        url=GRAFANA_URL,
        grafana_datasource_uid=GRAFANA_DATASOURCE_UID,
    )

    toolset = GrafanaLokiToolset()
    toolset._grafana_config = config
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
