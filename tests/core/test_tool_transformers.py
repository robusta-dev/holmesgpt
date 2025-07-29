"""
Unit tests for Phase 2.1: Tool transformer integration and validation.
"""

import pytest
from typing import Dict
from unittest.mock import Mock, patch

from holmes.core.tools import (
    Tool,
    YAMLTool,
    YAMLToolset,
    ToolsetYamlFromConfig,
    StructuredToolResult,
    ToolResultStatus,
)
from holmes.core.transformers import (
    registry,
    TransformerValidationError,
    TransformerError,
    validate_transformer_config,
    validate_transformer_configs,
    validate_tool_transformer_configs,
    safe_validate_tool_transformer_configs,
)
from holmes.core.transformers.base import BaseTransformer


class MockTransformer(BaseTransformer):
    """Mock transformer for testing."""

    def transform(self, input_text: str) -> str:
        return f"mock_transformed: {input_text}"

    def should_apply(self, input_text: str) -> bool:
        return len(input_text) > 5


class TestToolTransformField:
    """Test that Tool and YAMLTool accept transforms field."""

    def test_tool_with_transforms(self):
        """Test that Tool accepts transforms field."""
        transforms = [{"llm_summarize": {"input_threshold": 500}}]

        # Create a concrete tool for testing
        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> Mock:
                return Mock()

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool",
            description="Test tool with transforms",
            transformer_configs=transforms,
        )

        assert tool.transformer_configs == transforms

    def test_yaml_tool_with_transforms(self):
        """Test that YAMLTool accepts transforms field."""
        transforms = [{"llm_summarize": {"input_threshold": 1000}}]

        tool = YAMLTool(
            name="test_yaml_tool",
            description="Test YAML tool with transforms",
            command="echo 'test'",
            transformer_configs=transforms,
        )

        assert tool.transformer_configs == transforms

    def test_tool_without_transforms(self):
        """Test that tools work without transforms field."""

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> Mock:
                return Mock()

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool", description="Test tool without transforms"
        )

        assert tool.transformer_configs is None


class TestToolsetTransformers:
    """Test that Toolset classes accept transformers parameter."""

    def test_toolset_with_transformers(self):
        """Test that Toolset accepts transformers field."""
        transformers = [{"llm_summarize": {"input_threshold": 800}}]

        toolset = YAMLToolset(
            name="test_toolset",
            description="Test toolset with transformers",
            transformer_configs=transformers,
            tools=[],
        )

        assert toolset.transformer_configs == transformers

    def test_toolset_yaml_from_config_with_transformers(self):
        """Test that ToolsetYamlFromConfig accepts transformers."""
        transformers = [{"llm_summarize": {"input_threshold": 1200}}]

        toolset = ToolsetYamlFromConfig(
            name="test_config_toolset", transformer_configs=transformers
        )

        assert toolset.transformer_configs == transformers

    def test_toolset_transformers_propagation(self):
        """Test that toolset transformers propagate to tools that don't have their own."""
        toolset_transformers = [{"llm_summarize": {"input_threshold": 600}}]

        # Create toolset with transformers
        toolset_data = {
            "name": "test_toolset",
            "description": "Test toolset",
            "transformer_configs": toolset_transformers,
            "tools": [
                {
                    "name": "tool_without_transforms",
                    "description": "Tool without its own transforms",
                    "command": "echo 'test1'",
                },
                {
                    "name": "tool_with_transforms",
                    "description": "Tool with its own transforms",
                    "command": "echo 'test2'",
                    "transformer_configs": [
                        {"llm_summarize": {"input_threshold": 300}}
                    ],
                },
            ],
        }

        toolset = YAMLToolset(**toolset_data)

        # Tool without transforms should inherit from toolset
        assert toolset.tools[0].transformer_configs == toolset_transformers

        # Tool with transforms should keep its own
        assert toolset.tools[1].transformer_configs == [
            {"llm_summarize": {"input_threshold": 300}}
        ]


class TestTransformerValidation:
    """Test transformer validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Register mock transformer for testing
        registry.register("mock_transformer", MockTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        # Unregister mock transformer
        if registry.is_registered("mock_transformer"):
            registry.unregister("mock_transformer")

    def test_validate_transformer_config_valid(self):
        """Test validation of valid transformer configuration."""
        config = {"mock_transformer": {"test_param": "value"}}

        # Should not raise exception
        validate_transformer_config(config)

    def test_validate_transformer_config_invalid_format(self):
        """Test validation fails for invalid configuration format."""
        # Not a dict
        with pytest.raises(TransformerValidationError, match="must be a dictionary"):
            validate_transformer_config("invalid")  # type: ignore

        # Multiple transformers in one config
        with pytest.raises(
            TransformerValidationError, match="exactly one transformer type"
        ):
            validate_transformer_config({"transformer1": {}, "transformer2": {}})

    def test_validate_transformer_config_unknown_transformer(self):
        """Test validation fails for unknown transformer."""
        config = {"unknown_transformer": {}}

        with pytest.raises(TransformerValidationError, match="Unknown transformer"):
            validate_transformer_config(config)

    def test_validate_transformer_config_invalid_config(self):
        """Test validation fails for invalid transformer-specific config."""
        # Use llm_summarize with invalid threshold
        config = {"llm_summarize": {"input_threshold": -1}}

        with pytest.raises(TransformerValidationError, match="Invalid configuration"):
            validate_transformer_config(config)

    def test_validate_transforms_list_valid(self):
        """Test validation of valid transforms list."""
        transforms = [
            {"mock_transformer": {}},
            {"llm_summarize": {"input_threshold": 1000}},
        ]

        # Should not raise exception
        validate_transformer_configs(transforms)

    def test_validate_transforms_list_invalid_format(self):
        """Test validation fails for invalid transforms list format."""
        with pytest.raises(TransformerValidationError, match="must be a list"):
            validate_transformer_configs("not a list")  # type: ignore

    def test_validate_transforms_list_invalid_item(self):
        """Test validation fails for invalid item in transforms list."""
        transforms = [
            {"mock_transformer": {}},
            {"unknown_transformer": {}},  # Invalid
        ]

        with pytest.raises(
            TransformerValidationError,
            match="Invalid transformer configuration at index 1",
        ):
            validate_transformer_configs(transforms)

    def test_validate_tool_transforms_valid(self):
        """Test validation of valid tool transforms."""
        transforms = [{"mock_transformer": {}}]

        # Should not raise exception
        validate_tool_transformer_configs("test_tool", transforms)

    def test_validate_tool_transforms_none(self):
        """Test validation passes for None transforms."""
        # Should not raise exception
        validate_tool_transformer_configs("test_tool", None)

    def test_safe_validate_tool_transforms_valid(self):
        """Test safe validation returns True for valid transforms."""
        transforms = [{"mock_transformer": {}}]

        result = safe_validate_tool_transformer_configs("test_tool", transforms)
        assert result is True

    def test_safe_validate_tool_transforms_invalid(self):
        """Test safe validation returns False for invalid transforms."""
        transforms = [{"unknown_transformer": {}}]

        with patch("holmes.core.transformers.validation.logger") as mock_logger:
            result = safe_validate_tool_transformer_configs("test_tool", transforms)
            assert result is False
            mock_logger.warning.assert_called_once()


class TestToolValidationIntegration:
    """Test transformer validation integration in Tool classes."""

    def setup_method(self):
        """Set up test fixtures."""
        registry.register("mock_transformer", MockTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        if registry.is_registered("mock_transformer"):
            registry.unregister("mock_transformer")

    def test_tool_validation_success(self):
        """Test tool creation succeeds with valid transforms."""
        transforms = [{"mock_transformer": {}}]

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> Mock:
                return Mock()

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool", description="Test tool", transformer_configs=transforms
        )

        assert tool.transformer_configs == transforms

    def test_tool_validation_clears_invalid_transforms(self):
        """Test tool creation clears invalid transforms but continues."""
        invalid_transforms = [{"unknown_transformer": {}}]

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> Mock:
                return Mock()

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        with patch("holmes.core.tools.logging") as mock_logging:
            tool = ConcreteTestTool(
                name="test_tool",
                description="Test tool",
                transformer_configs=invalid_transforms,
            )

            # Transforms should be cleared
            assert tool.transformer_configs is None
            # Warning should be logged
            mock_logging.warning.assert_called()

    def test_yaml_tool_validation(self):
        """Test YAMLTool transformer validation."""
        transforms = [{"mock_transformer": {}}]

        tool = YAMLTool(
            name="test_yaml_tool",
            description="Test YAML tool",
            command="echo 'test'",
            transformer_configs=transforms,
        )

        assert tool.transformer_configs == transforms


class TestBackwardCompatibility:
    """Test that existing tools continue to work without transformers."""

    def test_existing_yaml_tool_compatibility(self):
        """Test that existing YAML tools work without transforms."""
        tool = YAMLTool(
            name="legacy_tool",
            description="Legacy tool without transforms",
            command="echo 'legacy'",
        )

        assert tool.transformer_configs is None
        assert tool.name == "legacy_tool"

    def test_existing_toolset_compatibility(self):
        """Test that existing toolsets work without transformers."""
        toolset = YAMLToolset(
            name="legacy_toolset", description="Legacy toolset", tools=[]
        )

        assert toolset.transformer_configs is None
        assert toolset.name == "legacy_toolset"

    def test_mixed_old_new_tools(self):
        """Test toolset with mix of tools with and without transforms."""
        toolset_data = {
            "name": "mixed_toolset",
            "description": "Mixed toolset",
            "tools": [
                {
                    "name": "legacy_tool",
                    "description": "Legacy tool",
                    "command": "echo 'legacy'",
                },
                {
                    "name": "new_tool",
                    "description": "New tool with transforms",
                    "command": "echo 'new'",
                    "transformer_configs": [{"llm_summarize": {}}],
                },
            ],
        }

        toolset = YAMLToolset(**toolset_data)

        assert toolset.tools[0].transformer_configs is None
        assert toolset.tools[1].transformer_configs == [{"llm_summarize": {}}]


class TestToolExecutionPipeline:
    """Test Tool Execution Pipeline with transformers."""

    def setup_method(self):
        """Set up test fixtures."""
        registry.register("mock_transformer", MockTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        if registry.is_registered("mock_transformer"):
            registry.unregister("mock_transformer")

    def test_successful_tool_execution_with_transformers(self):
        """Test that tools execute successfully and apply transformers."""
        transforms = [{"mock_transformer": {}}]

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> StructuredToolResult:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="This is a long test output that should be transformed",
                )

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool", description="Test tool", transformer_configs=transforms
        )

        result = tool.invoke({})

        # Should have applied transformation
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data is not None
        assert "mock_transformed:" in result.data
        assert "This is a long test output that should be transformed" in result.data

    def test_tool_execution_skips_transformers_on_error(self):
        """Test that transformers are not applied when tool execution fails."""
        transforms = [{"mock_transformer": {}}]

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> StructuredToolResult:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Tool execution failed",
                    data="Some error output",
                )

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool", description="Test tool", transformer_configs=transforms
        )

        result = tool.invoke({})

        # Should not have applied transformation due to error status
        assert result.status == ToolResultStatus.ERROR
        assert "mock_transformed:" not in str(result.data)
        assert result.data == "Some error output"

    def test_tool_execution_skips_transformers_on_empty_data(self):
        """Test that transformers are not applied when data is empty."""
        transforms = [{"mock_transformer": {}}]

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> StructuredToolResult:
                return StructuredToolResult(status=ToolResultStatus.NO_DATA, data="")

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool", description="Test tool", transformer_configs=transforms
        )

        result = tool.invoke({})

        # Should not have applied transformation due to empty data
        assert result.status == ToolResultStatus.NO_DATA
        assert result.data == ""

    def test_transformer_failure_handling(self):
        """Test that transformer failures are handled gracefully."""

        # Create a transformer that will fail
        class FailingTransformer(BaseTransformer):
            def transform(self, input_text: str) -> str:
                raise TransformerError("Transformer failed")

            def should_apply(self, input_text: str) -> bool:
                return True

        registry.register("failing_transformer", FailingTransformer)

        try:
            transforms = [{"failing_transformer": {}}]

            class ConcreteTestTool(Tool):
                def _invoke(self, params: Dict) -> StructuredToolResult:
                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS, data="Test output"
                    )

                def get_parameterized_one_liner(self, params: Dict) -> str:
                    return "test command"

            tool = ConcreteTestTool(
                name="test_tool",
                description="Test tool",
                transformer_configs=transforms,
            )

            with patch("holmes.core.tools.logging") as mock_logging:
                result = tool.invoke({})

                # Should return original data when transformer fails
                assert result.status == ToolResultStatus.SUCCESS
                assert result.data == "Test output"

                # Should log warning about transformer failure
                mock_logging.warning.assert_called()
                warning_call = mock_logging.warning.call_args[0][0]
                assert "failing_transformer" in warning_call
                assert "failed" in warning_call

        finally:
            if registry.is_registered("failing_transformer"):
                registry.unregister("failing_transformer")

    def test_multiple_transformers_chaining(self):
        """Test that multiple transformers are applied in sequence."""

        class SecondTransformer(BaseTransformer):
            def transform(self, input_text: str) -> str:
                return f"second_transformed: {input_text}"

            def should_apply(self, input_text: str) -> bool:
                return True

        registry.register("second_transformer", SecondTransformer)

        try:
            transforms = [{"mock_transformer": {}}, {"second_transformer": {}}]

            class ConcreteTestTool(Tool):
                def _invoke(self, params: Dict) -> StructuredToolResult:
                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS,
                        data="Original text that should be transformed twice",
                    )

                def get_parameterized_one_liner(self, params: Dict) -> str:
                    return "test command"

            tool = ConcreteTestTool(
                name="test_tool",
                description="Test tool",
                transformer_configs=transforms,
            )

            result = tool.invoke({})

            # Should have applied both transformations in sequence
            assert result.status == ToolResultStatus.SUCCESS
            assert result.data is not None
            assert "second_transformed:" in result.data
            assert "mock_transformed:" in result.data

        finally:
            if registry.is_registered("second_transformer"):
                registry.unregister("second_transformer")

    def test_transformer_conditional_application(self):
        """Test that transformers are only applied when should_apply returns True."""

        class ConditionalTransformer(BaseTransformer):
            def transform(self, input_text: str) -> str:
                return f"conditional_transformed: {input_text}"

            def should_apply(self, input_text: str) -> bool:
                # Only apply to inputs longer than 10 characters
                return len(input_text) > 10

        registry.register("conditional_transformer", ConditionalTransformer)

        try:
            transforms = [{"conditional_transformer": {}}]

            class ConcreteTestTool(Tool):
                def _invoke(self, params: Dict) -> StructuredToolResult:
                    data = params.get("data", "short")
                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS, data=data
                    )

                def get_parameterized_one_liner(self, params: Dict) -> str:
                    return "test command"

            tool = ConcreteTestTool(
                name="test_tool",
                description="Test tool",
                transformer_configs=transforms,
            )

            # Test with short input - should not transform
            result = tool.invoke({"data": "short"})
            assert result.data == "short"
            assert (
                result.data is not None
                and "conditional_transformed:" not in result.data
            )

            # Test with long input - should transform
            result = tool.invoke(
                {"data": "this is a very long input that should be transformed"}
            )
            assert result.data is not None
            assert "conditional_transformed:" in result.data

        finally:
            if registry.is_registered("conditional_transformer"):
                registry.unregister("conditional_transformer")

    def test_transformer_preserves_original_result_structure(self):
        """Test that transformer only modifies data field, preserving other result fields."""
        transforms = [{"mock_transformer": {}}]

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> StructuredToolResult:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="Test output to transform",
                    url="http://example.com",
                    invocation="test command",
                    params={"test": "param"},
                    return_code=0,
                )

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool", description="Test tool", transformer_configs=transforms
        )

        result = tool.invoke({})

        # Data should be transformed
        assert result.data is not None
        assert "mock_transformed:" in result.data

        # Other fields should be preserved
        assert result.status == ToolResultStatus.SUCCESS
        assert result.url == "http://example.com"
        assert result.invocation == "test command"
        assert result.params == {"test": "param"}
        assert result.return_code == 0

    def test_performance_metrics_logging(self):
        """Test that transformer performance metrics are logged."""
        transforms = [{"mock_transformer": {}}]

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> StructuredToolResult:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="Test output that will be transformed for performance measurement",
                )

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool", description="Test tool", transformer_configs=transforms
        )

        with patch("holmes.core.tools.logging") as mock_logging:
            result = tool.invoke({})

            # Should log transformer application with performance metrics
            info_calls = [call[0][0] for call in mock_logging.info.call_args_list]
            transformer_log = next(
                (call for call in info_calls if "Applied transformer" in call), None
            )

            assert transformer_log is not None
            assert "mock_transformer" in transformer_log
            assert "test_tool" in transformer_log
            assert "output size:" in transformer_log
            assert "characters)" in transformer_log

    def test_tool_without_transformers_unchanged(self):
        """Test that tools without transformers work exactly as before."""

        class ConcreteTestTool(Tool):
            def _invoke(self, params: Dict) -> StructuredToolResult:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="Test output without transformation",
                )

            def get_parameterized_one_liner(self, params: Dict) -> str:
                return "test command"

        tool = ConcreteTestTool(
            name="test_tool",
            description="Test tool",
            # No transformer_configs
        )

        result = tool.invoke({})

        # Should return unchanged result
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data == "Test output without transformation"
