from holmes.plugins.prompts import load_and_render_prompt

template = "builtin://generic_ask_conversation.jinja2"


def test_prometheus_prompt_inclusion():
    # Case 1: prometheus/metrics is enabled
    context = {
        "enabled_toolsets": [
            {
                "name": "prometheus/metrics",
                "llm_instructions": "# Prometheus/PromQL queries Use prometheus to execute promql queries",
            },
            {"name": "other_tool"},
        ]
    }
    rendered = load_and_render_prompt(template, context)

    # Check prometheus section is included
    assert "# Prometheus/PromQL queries" in rendered
    assert "Use prometheus to execute promql queries" in rendered

    # Case 2: prometheus/metrics is not enabled
    context = {"enabled_toolsets": [{"name": "other_tool"}]}
    rendered = load_and_render_prompt(template, context)

    # Check prometheus section is not included
    assert "# Prometheus/PromQL queries" not in rendered
    assert "Use prometheus to execute promql queries" not in rendered

    # Case 3: empty toolsets
    context = {"enabled_toolsets": []}
    rendered = load_and_render_prompt(template, context)

    # Check prometheus section is not included
    assert "# Prometheus/PromQL queries" not in rendered
    assert "Use prometheus to execute promql queries" not in rendered
