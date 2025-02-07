import os
import time

import pytest

from holmes.plugins.toolsets.grafana.common import GrafanaConfig
from holmes.plugins.toolsets.grafana.grafana_api import list_grafana_datasources
from holmes.plugins.toolsets.grafana.toolset_grafana_loki import (
    GetLokiLogsByNode,
    GetLokiLogsByPod,
    GrafanaLokiToolset,
)

GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "")


@pytest.mark.skipif(
    not GRAFANA_URL, reason="'GRAFANA_URL' must be set to run Grafana tests"
)
def test_grafana_list_loki_datasources():
    config = GrafanaConfig(api_key=GRAFANA_API_KEY, url=GRAFANA_URL)
    datasources = list_grafana_datasources(
        grafana_url=config.url, api_key=config.api_key, source_name="loki"
    )
    assert len(datasources) > 0
    for datasource in datasources:
        assert (
            datasource.get("type") == "loki"
        ), f"unexpected datasource is not of type loky: {datasource}"


@pytest.mark.skipif(
    not GRAFANA_URL, reason="'GRAFANA_URL' must be set to run Grafana tests"
)
def test_grafana_query_loki_logs_by_node():
    config = GrafanaConfig(api_key=GRAFANA_API_KEY, url=GRAFANA_URL)
    datasources = list_grafana_datasources(
        grafana_url=config.url, api_key=config.api_key, source_name="loki"
    )
    assert len(datasources) > 0

    toolset = GrafanaLokiToolset()
    toolset._grafana_config = config
    tool = GetLokiLogsByNode(toolset)
    # just tests that this does not throw
    tool.invoke(
        params={
            "loki_datasource_id": datasources[0]["id"],
            "node_name": "foo",
            "limit": 10,
            "start_timestamp": int(time.time()) - 3600,
            "end_timestamp": int(time.time()),
        }
    )


@pytest.mark.skipif(
    not GRAFANA_URL, reason="'GRAFANA_URL' must be set to run Grafana tests"
)
def test_grafana_query_loki_logs_by_pod():
    config = GrafanaConfig(api_key=GRAFANA_API_KEY, url=GRAFANA_URL)
    datasources = list_grafana_datasources(
        grafana_url=config.url, api_key=config.api_key, source_name="loki"
    )
    assert len(datasources) > 0

    toolset = GrafanaLokiToolset()
    toolset._grafana_config = config
    tool = GetLokiLogsByPod(toolset)
    # just tests that this does not throw
    tool.invoke(
        params={
            "loki_datasource_id": datasources[0]["id"],
            "namespace": "kube-system",
            "pod_regex": "coredns.*",
            "limit": 10,
            "start_timestamp": int(time.time()) - 3600,
            "end_timestamp": int(time.time()),
        }
    )
