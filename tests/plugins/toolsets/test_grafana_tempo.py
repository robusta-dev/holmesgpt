from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import (
    GrafanaTempoToolset,
    GetTempoTraces,
)


def test_grafana_tempo_has_prompt():
    toolset = GrafanaTempoToolset()
    tool = GetTempoTraces(toolset)
    assert tool.name is not None
    assert toolset.llm_instructions is not None
    assert tool.name in toolset.llm_instructions
