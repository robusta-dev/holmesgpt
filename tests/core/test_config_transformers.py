"""Tests for global transformer configuration inheritance."""

from unittest.mock import Mock, patch
import sys

from holmes.config import Config
from holmes.core.toolset_manager import ToolsetManager
from holmes.core.tools import Toolset, Tool, Transformer

# Setup global namespace for Config model rebuilding
sys.modules[__name__].__dict__["Transformer"] = Transformer
Config.model_rebuild()


class TestConfigTransformers:
    """Test global transformer configuration functionality."""

    def test_config_loads_transformers_from_dict(self):
        """Test that Config correctly loads transformers from dict."""
        transformers = [
            Transformer(
                name="llm_summarize",
                config={"input_threshold": 1000, "prompt": "Test prompt"},
            )
        ]
        config_data = {
            "model": "gpt-4o",
            "transformers": transformers,
        }

        config = Config(**config_data)

        assert config.transformers is not None
        assert len(config.transformers) == 1
        assert config.transformers[0].name == "llm_summarize"
        assert config.transformers[0].config["input_threshold"] == 1000
        assert config.transformers[0].config["prompt"] == "Test prompt"

    def test_config_handles_none_transformers(self):
        """Test that Config handles None transformers gracefully."""

        config_data = {"model": "gpt-4o", "transformers": None}

        config = Config(**config_data)

        assert config.transformers is None

    def test_config_handles_empty_transformers(self):
        """Test that Config handles empty transformers list."""

        config_data = {"model": "gpt-4o", "transformers": []}

        config = Config(**config_data)

        assert config.transformers == []

    def test_config_passes_transformers_to_toolset_manager(self):
        """Test that Config passes transformers to ToolsetManager."""

        transformers = [
            Transformer(name="llm_summarize", config={"input_threshold": 500})
        ]

        config_data = {"model": "gpt-4o", "transformers": transformers}

        config = Config(**config_data)

        # Access the toolset_manager property to trigger creation
        toolset_manager = config.toolset_manager

        assert toolset_manager.global_transformers == transformers

    @patch("holmes.config.ToolsetManager")
    def test_toolset_manager_receives_global_configs(self, mock_toolset_manager):
        """Test that ToolsetManager receives global transformers."""

        transformers = [
            Transformer(name="llm_summarize", config={"input_threshold": 800})
        ]

        config_data = {"model": "gpt-4o", "transformers": transformers}

        config = Config(**config_data)

        # Access toolset_manager to trigger creation
        _ = config.toolset_manager

        # Verify ToolsetManager was called with global_transformers
        mock_toolset_manager.assert_called_once()
        call_kwargs = mock_toolset_manager.call_args[1]
        assert call_kwargs["global_transformers"] == transformers


class TestToolsetManagerTransformers:
    """Test ToolsetManager transformer configuration inheritance."""

    def test_toolset_manager_stores_global_transformers(self):
        """Test that ToolsetManager stores global transformers."""
        global_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ]

        manager = ToolsetManager(global_transformers=global_configs)

        assert manager.global_transformers == global_configs

    def test_apply_global_transformers_to_toolset_without_configs(self):
        """Test that global transformers are NOT applied to toolsets without configs (new behavior)."""
        global_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ]

        # Create a mock toolset without transformers
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformers=global_configs)
        manager._apply_global_transformers([mock_toolset])

        assert mock_toolset.transformers is None  # Global configs should NOT be applied

    def test_does_not_override_existing_toolset_configs(self):
        """Test that existing toolset configs are not overridden by global configs."""
        global_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ]
        existing_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 500})
        ]

        # Create a mock toolset with existing transformers
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = existing_configs
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformers=global_configs)
        manager._apply_global_transformers([mock_toolset])

        # Existing configs should remain unchanged
        assert mock_toolset.transformers == existing_configs

    def test_apply_global_configs_to_tools_without_configs(self):
        """Test that global transformers are NOT applied when toolset has no transformers (new behavior)."""
        global_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ]

        # Create mock tool without transformers
        mock_tool = Mock(spec=Tool)
        mock_tool.transformers = None

        # Create mock toolset without transformers
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = [mock_tool]

        manager = ToolsetManager(global_transformers=global_configs)
        manager._apply_global_transformers([mock_toolset])

        # Toolset should NOT receive global configs when it has no transformers
        assert mock_toolset.transformers is None
        # Tool transformers remain unchanged
        assert mock_tool.transformers is None

    def test_tool_configs_override_global_configs(self):
        """Test that tool-level configs remain unchanged when toolset has no transformers (new behavior)."""
        global_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ]
        tool_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 200})
        ]

        # Create mock tool with existing transformers
        mock_tool = Mock(spec=Tool)
        mock_tool.transformers = tool_configs

        # Create mock toolset without transformers
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = [mock_tool]

        manager = ToolsetManager(global_transformers=global_configs)
        manager._apply_global_transformers([mock_toolset])

        # Toolset should NOT get global configs when it has none
        assert mock_toolset.transformers is None
        # Tool should keep its own configs unchanged
        assert mock_tool.transformers == tool_configs

    def test_toolset_configs_prevent_global_application_to_tools(self):
        """Test that toolset configs prevent global configs from being applied to tools."""
        global_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ]
        toolset_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 500})
        ]

        # Create mock tool without transformers
        mock_tool = Mock(spec=Tool)
        mock_tool.transformers = None

        # Create mock toolset with transformers
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = toolset_configs
        mock_toolset.tools = [mock_tool]

        manager = ToolsetManager(global_transformers=global_configs)
        manager._apply_global_transformers([mock_toolset])

        # Toolset should keep its configs, tool should inherit from toolset
        assert mock_toolset.transformers == toolset_configs
        assert mock_tool.transformers == toolset_configs

    def test_handles_none_global_configs_gracefully(self):
        """Test that None global configs are handled gracefully."""
        # Create mock toolset
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformers=None)

        # Should not raise an exception
        manager._apply_global_transformers([mock_toolset])

        # Toolset configs should remain unchanged
        assert mock_toolset.transformers is None

    def test_handles_empty_global_configs_gracefully(self):
        """Test that empty global configs list is handled gracefully."""
        # Create mock toolset
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = []

        manager = ToolsetManager(global_transformers=[])

        # Should not raise an exception
        manager._apply_global_transformers([mock_toolset])

        # Toolset configs should remain unchanged
        assert mock_toolset.transformers is None


class TestConfigInheritanceIntegration:
    """Integration tests for transformer configuration inheritance."""

    def test_configuration_inheritance_priority(self):
        """Test complete configuration inheritance: Global → Toolset → Tool."""
        global_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ]
        toolset_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 500})
        ]
        tool_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 200})
        ]

        # Create tools with different config states
        tool_with_configs = Mock(spec=Tool)
        tool_with_configs.transformers = tool_configs

        tool_without_configs = Mock(spec=Tool)
        tool_without_configs.transformers = None

        # Create toolset with configs and tools
        toolset_with_configs = Mock(spec=Toolset)
        toolset_with_configs.transformers = toolset_configs
        toolset_with_configs.tools = [tool_with_configs, tool_without_configs]

        # Create toolset without configs
        tool_in_no_config_toolset = Mock(spec=Tool)
        tool_in_no_config_toolset.transformers = None

        toolset_without_configs = Mock(spec=Toolset)
        toolset_without_configs.transformers = None
        toolset_without_configs.tools = [tool_in_no_config_toolset]

        # Apply global configs
        manager = ToolsetManager(global_transformers=global_configs)
        manager._apply_global_transformers(
            [toolset_with_configs, toolset_without_configs]
        )

        # Verify inheritance priority:
        # 1. Tool with configs keeps its own configs
        assert tool_with_configs.transformers == tool_configs

        # 2. Tool without configs in toolset with configs inherits from toolset
        assert tool_without_configs.transformers == toolset_configs

        # 3. Toolset with configs keeps its own configs
        assert toolset_with_configs.transformers == toolset_configs

        # 4. Toolset without configs does NOT get global configs (new behavior)
        assert toolset_without_configs.transformers is None

        # 5. Tool in toolset without configs also remains None
        assert tool_in_no_config_toolset.transformers is None
