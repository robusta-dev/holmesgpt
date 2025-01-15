import os
import time

import pytest
from holmes.plugins.toolsets.grafana.loki_api import GRAFANA_URL_ENV_NAME, list_grafana_datasources, query_loki_logs_by_node, query_loki_logs_by_pod
from holmes.plugins.toolsets.grafana_loki import GetLokiLogsByNode, GetLokiLogsByPod, ListLokiDatasources

@pytest.mark.skipif(not os.environ.get(GRAFANA_URL_ENV_NAME), reason=f"{GRAFANA_URL_ENV_NAME} must be set to run Grafana tests")
def test_grafana_list_loki_datasources():
    datasources = list_grafana_datasources("loki")
    assert len(datasources) > 0
    for datasource in datasources:
        assert datasource.get("type") == "loki", f"unexpected datasource is not of type loky: {datasource}"

@pytest.mark.skipif(not os.environ.get(GRAFANA_URL_ENV_NAME), reason=f"{GRAFANA_URL_ENV_NAME} must be set to run Grafana tests")
def test_grafana_query_loki_logs_by_node():
    datasources = list_grafana_datasources("loki")
    assert len(datasources) > 0

    tool = GetLokiLogsByNode()
    # just tests that this does not throw
    tool.invoke(params={
        "loki_datasource_id": datasources[0]["id"],
        "node_name": "foo",
        "limit": 10,
        "start_timestamp": int(time.time()) - 3600,
        "end_timestamp": int(time.time())
    })

@pytest.mark.skipif(not os.environ.get(GRAFANA_URL_ENV_NAME), reason=f"{GRAFANA_URL_ENV_NAME} must be set to run Grafana tests")
def test_grafana_query_loki_logs_by_pod():
    datasources = list_grafana_datasources("loki")
    assert len(datasources) > 0

    tool = GetLokiLogsByPod()
        # just tests that this does not throw
    tool.invoke(params={
        "loki_datasource_id": datasources[0]["id"],
        "namespace": "kube-system",
        "pod_regex": "coredns.*",
        "limit": 10,
        "start_timestamp": int(time.time()) - 3600,
        "end_timestamp": int(time.time())
    })
