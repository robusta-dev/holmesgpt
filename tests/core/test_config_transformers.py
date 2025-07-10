"""Tests for global transformer configuration inheritance."""

from unittest.mock import Mock, patch
import sys

from holmes.config import Config
from holmes.core.toolset_manager import ToolsetManager
from holmes.core.tools import Toolset, Tool
from holmes.core.transformers import Transformer, registry

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

    def test_config_passes_fast_model_to_toolset_manager(self):
        """Test that Config passes fast_model to ToolsetManager."""

        config_data = {"model": "gpt-4o", "fast_model": "gpt-4o-mini"}

        config = Config(**config_data)

        # Access the toolset_manager property to trigger creation
        toolset_manager = config.toolset_manager

        assert toolset_manager.global_fast_model == "gpt-4o-mini"

    @patch("holmes.config.ToolsetManager")
    def test_toolset_manager_receives_fast_model(self, mock_toolset_manager):
        """Test that ToolsetManager receives global fast_model."""

        config_data = {"model": "gpt-4o", "fast_model": "gpt-4o-mini"}

        config = Config(**config_data)

        # Access toolset_manager to trigger creation
        _ = config.toolset_manager

        # Verify ToolsetManager was called with global_fast_model
        mock_toolset_manager.assert_called_once()
        call_kwargs = mock_toolset_manager.call_args[1]
        assert call_kwargs["global_fast_model"] == "gpt-4o-mini"


class TestToolsetManagerFastModel:
    """Test ToolsetManager fast model injection functionality."""

    def test_toolset_manager_stores_global_fast_model(self):
        """Test that ToolsetManager stores global fast model."""
        global_fast_model = "gpt-4o-mini"

        manager = ToolsetManager(global_fast_model=global_fast_model)

        assert manager.global_fast_model == global_fast_model

    def test_inject_fast_model_to_transformers_with_existing_configs(self):
        """Test that fast model is injected into transformers without fast_model config."""
        global_fast_model = "gpt-4o-mini"

        # Create a real Transformer instance with the config (not a mock)
        mock_transformer = Transformer(
            name="llm_summarize", config={"input_threshold": 1000}
        )

        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = [mock_transformer]
        mock_toolset.tools = []
        mock_toolset.name = "test_toolset"

        manager = ToolsetManager(global_fast_model=global_fast_model)
        manager._inject_fast_model_into_transformers([mock_toolset])

        # Should inject global_fast_model into transformer config
        assert mock_transformer.config["global_fast_model"] == "gpt-4o-mini"

    def test_does_not_inject_when_fast_model_already_exists(self):
        """Test that existing fast_model configs are not overridden."""
        global_fast_model = "gpt-4o-mini"

        # Create transformer with existing fast_model using real Transformer instance
        mock_transformer = Transformer(
            name="llm_summarize",
            config={
                "input_threshold": 500,
                "fast_model": "existing-model",
            },
        )

        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = [mock_transformer]
        mock_toolset.tools = []
        mock_toolset.name = "test_toolset"

        manager = ToolsetManager(global_fast_model=global_fast_model)
        manager._inject_fast_model_into_transformers([mock_toolset])

        # Should NOT override existing fast_model
        assert mock_transformer.config["fast_model"] == "existing-model"
        assert "global_fast_model" not in mock_transformer.config

    def test_inject_into_tool_level_transformers(self):
        """Test that fast model is injected into tool-level transformers."""
        global_fast_model = "gpt-4o-mini"

        # Create mock tool with transformers that need fast_model using real Transformer
        mock_tool_transformer = Transformer(
            name="llm_summarize", config={"input_threshold": 200}
        )

        mock_tool = Mock(spec=Tool)
        mock_tool.transformers = [mock_tool_transformer]
        mock_tool.name = "test_tool"
        mock_tool._transformer_instances = []

        # Create mock toolset without toolset-level transformers
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = [mock_tool]
        mock_toolset.name = "test_toolset"

        # Mock the transformer registry
        mock_instance = Mock()
        with patch.object(registry, "create_transformer") as mock_create_transformer:
            mock_create_transformer.return_value = mock_instance

            manager = ToolsetManager(global_fast_model=global_fast_model)
            manager._inject_fast_model_into_transformers([mock_toolset])

            # Should inject global_fast_model into tool transformer
            assert mock_tool_transformer.config["global_fast_model"] == "gpt-4o-mini"
            # Should recreate transformer instances
            mock_create_transformer.assert_called_once_with(
                "llm_summarize", mock_tool_transformer.config
            )
            assert mock_tool._transformer_instances == [mock_instance]

    def test_skips_non_llm_summarize_transformers(self):
        """Test that injection only affects llm_summarize transformers."""
        global_fast_model = "gpt-4o-mini"

        # Create transformers with different names using real Transformer instances
        llm_transformer = Transformer(
            name="llm_summarize", config={"input_threshold": 200}
        )

        other_transformer = Transformer(
            name="custom_transformer", config={"some_param": "value"}
        )

        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = [llm_transformer, other_transformer]
        mock_toolset.tools = []
        mock_toolset.name = "test_toolset"

        manager = ToolsetManager(global_fast_model=global_fast_model)
        manager._inject_fast_model_into_transformers([mock_toolset])

        # Should inject into llm_summarize transformer
        assert llm_transformer.config["global_fast_model"] == "gpt-4o-mini"
        # Should NOT inject into other transformer
        assert "global_fast_model" not in other_transformer.config

    def test_handles_none_global_fast_model_gracefully(self):
        """Test that None global fast model is handled gracefully."""
        # Create mock toolset
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = []
        mock_toolset.name = "test_toolset"

        manager = ToolsetManager(global_fast_model=None)

        # Should not raise an exception
        manager._inject_fast_model_into_transformers([mock_toolset])

        # Toolset configs should remain unchanged
        assert mock_toolset.transformers is None

    def test_handles_empty_global_fast_model_gracefully(self):
        """Test that empty global fast model is handled gracefully."""
        # Create mock toolset
        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = []
        mock_toolset.name = "test_toolset"

        manager = ToolsetManager(global_fast_model="")

        # Should not raise an exception and should not inject
        manager._inject_fast_model_into_transformers([mock_toolset])

        # Toolset configs should remain unchanged
        assert mock_toolset.transformers is None


class TestFastModelInjectionIntegration:
    """Integration tests for fast model injection functionality."""

    def test_fast_model_injection_end_to_end(self):
        """Test complete fast model injection: ToolsetManager → Transformers."""
        global_fast_model = "gpt-4o-mini"

        # Create transformers with different configurations using real Transformer instances
        toolset_transformer = Transformer(
            name="llm_summarize", config={"input_threshold": 500}
        )

        tool_transformer = Transformer(
            name="llm_summarize", config={"input_threshold": 200}
        )

        existing_fast_model_transformer = Transformer(
            name="llm_summarize", config={"fast_model": "existing-model"}
        )

        # Create tools
        tool_with_transformers = Mock(spec=Tool)
        tool_with_transformers.transformers = [tool_transformer]
        tool_with_transformers.name = "tool1"
        tool_with_transformers._transformer_instances = []

        tool_with_existing_fast_model = Mock(spec=Tool)
        tool_with_existing_fast_model.transformers = [existing_fast_model_transformer]
        tool_with_existing_fast_model.name = "tool2"
        tool_with_existing_fast_model._transformer_instances = []

        # Create toolset with transformers and tools
        toolset_with_transformers = Mock(spec=Toolset)
        toolset_with_transformers.transformers = [toolset_transformer]
        toolset_with_transformers.tools = [
            tool_with_transformers,
            tool_with_existing_fast_model,
        ]
        toolset_with_transformers.name = "test_toolset"

        # Mock transformer recreation
        mock_instance = Mock()
        with patch("holmes.core.transformers.registry") as mock_registry:
            mock_registry.create_transformer.return_value = mock_instance

            # Apply fast model injection
            manager = ToolsetManager(global_fast_model=global_fast_model)
            manager._inject_fast_model_into_transformers([toolset_with_transformers])

        # Verify injection results:
        # 1. Toolset transformer should get global_fast_model
        assert toolset_transformer.config["global_fast_model"] == "gpt-4o-mini"

        # 2. Tool transformer should get global_fast_model
        assert tool_transformer.config["global_fast_model"] == "gpt-4o-mini"

        # 3. Transformer with existing fast_model should remain unchanged
        assert "global_fast_model" not in existing_fast_model_transformer.config
        assert existing_fast_model_transformer.config["fast_model"] == "existing-model"

        # 4. Only tool transformers should trigger instance recreation
        # (toolset transformers don't have _transformer_instances)
        assert (
            mock_registry.create_transformer.call_count == 1
        )  # Only tool should get recreation
