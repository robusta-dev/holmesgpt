"""Tests for backwards compatibility of transformer configuration changes."""

from unittest.mock import Mock, patch
from pathlib import Path
import sys

from holmes.config import Config
from holmes.core.toolset_manager import ToolsetManager
from holmes.core.tools import Toolset, Tool
from holmes.core.transformers import Transformer

# Setup global namespace for Config model rebuilding
sys.modules[__name__].__dict__["Transformer"] = Transformer
Config.model_rebuild()


class TestBackwardsCompatibility:
    """Test that existing configurations continue to work unchanged."""

    def test_existing_config_without_transformers_works(self):
        """Test that existing configs without transformers still work."""
        # Simulate an existing config file without transformers
        config_data = {"model": "gpt-4o", "api_key": "test-key", "max_steps": 5}

        # Should not raise any exceptions
        config = Config(**config_data)

        assert config.model == "gpt-4o"
        assert config.transformers is None
        assert config.max_steps == 5

    def test_existing_toolsets_without_transformers_work(self):
        """Test that existing toolsets without transformers continue to work."""
        # Create a toolset without transformers (existing behavior)
        mock_tool = Mock(spec=Tool)
        mock_tool.transformers = None
        mock_tool.name = "test_tool"

        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = None
        mock_toolset.tools = [mock_tool]
        mock_toolset.name = "test_toolset"

        # Create ToolsetManager without global fast model (existing behavior)
        manager = ToolsetManager()

        # Should not raise any exceptions
        manager._inject_fast_model_into_transformers([mock_toolset])

        # Nothing should change (no injection occurs when no global_fast_model)
        assert mock_toolset.transformers is None
        assert mock_tool.transformers is None

    def test_existing_toolsets_with_transformers_unchanged(self):
        """Test that existing toolsets with transformers get global_fast_model injection."""
        existing_tool_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 300})
        ]
        existing_toolset_configs = [
            Transformer(name="llm_summarize", config={"input_threshold": 600})
        ]

        # Create tool and toolset with existing configs
        mock_tool = Mock(spec=Tool)
        mock_tool.transformers = existing_tool_configs
        mock_tool.name = "test_tool"
        mock_tool._transformer_instances = []

        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformers = existing_toolset_configs
        mock_toolset.tools = [mock_tool]
        mock_toolset.name = "test_toolset"

        # Apply global fast model
        global_fast_model = "gpt-4o-mini"

        with patch("holmes.core.transformers.registry") as mock_registry:
            mock_instance = Mock()
            mock_registry.create_transformer.return_value = mock_instance

            manager = ToolsetManager(global_fast_model=global_fast_model)
            manager._inject_fast_model_into_transformers([mock_toolset])

            # Existing configs should get global_fast_model injected
            assert existing_tool_configs[0].config["global_fast_model"] == "gpt-4o-mini"
            assert (
                existing_toolset_configs[0].config["global_fast_model"] == "gpt-4o-mini"
            )

            # Original config values should remain
            assert existing_tool_configs[0].config["input_threshold"] == 300
            assert existing_toolset_configs[0].config["input_threshold"] == 600

    def test_config_load_from_file_backwards_compatible(self):
        """Test that Config.load_from_file works with existing config files."""
        # Mock an existing config file without transformers
        mock_config_content = {
            "model": "gpt-4o",
            "max_steps": 10,
            "alertmanager_url": "http://localhost:9093",
        }

        with patch("holmes.config.load_model_from_file") as mock_load:
            mock_load.return_value = Config(**mock_config_content)

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                # Should load successfully without transformers
                config = Config.load_from_file(Path("fake_config.yaml"))

                assert config.model == "gpt-4o"
                assert config.max_steps == 10
                assert config.transformers is None

    def test_config_load_from_env_backwards_compatible(self):
        """Test that Config.load_from_env works as before."""
        test_env = {"MODEL": "gpt-4o", "API_KEY": "test-key", "MAX_STEPS": "8"}

        with patch.dict("os.environ", test_env):
            with patch(
                "holmes.config.Config._Config__get_cluster_name"
            ) as mock_cluster:
                mock_cluster.return_value = "test-cluster"

                config = Config.load_from_env()

                assert config.model == "gpt-4o"
                assert config.max_steps == 8
                assert config.transformers is None

    def test_toolset_preprocess_tools_still_works(self):
        """Test that Toolset.preprocess_tools validator still works with Transformer objects."""
        # Test the existing behavior for toolset-level transformers
        values = {
            "additional_instructions": "Test instructions",
            "transformers": [
                Transformer(name="llm_summarize", config={"input_threshold": 500})
            ],
            "tools": [
                {
                    "name": "test_tool",
                    "description": "Test tool",
                    # No transformers - should inherit from toolset
                },
                {
                    "name": "tool_with_configs",
                    "description": "Tool with configs",
                    "transformers": [
                        Transformer(
                            name="llm_summarize", config={"input_threshold": 200}
                        )
                    ],
                    # Has its own configs - should not inherit
                },
            ],
        }

        # Import the actual validator
        from holmes.core.tools import Toolset

        # Call the validator (this is what Pydantic does internally)
        processed_values = Toolset.preprocess_tools(values)

        # Check that existing behavior is preserved
        assert (
            processed_values["tools"][0]["additional_instructions"]
            == "Test instructions"
        )
        assert (
            processed_values["tools"][1]["additional_instructions"]
            == "Test instructions"
        )

        # Tool without configs should inherit toolset configs (as Transformer objects)
        tool0_transformers = processed_values["tools"][0]["transformers"]
        assert len(tool0_transformers) == 1
        assert tool0_transformers[0].name == "llm_summarize"
        assert tool0_transformers[0].config["input_threshold"] == 500

        # Tool with configs should keep its own (as Transformer objects)
        tool1_transformers = processed_values["tools"][1]["transformers"]
        assert len(tool1_transformers) == 1
        assert tool1_transformers[0].name == "llm_summarize"
        assert tool1_transformers[0].config["input_threshold"] == 200

    def test_yaml_toolsets_continue_working(self):
        """Test that YAML toolsets without transformers continue working."""
        # This would be a typical YAML toolset definition without transformers
        yaml_toolset_data = {
            "name": "test/toolset",
            "description": "Test toolset",
            "enabled": True,
            "tools": [
                {
                    "name": "test_tool",
                    "description": "Test tool",
                    "command": "echo 'test'",
                }
            ],
        }

        # Should create successfully without transformers
        from holmes.core.tools import YAMLToolset

        toolset = YAMLToolset(**yaml_toolset_data)

        assert toolset.name == "test/toolset"
        assert toolset.transformers is None
        assert len(toolset.tools) == 1
        assert toolset.tools[0].transformers is None

    def test_python_toolsets_continue_working(self):
        """Test that Python toolsets without transformers continue working."""
        # Simulate existing Python toolset without transformers
        from holmes.core.tools import Toolset, Tool

        # Create a basic tool without transformers
        basic_tool = Mock(spec=Tool)
        basic_tool.name = "basic_tool"
        basic_tool.transformers = None

        # Create toolset data without transformers
        toolset_data = {
            "name": "test/python_toolset",
            "description": "Test Python toolset",
            "tools": [basic_tool],
        }

        # Should work exactly as before
        class TestToolset(Toolset):
            def get_example_config(self):
                return {}

        toolset = TestToolset(**toolset_data)

        assert toolset.name == "test/python_toolset"
        assert toolset.transformers is None
        assert len(toolset.tools) == 1

    def test_no_regression_in_tool_execution(self):
        """Test that tool execution behavior hasn't regressed."""
        # Mock a tool without transformers
        from holmes.core.tools import StructuredToolResult, ToolResultStatus

        class TestTool(Tool):
            def _invoke(self, params):
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS, data="test output"
                )

            def get_parameterized_one_liner(self, params):
                return "test tool execution"

        tool = TestTool(name="test_tool", description="Test tool", transformers=None)

        # Tool should execute normally without transformers
        result = tool.invoke({})

        assert result.status == ToolResultStatus.SUCCESS
        assert result.data == "test output"

    def test_toolset_manager_backwards_compatible_constructor(self):
        """Test that ToolsetManager constructor is backwards compatible."""
        # Old way of creating ToolsetManager (without global_fast_model)
        manager = ToolsetManager(
            toolsets={"test": {"enabled": True}},
            custom_toolsets=None,
            custom_toolsets_from_cli=None,
        )

        # Should work fine
        assert manager.toolsets == {"test": {"enabled": True}}
        assert manager.global_fast_model is None

        # New way should also work
        global_fast_model = "gpt-4o-mini"
        manager_with_fast_model = ToolsetManager(
            toolsets={"test": {"enabled": True}},
            global_fast_model=global_fast_model,
        )

        assert manager_with_fast_model.global_fast_model == global_fast_model
