import json
import os
from holmes.plugins.toolsets.grafana.grafana_api import grafana_health_check

import pytest

from holmes.core.tools import ToolsetStatusEnum
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import (
    GetTempoTraces,
    GrafanaTempoConfig,
    GrafanaTempoToolset,
)
from holmes.plugins.toolsets.grafana.trace_parser import process_trace

GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "")
GRAFANA_TEMPO_DATASOURCE_UID = os.environ.get("GRAFANA_TEMPO_DATASOURCE_UID", "")


def test_process_trace_json():
    input_trace_data_file_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "test_tempo_api",
            "trace_data.input.json",
        )
    )
    expected_trace_data_file_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "test_tempo_api",
            "trace_data.expected.txt",
        )
    )

    labels = [
        "service.name",
        "service.version",
        "k8s.deployment.name",
        "k8s.node.name",
        "k8s.pod.name",
        "k8s.namespace.name",
    ]
    trace_data = json.loads(open(input_trace_data_file_path).read())
    expected_result = open(expected_trace_data_file_path).read()
    result = process_trace(trace_data, labels)
    print(result)
    assert result is not None
    assert result.strip() == expected_result.strip()


def test_grafana_tempo_has_prompt():
    toolset = GrafanaTempoToolset()
    tool = GetTempoTraces(toolset)
    assert tool.name is not None
    assert toolset.llm_instructions is not None
    assert tool.name in toolset.llm_instructions


@pytest.mark.skipif(
    not GRAFANA_URL,
    reason="'GRAFANA_URL' must be set to run Grafana tests",
)
def test_grafana_query_loki_logs_by_pod():
    config = {
        "api_key": GRAFANA_API_KEY,
        "headers": {},
        "url": GRAFANA_URL,
        "grafana_datasource_uid": GRAFANA_TEMPO_DATASOURCE_UID,
    }

    if not GRAFANA_TEMPO_DATASOURCE_UID:
        config["headers"]["X-Scope-OrgID"] = (
            "1"  # standalone tempo likely requires an orgid
        )

    toolset = GrafanaTempoToolset()
    toolset.config = config
    toolset.check_prerequisites()

    assert toolset.error is None
    assert toolset.status == ToolsetStatusEnum.ENABLED

    tool = GetTempoTraces(toolset)
    # just tests that this does not throw
    tool.invoke(params={"min_duration": "5"})


@pytest.mark.skipif(
    not GRAFANA_URL,
    reason="'GRAFANA_URL' must be set",
)
def test_grafana_loki_health_check():
    config = GrafanaTempoConfig(
        api_key=GRAFANA_API_KEY,
        headers=None,
        url=GRAFANA_URL,
        grafana_datasource_uid=GRAFANA_TEMPO_DATASOURCE_UID,
    )

    success, error_message = grafana_health_check(config)

    assert not error_message
    assert success
