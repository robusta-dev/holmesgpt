from holmes.core.tools import ToolsetStatusEnum
from holmes.plugins.prompts import load_and_render_prompt
from holmes.plugins.toolsets.prometheus.prometheus import PrometheusToolset

template = "builtin://generic_ask_conversation.jinja2"


def test_prometheus_prompt_inclusion():
    # Case 1: prometheus/metrics is enabled
    ts = PrometheusToolset()
    ts._status = ToolsetStatusEnum.ENABLED
    context = {"toolsets": [ts]}
    rendered = load_and_render_prompt(template, context)

    # Check prometheus section is included
    assert "# Prometheus/PromQL queries" in rendered
    assert "Use prometheus to execute promql queries" in rendered

    # Case 2: prometheus/metrics is not enabled
    context = {"toolsets": []}
    rendered = load_and_render_prompt(template, context)

    # Check prometheus section is not included
    assert "# Prometheus/PromQL queries" not in rendered
    assert "Use prometheus to execute promql queries" not in rendered

    # Case 3: empty toolsets
    context = {"toolsets": []}
    rendered = load_and_render_prompt(template, context)

    # Check prometheus section is not included
    assert "# Prometheus/PromQL queries" not in rendered
    assert "Use prometheus to execute promql queries" not in rendered
