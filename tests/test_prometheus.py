import json
import os

import pytest
from holmes.core.tools import ToolExecutor
from holmes.plugins.toolsets.prometheus import PrometheusConfig, PrometheusToolset

pytestmark = pytest.mark.skipif(os.environ.get("PROMETHEUS_URL", None) is None, reason="PROMETHEUS_URL must be set")

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", None)

toolset = PrometheusToolset(PrometheusConfig(url= PROMETHEUS_URL))
tool_executor = ToolExecutor(toolsets=[toolset])

def test_list_available_metrics():
    tool = tool_executor.get_tool_by_name('list_available_metrics')
    assert tool
    actual_output = tool.invoke({})
    print(actual_output)
    assert "kubelet_running_pods" in actual_output

def test_list_prometheus_series():
    tool = tool_executor.get_tool_by_name('list_prometheus_series')
    assert tool
    actual_output = tool.invoke({
        "match": [
            'kubelet_running_pods',
            'up',
        ]})
    print(actual_output)
    assert "'__name__': 'kubelet_running_pods'" in actual_output
    assert "'__name__': 'up'" in actual_output
    # assert False

def test_list_prometheus_labels():
    tool = tool_executor.get_tool_by_name('list_prometheus_labels')
    assert tool
    actual_output = tool.invoke({})
    print(actual_output)
    assert "replicaset" in actual_output

def test_list_prometheus_label_values():
    tool = tool_executor.get_tool_by_name('list_prometheus_label_values')
    assert tool
    actual_output = tool.invoke({"label_name": "replicaset"})
    print(actual_output)
    assert actual_output
    assert len(actual_output.split("\n")) > 1

def test_execute_prometheus_query():
    tool = tool_executor.get_tool_by_name('execute_prometheus_query')
    assert tool
    actual_output = tool.invoke({"query": "up", "type": "query"})
    print(actual_output)
    assert actual_output
    parsed_output = json.loads(actual_output)
    assert parsed_output.get("status") == "success"
