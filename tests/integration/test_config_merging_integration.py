"""
Integration tests for config merging functionality.
Tests the complete CLI --fast-model workflow with real-world toolset configurations.
"""

from unittest.mock import patch

from holmes.core.tools import YAMLTool, YAMLToolset, ToolsetTag
from holmes.core.toolset_manager import ToolsetManager


def create_kubernetes_toolset():
    """Create a Kubernetes toolset similar to the real one with transformer configs."""
    # Create tools with transformer configs like the real Kubernetes toolset
    kubectl_describe = YAMLTool(
        name="kubectl_describe",
        description="Run kubectl describe",
        command="kubectl describe {{ kind }} {{ name }}",
        transformer_configs=[
            {
                "llm_summarize": {
                    "input_threshold": 1000,
                    "prompt": "Summarize kubectl describe output...",
                }
            }
        ],
    )

    kubectl_get = YAMLTool(
        name="kubectl_get_by_kind_in_namespace",
        description="Run kubectl get",
        command="kubectl get {{ kind }} -n {{ namespace }}",
        transformer_configs=[
            {
                "llm_summarize": {
                    "input_threshold": 1000,
                    "prompt": "Summarize kubectl output...",
                }
            }
        ],
    )

    # Create toolset without fast_model (like real YAML configs)
    return YAMLToolset(
        name="kubernetes/core",
        tags=[ToolsetTag.CORE],
        description="Kubernetes toolset",
        tools=[kubectl_describe, kubectl_get],
    )


def test_cli_fast_model_integration_with_kubernetes():
    """
    Integration test: CLI --fast-model should work with Kubernetes toolset.
    This is the critical test case from the plan.
    """
    # Simulate CLI --fast-model setting
    global_configs = [{"llm_summarize": {"fast_model": "azure/gpt-4.1"}}]

    kubernetes_toolset = create_kubernetes_toolset()

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [kubernetes_toolset]

        manager = ToolsetManager(global_transformer_configs=global_configs)
        toolsets = manager._list_all_toolsets(check_prerequisites=False)

        # Find the Kubernetes toolset
        k8s_toolset = next(t for t in toolsets if t.name == "kubernetes/core")

        # Verify that tools inherited the fast_model from global config
        kubectl_describe = next(
            t for t in k8s_toolset.tools if t.name == "kubectl_describe"
        )

        # Extract transformer config
        config_dict = {}
        if kubectl_describe.transformer_configs:
            for config in kubectl_describe.transformer_configs:
                config_dict.update(config)

        # Verify merging worked correctly
        assert config_dict["llm_summarize"]["fast_model"] == "azure/gpt-4.1"  # From CLI
        assert config_dict["llm_summarize"]["input_threshold"] == 1000  # From YAML
        assert "prompt" in config_dict["llm_summarize"]  # From YAML


def test_three_level_inheritance_chain():
    """
    Test the complete inheritance chain: Global → Toolset → Tool
    """
    # Global config (CLI --fast-model)
    global_configs = [
        {"llm_summarize": {"fast_model": "gpt-4.1", "input_threshold": 500}}
    ]

    # Tool with specific override
    tool_with_override = YAMLTool(
        name="specific_tool",
        description="Tool with specific config",
        command="echo test",
        transformer_configs=[{"llm_summarize": {"input_threshold": 2000}}],
    )

    # Tool without specific config (should inherit from toolset)
    tool_without_config = YAMLTool(
        name="generic_tool", description="Generic tool", command="echo generic"
    )

    # Toolset with transformer configs
    toolset = YAMLToolset(
        name="test_toolset",
        tags=[ToolsetTag.CORE],
        description="Test toolset",
        transformer_configs=[
            {"llm_summarize": {"input_threshold": 1000, "prompt": "Toolset prompt"}}
        ],
        tools=[tool_with_override, tool_without_config],
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [toolset]

        manager = ToolsetManager(global_transformer_configs=global_configs)
        toolsets = manager._list_all_toolsets(check_prerequisites=False)

        test_toolset = toolsets[0]

        # Check tool with override (should have highest precedence)
        specific_tool = next(t for t in test_toolset.tools if t.name == "specific_tool")
        assert(specific_tool.transformer_configs) is not None
        specific_config = {}
        for config in specific_tool.transformer_configs:
            specific_config.update(config)

        assert (
            specific_config["llm_summarize"]["input_threshold"] == 2000
        )  # Tool override
        assert (
            specific_config["llm_summarize"]["fast_model"] == "gpt-4.1"
        )  # From global
        assert (
            specific_config["llm_summarize"]["prompt"] == "Toolset prompt"
        )  # From toolset

        # Check tool without config (should inherit merged toolset config)
        generic_tool = next(t for t in test_toolset.tools if t.name == "generic_tool")
        generic_config = {}
        assert(generic_tool.transformer_configs) is not None
        for config in generic_tool.transformer_configs:
            generic_config.update(config)

        assert (
            generic_config["llm_summarize"]["input_threshold"] == 1000
        )  # From toolset
        assert generic_config["llm_summarize"]["fast_model"] == "gpt-4.1"  # From global
        assert (
            generic_config["llm_summarize"]["prompt"] == "Toolset prompt"
        )  # From toolset


def test_multiple_transformer_types_integration():
    """
    Test that different transformer types can coexist and merge independently.
    Note: Using only llm_summarize since that's the only registered transformer.
    """
    global_configs = [
        {"llm_summarize": {"fast_model": "gpt-4o-mini", "input_threshold": 500}}
    ]

    toolset_configs = [
        {"llm_summarize": {"input_threshold": 1000, "prompt": "Toolset prompt"}}
    ]

    tool_configs = [{"llm_summarize": {"prompt": "Custom prompt"}}]

    tool = YAMLTool(
        name="multi_transformer_tool",
        description="Tool with multiple transformers",
        command="echo test",
        transformer_configs=tool_configs,
    )

    toolset = YAMLToolset(
        name="multi_transformer_toolset",
        tags=[ToolsetTag.CORE],
        description="Multi transformer toolset",
        transformer_configs=toolset_configs,
        tools=[tool],
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [toolset]

        manager = ToolsetManager(global_transformer_configs=global_configs)
        toolsets = manager._list_all_toolsets(check_prerequisites=False)

        result_toolset = toolsets[0]
        result_tool = result_toolset.tools[0]

        # Convert to dict for easier testing
        final_config = {}
        assert result_tool.transformer_configs is not None
        for config in result_tool.transformer_configs:
            final_config.update(config)

        # Verify merging worked correctly across all three levels
        assert (
            final_config["llm_summarize"]["fast_model"] == "gpt-4o-mini"
        )  # From global
        assert final_config["llm_summarize"]["input_threshold"] == 1000  # From toolset
        assert (
            final_config["llm_summarize"]["prompt"] == "Custom prompt"
        )  # From tool (highest precedence)

        # Should have 1 transformer type
        assert len(final_config) == 1


def test_backward_compatibility():
    """
    Test that toolsets without transformer configs still work correctly.
    """
    global_configs = [{"llm_summarize": {"fast_model": "gpt-4o-mini"}}]

    # Toolset without transformer configs (like some existing toolsets)
    simple_toolset = YAMLToolset(
        name="simple_toolset",
        tags=[ToolsetTag.CORE],
        description="Simple toolset without transformer configs",
        tools=[YAMLTool(name="simple_tool", description="Simple", command="echo")],
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [simple_toolset]

        manager = ToolsetManager(global_transformer_configs=global_configs)
        toolsets = manager._list_all_toolsets(check_prerequisites=False)

        result_toolset = toolsets[0]

        # Toolset should receive global configs
        assert result_toolset.transformer_configs == global_configs

        # Tool should inherit the configs too
        tool = result_toolset.tools[0]
        assert tool.transformer_configs == global_configs


def test_no_global_configs_no_regression():
    """
    Test that existing behavior is unchanged when no global configs are provided.
    """
    toolset_configs = [{"llm_summarize": {"input_threshold": 1000}}]

    toolset = YAMLToolset(
        name="existing_toolset",
        tags=[ToolsetTag.CORE],
        description="Existing toolset",
        transformer_configs=toolset_configs,
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [toolset]

        # No global configs (normal case)
        manager = ToolsetManager()
        toolsets = manager._list_all_toolsets(check_prerequisites=False)

        result_toolset = toolsets[0]

        # Should remain unchanged
        assert result_toolset.transformer_configs == toolset_configs
