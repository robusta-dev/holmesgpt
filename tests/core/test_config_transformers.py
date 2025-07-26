"""Tests for global transformer configuration inheritance."""

from unittest.mock import Mock, patch

from holmes.config import Config
from holmes.core.toolset_manager import ToolsetManager
from holmes.core.tools import Toolset, Tool


class TestConfigTransformers:
    """Test global transformer configuration functionality."""

    def test_config_loads_transformer_configs_from_dict(self):
        """Test that Config correctly loads transformer_configs from dict."""
        config_data = {
            "model": "gpt-4o",
            "transformer_configs": [
                {"llm_summarize": {"input_threshold": 1000, "prompt": "Test prompt"}}
            ],
        }

        config = Config(**config_data)

        assert config.transformer_configs is not None
        assert len(config.transformer_configs) == 1
        assert "llm_summarize" in config.transformer_configs[0]
        assert config.transformer_configs[0]["llm_summarize"]["input_threshold"] == 1000
        assert config.transformer_configs[0]["llm_summarize"]["prompt"] == "Test prompt"

    def test_config_handles_none_transformer_configs(self):
        """Test that Config handles None transformer_configs gracefully."""
        config_data = {"model": "gpt-4o", "transformer_configs": None}

        config = Config(**config_data)

        assert config.transformer_configs is None

    def test_config_handles_empty_transformer_configs(self):
        """Test that Config handles empty transformer_configs list."""
        config_data = {"model": "gpt-4o", "transformer_configs": []}

        config = Config(**config_data)

        assert config.transformer_configs == []

    def test_config_passes_transformer_configs_to_toolset_manager(self):
        """Test that Config passes transformer_configs to ToolsetManager."""
        transformer_configs = [{"llm_summarize": {"input_threshold": 500}}]

        config_data = {"model": "gpt-4o", "transformer_configs": transformer_configs}

        config = Config(**config_data)

        # Access the toolset_manager property to trigger creation
        toolset_manager = config.toolset_manager

        assert toolset_manager.global_transformer_configs == transformer_configs

    @patch("holmes.config.ToolsetManager")
    def test_toolset_manager_receives_global_configs(self, mock_toolset_manager):
        """Test that ToolsetManager receives global transformer configs."""
        transformer_configs = [{"llm_summarize": {"input_threshold": 800}}]

        config_data = {"model": "gpt-4o", "transformer_configs": transformer_configs}

        config = Config(**config_data)

        # Access toolset_manager to trigger creation
        _ = config.toolset_manager

        # Verify ToolsetManager was called with global_transformer_configs
        mock_toolset_manager.assert_called_once()
        call_kwargs = mock_toolset_manager.call_args[1]
        assert call_kwargs["global_transformer_configs"] == transformer_configs


class TestToolsetManagerTransformers:
    """Test ToolsetManager transformer configuration inheritance."""

    def test_toolset_manager_stores_global_transformer_configs(self):
        """Test that ToolsetManager stores global transformer configs."""
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]

        manager = ToolsetManager(global_transformer_configs=global_configs)

        assert manager.global_transformer_configs == global_configs

    def test_apply_global_transformer_configs_to_toolset_without_configs(self):
        """Test applying global configs to toolset without its own configs."""
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]

        # Create a mock toolset without transformer configs
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = None
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformer_configs=global_configs)
        manager._apply_global_transformer_configs([mock_toolset])

        assert mock_toolset.transformer_configs == global_configs

    def test_does_not_override_existing_toolset_configs(self):
        """Test that existing toolset configs are not overridden by global configs."""
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]
        existing_configs = [{"llm_summarize": {"input_threshold": 500}}]

        # Create a mock toolset with existing transformer configs
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = existing_configs
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformer_configs=global_configs)
        manager._apply_global_transformer_configs([mock_toolset])

        # Existing configs should remain unchanged
        assert mock_toolset.transformer_configs == existing_configs

    def test_apply_global_configs_to_tools_without_configs(self):
        """Test that tool inheritance is handled by existing preprocess_tools logic."""
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]

        # Create mock tool without transformer configs
        mock_tool = Mock(spec=Tool)
        mock_tool.transformer_configs = None

        # Create mock toolset without transformer configs
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = None
        mock_toolset.tools = [mock_tool]

        manager = ToolsetManager(global_transformer_configs=global_configs)
        manager._apply_global_transformer_configs([mock_toolset])

        # Only toolset should receive global configs
        # Tool inheritance is handled by Toolset.preprocess_tools() during toolset creation
        assert mock_toolset.transformer_configs == global_configs
        assert (
            mock_tool.transformer_configs is None
        )  # Unchanged by global config application

    def test_tool_configs_override_global_configs(self):
        """Test that tool-level configs are not overridden by global configs."""
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]
        tool_configs = [{"llm_summarize": {"input_threshold": 200}}]

        # Create mock tool with existing transformer configs
        mock_tool = Mock(spec=Tool)
        mock_tool.transformer_configs = tool_configs

        # Create mock toolset without transformer configs
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = None
        mock_toolset.tools = [mock_tool]

        manager = ToolsetManager(global_transformer_configs=global_configs)
        manager._apply_global_transformer_configs([mock_toolset])

        # Toolset should get global configs, but tool should keep its own
        assert mock_toolset.transformer_configs == global_configs
        assert mock_tool.transformer_configs == tool_configs

    def test_toolset_configs_prevent_global_application_to_tools(self):
        """Test that toolset configs prevent global configs from being applied to tools."""
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]
        toolset_configs = [{"llm_summarize": {"input_threshold": 500}}]

        # Create mock tool without transformer configs
        mock_tool = Mock(spec=Tool)
        mock_tool.transformer_configs = None

        # Create mock toolset with transformer configs
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = toolset_configs
        mock_toolset.tools = [mock_tool]

        manager = ToolsetManager(global_transformer_configs=global_configs)
        manager._apply_global_transformer_configs([mock_toolset])

        # Toolset should keep its configs, tool should not get global configs
        assert mock_toolset.transformer_configs == toolset_configs
        assert mock_tool.transformer_configs is None

    def test_handles_none_global_configs_gracefully(self):
        """Test that None global configs are handled gracefully."""
        # Create mock toolset
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = None
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformer_configs=None)

        # Should not raise an exception
        manager._apply_global_transformer_configs([mock_toolset])

        # Toolset configs should remain unchanged
        assert mock_toolset.transformer_configs is None

    def test_handles_empty_global_configs_gracefully(self):
        """Test that empty global configs list is handled gracefully."""
        # Create mock toolset
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = None
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformer_configs=[])

        # Should not raise an exception
        manager._apply_global_transformer_configs([mock_toolset])

        # Toolset configs should remain unchanged
        assert mock_toolset.transformer_configs is None


class TestConfigInheritanceIntegration:
    """Integration tests for transformer configuration inheritance."""

    def test_configuration_inheritance_priority(self):
        """Test complete configuration inheritance: Global → Toolset → Tool."""
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]
        toolset_configs = [{"llm_summarize": {"input_threshold": 500}}]
        tool_configs = [{"llm_summarize": {"input_threshold": 200}}]

        # Create tools with different config states
        tool_with_configs = Mock(spec=Tool)
        tool_with_configs.transformer_configs = tool_configs

        tool_without_configs = Mock(spec=Tool)
        tool_without_configs.transformer_configs = None

        # Create toolset with configs and tools
        toolset_with_configs = Mock(spec=Toolset)
        toolset_with_configs.transformer_configs = toolset_configs
        toolset_with_configs.tools = [tool_with_configs, tool_without_configs]

        # Create toolset without configs
        tool_in_no_config_toolset = Mock(spec=Tool)
        tool_in_no_config_toolset.transformer_configs = None

        toolset_without_configs = Mock(spec=Toolset)
        toolset_without_configs.transformer_configs = None
        toolset_without_configs.tools = [tool_in_no_config_toolset]

        # Apply global configs
        manager = ToolsetManager(global_transformer_configs=global_configs)
        manager._apply_global_transformer_configs(
            [toolset_with_configs, toolset_without_configs]
        )

        # Verify inheritance priority:
        # 1. Tool with configs keeps its own configs
        assert tool_with_configs.transformer_configs == tool_configs

        # 2. Tool without configs in toolset with configs doesn't get global configs
        assert tool_without_configs.transformer_configs is None

        # 3. Toolset with configs keeps its own configs
        assert toolset_with_configs.transformer_configs == toolset_configs

        # 4. Toolset without configs gets global configs
        assert toolset_without_configs.transformer_configs == global_configs

        # 5. Tool in toolset without configs doesn't get global configs directly
        # (Tool inheritance is handled by Toolset.preprocess_tools() during toolset creation)
        assert tool_in_no_config_toolset.transformer_configs is None
