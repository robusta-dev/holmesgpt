"""Tests for backwards compatibility of transformer configuration changes."""

from unittest.mock import Mock, patch
from pathlib import Path

from holmes.config import Config
from holmes.core.toolset_manager import ToolsetManager
from holmes.core.tools import Toolset, Tool


class TestBackwardsCompatibility:
    """Test that existing configurations continue to work unchanged."""

    def test_existing_config_without_transformer_configs_works(self):
        """Test that existing configs without transformer_configs still work."""
        # Simulate an existing config file without transformer_configs
        config_data = {"model": "gpt-4o", "api_key": "test-key", "max_steps": 5}

        # Should not raise any exceptions
        config = Config(**config_data)

        assert config.model == "gpt-4o"
        assert config.transformer_configs is None
        assert config.max_steps == 5

    def test_existing_toolsets_without_transformer_configs_work(self):
        """Test that existing toolsets without transformer configs continue to work."""
        # Create a toolset without transformer configs (existing behavior)
        mock_tool = Mock(spec=Tool)
        mock_tool.transformer_configs = None

        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = None
        mock_toolset.tools = [mock_tool]

        # Create ToolsetManager without global configs (existing behavior)
        manager = ToolsetManager()

        # Should not raise any exceptions
        manager._apply_global_transformer_configs([mock_toolset])

        # Nothing should change
        assert mock_toolset.transformer_configs is None
        assert mock_tool.transformer_configs is None

    def test_existing_toolsets_with_transformer_configs_unchanged(self):
        """Test that existing toolsets with transformer configs are unchanged."""
        existing_tool_configs = [{"llm_summarize": {"input_threshold": 300}}]
        existing_toolset_configs = [{"llm_summarize": {"input_threshold": 600}}]

        # Create tool and toolset with existing configs
        mock_tool = Mock(spec=Tool)
        mock_tool.transformer_configs = existing_tool_configs

        mock_toolset = Mock(spec=Toolset)
        mock_toolset.transformer_configs = existing_toolset_configs
        mock_toolset.tools = [mock_tool]

        # Apply global configs
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]
        manager = ToolsetManager(global_transformer_configs=global_configs)
        manager._apply_global_transformer_configs([mock_toolset])

        # Existing configs should be completely unchanged
        assert mock_tool.transformer_configs == existing_tool_configs
        assert mock_toolset.transformer_configs == existing_toolset_configs

    def test_config_load_from_file_backwards_compatible(self):
        """Test that Config.load_from_file works with existing config files."""
        # Mock an existing config file without transformer_configs
        mock_config_content = {
            "model": "gpt-4o",
            "max_steps": 10,
            "alertmanager_url": "http://localhost:9093",
        }

        with patch("holmes.config.load_model_from_file") as mock_load:
            mock_load.return_value = Config(**mock_config_content)

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                # Should load successfully without transformer_configs
                config = Config.load_from_file(Path("fake_config.yaml"))

                assert config.model == "gpt-4o"
                assert config.max_steps == 10
                assert config.transformer_configs is None

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
                assert config.transformer_configs is None

    def test_toolset_preprocess_tools_still_works(self):
        """Test that existing Toolset.preprocess_tools validator still works."""
        # Test the existing behavior for toolset-level transformer configs
        values = {
            "additional_instructions": "Test instructions",
            "transformer_configs": [{"llm_summarize": {"input_threshold": 500}}],
            "tools": [
                {
                    "name": "test_tool",
                    "description": "Test tool",
                    # No transformer_configs - should inherit from toolset
                },
                {
                    "name": "tool_with_configs",
                    "description": "Tool with configs",
                    "transformer_configs": [
                        {"llm_summarize": {"input_threshold": 200}}
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

        # Tool without configs should inherit toolset configs
        assert processed_values["tools"][0]["transformer_configs"] == [
            {"llm_summarize": {"input_threshold": 500}}
        ]

        # Tool with configs should keep its own
        assert processed_values["tools"][1]["transformer_configs"] == [
            {"llm_summarize": {"input_threshold": 200}}
        ]

    def test_yaml_toolsets_continue_working(self):
        """Test that YAML toolsets without transformer configs continue working."""
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

        # Should create successfully without transformer configs
        from holmes.core.tools import YAMLToolset

        toolset = YAMLToolset(**yaml_toolset_data)

        assert toolset.name == "test/toolset"
        assert toolset.transformer_configs is None
        assert len(toolset.tools) == 1
        assert toolset.tools[0].transformer_configs is None

    def test_python_toolsets_continue_working(self):
        """Test that Python toolsets without transformer configs continue working."""
        # Simulate existing Python toolset without transformer configs
        from holmes.core.tools import Toolset, Tool

        # Create a basic tool without transformer configs
        basic_tool = Mock(spec=Tool)
        basic_tool.name = "basic_tool"
        basic_tool.transformer_configs = None

        # Create toolset data without transformer_configs
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
        assert toolset.transformer_configs is None
        assert len(toolset.tools) == 1

    def test_no_regression_in_tool_execution(self):
        """Test that tool execution behavior hasn't regressed."""
        # Mock a tool without transformer configs
        from holmes.core.tools import StructuredToolResult, ToolResultStatus

        class TestTool(Tool):
            def _invoke(self, params):
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS, data="test output"
                )

            def get_parameterized_one_liner(self, params):
                return "test tool execution"

        tool = TestTool(
            name="test_tool", description="Test tool", transformer_configs=None
        )

        # Tool should execute normally without transformer configs
        result = tool.invoke({})

        assert result.status == ToolResultStatus.SUCCESS
        assert result.data == "test output"

    def test_toolset_manager_backwards_compatible_constructor(self):
        """Test that ToolsetManager constructor is backwards compatible."""
        # Old way of creating ToolsetManager (without global_transformer_configs)
        manager = ToolsetManager(
            toolsets={"test": {"enabled": True}},
            custom_toolsets=None,
            custom_toolsets_from_cli=None,
        )

        # Should work fine
        assert manager.toolsets == {"test": {"enabled": True}}
        assert manager.global_transformer_configs is None

        # New way should also work
        global_configs = [{"llm_summarize": {"input_threshold": 1000}}]
        manager_with_configs = ToolsetManager(
            toolsets={"test": {"enabled": True}},
            global_transformer_configs=global_configs,
        )

        assert manager_with_configs.global_transformer_configs == global_configs
