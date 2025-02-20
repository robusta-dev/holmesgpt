import json
import os

import pytest
from holmes.core.tools import ToolExecutor, ToolsetStatusEnum
from holmes.plugins.toolsets.prometheus import (
    PrometheusToolset,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("PROMETHEUS_URL", None) is None, reason="PROMETHEUS_URL must be set"
)

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", None)


@pytest.fixture
def tool_executor():
    toolset = PrometheusToolset()
    toolset.enabled = True
    toolset.config = {"prometheus_url": PROMETHEUS_URL}
    toolset.check_prerequisites()
    assert toolset.get_status() == ToolsetStatusEnum.ENABLED
    tool_executor = ToolExecutor(toolsets=[toolset])
    return tool_executor


def test_list_available_metrics(tool_executor: ToolExecutor):
    tool = tool_executor.get_tool_by_name("list_available_metrics")
    assert tool
    actual_output = tool.invoke({"name_filter": "kubelet_running_pods"})
    print(actual_output)
    assert "kubelet_running_pods" in actual_output


def test_execute_prometheus_query(tool_executor: ToolExecutor):
    tool = tool_executor.get_tool_by_name("execute_prometheus_instant_query")
    assert tool
    actual_output = tool.invoke({"query": "up", "type": "query"})
    print(actual_output)
    assert actual_output
    parsed_output = json.loads(actual_output)
    assert parsed_output.get("status") == "success"
