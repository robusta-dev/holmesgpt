"""
Unit tests for transformer validation module.
"""

import pytest
from unittest.mock import patch
from typing import Optional
from pydantic import Field, field_validator

from holmes.core.transformers.validation import (
    TransformerValidationError,
    validate_transformer_config,
    validate_transformer_configs,
    validate_tool_transformer_configs,
    safe_validate_tool_transformer_configs,
)
from holmes.core.transformers.base import BaseTransformer
from holmes.core.transformers import registry


class MockValidTransformer(BaseTransformer):
    """Mock transformer that always validates successfully."""

    def transform(self, input_text: str) -> str:
        return f"valid_transformed: {input_text}"

    def should_apply(self, input_text: str) -> bool:
        return True

    @property
    def name(self) -> str:
        return "mock_valid"


class MockConfigTransformer(BaseTransformer):
    """Mock transformer with config validation."""

    required_param: str = Field(description="Required parameter for testing")
    invalid_param: Optional[str] = Field(default=None, description="Parameter for testing validation")

    @field_validator('invalid_param')
    @classmethod
    def validate_invalid_param(cls, v):
        if v == "invalid":
            raise ValueError("invalid_param has invalid value")
        return v

    def transform(self, input_text: str) -> str:
        return f"config_transformed: {input_text}"

    def should_apply(self, input_text: str) -> bool:
        return True

    @property
    def name(self) -> str:
        return "mock_config"


class TestTransformerValidationError:
    """Test TransformerValidationError exception."""

    def test_transformer_validation_error_creation(self):
        """Test creation of TransformerValidationError."""
        error = TransformerValidationError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestValidateTransformerConfig:
    """Test validate_transformer_config function."""

    def setup_method(self):
        """Set up test fixtures."""
        registry.register("mock_valid", MockValidTransformer)
        registry.register("mock_config", MockConfigTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        for transformer_name in ["mock_valid", "mock_config"]:
            if registry.is_registered(transformer_name):
                registry.unregister(transformer_name)

    def test_validate_valid_config(self):
        """Test validation passes for valid configuration."""
        config = {"mock_valid": {}}
        validate_transformer_config(config)  # Should not raise

    def test_validate_config_with_params(self):
        """Test validation passes for valid configuration with parameters."""
        config = {"mock_config": {"required_param": "value"}}
        validate_transformer_config(config)  # Should not raise

    def test_validate_non_dict_config(self):
        """Test validation fails for non-dictionary configuration."""
        with pytest.raises(TransformerValidationError, match="must be a dictionary"):
            validate_transformer_config("not a dict")  # type: ignore

        with pytest.raises(TransformerValidationError, match="must be a dictionary"):
            validate_transformer_config(["list", "not", "dict"])  # type: ignore

    def test_validate_empty_config(self):
        """Test validation fails for empty configuration."""
        with pytest.raises(
            TransformerValidationError, match="exactly one transformer type"
        ):
            validate_transformer_config({})

    def test_validate_multiple_transformers(self):
        """Test validation fails for multiple transformers in one config."""
        config = {"mock_valid": {}, "mock_config": {"required_param": "value"}}
        with pytest.raises(
            TransformerValidationError, match="exactly one transformer type"
        ):
            validate_transformer_config(config)

    def test_validate_unknown_transformer(self):
        """Test validation fails for unknown transformer."""
        config = {"unknown_transformer": {}}
        with pytest.raises(
            TransformerValidationError,
            match="Unknown transformer 'unknown_transformer'",
        ):
            validate_transformer_config(config)

    def test_validate_invalid_transformer_config(self):
        """Test validation fails for invalid transformer-specific configuration."""
        config = {"mock_config": {}}  # Missing required_param
        with pytest.raises(
            TransformerValidationError,
            match="Invalid configuration for transformer 'mock_config'",
        ):
            validate_transformer_config(config)

        config = {
            "mock_config": {"required_param": "value", "invalid_param": "invalid"}
        }
        with pytest.raises(
            TransformerValidationError,
            match="Invalid configuration for transformer 'mock_config'",
        ):
            validate_transformer_config(config)


class TestValidateTransformsList:
    """Test validate_transforms_list function."""

    def setup_method(self):
        """Set up test fixtures."""
        registry.register("mock_valid", MockValidTransformer)
        registry.register("mock_config", MockConfigTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        for transformer_name in ["mock_valid", "mock_config"]:
            if registry.is_registered(transformer_name):
                registry.unregister(transformer_name)

    def test_validate_valid_transforms_list(self):
        """Test validation passes for valid transforms list."""
        transforms = [{"mock_valid": {}}, {"mock_config": {"required_param": "value"}}]
        validate_transformer_configs(transforms)  # Should not raise

    def test_validate_empty_transforms_list(self):
        """Test validation passes for empty transforms list."""
        validate_transformer_configs([])  # Should not raise

    def test_validate_non_list_transforms(self):
        """Test validation fails for non-list transforms."""
        with pytest.raises(TransformerValidationError, match="must be a list"):
            validate_transformer_configs("not a list")  # type: ignore

        with pytest.raises(TransformerValidationError, match="must be a list"):
            validate_transformer_configs({"mock_valid": {}})  # type: ignore

    def test_validate_transforms_list_with_invalid_item(self):
        """Test validation fails when list contains invalid transformer config."""
        transforms = [
            {"mock_valid": {}},
            {"unknown_transformer": {}},  # Invalid
            {"mock_config": {"required_param": "value"}},
        ]
        with pytest.raises(
            TransformerValidationError,
            match="Invalid transformer configuration at index 1",
        ):
            validate_transformer_configs(transforms)

    def test_validate_transforms_list_with_invalid_config(self):
        """Test validation fails when list contains transformer with invalid config."""
        transforms = [
            {"mock_valid": {}},
            {"mock_config": {}},  # Missing required_param
        ]
        with pytest.raises(
            TransformerValidationError,
            match="Invalid transformer configuration at index 1",
        ):
            validate_transformer_configs(transforms)


class TestValidateToolTransforms:
    """Test validate_tool_transforms function."""

    def setup_method(self):
        """Set up test fixtures."""
        registry.register("mock_valid", MockValidTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        if registry.is_registered("mock_valid"):
            registry.unregister("mock_valid")

    def test_validate_none_transforms(self):
        """Test validation passes for None transforms."""
        validate_tool_transformer_configs("test_tool", None)  # Should not raise

    def test_validate_valid_tool_transforms(self):
        """Test validation passes for valid tool transforms."""
        transforms = [{"mock_valid": {}}]
        validate_tool_transformer_configs("test_tool", transforms)  # Should not raise

    def test_validate_invalid_tool_transforms(self):
        """Test validation fails for invalid tool transforms."""
        transforms = [{"unknown_transformer": {}}]
        with pytest.raises(
            TransformerValidationError, match="Validation failed for tool 'test_tool'"
        ):
            validate_tool_transformer_configs("test_tool", transforms)


class TestSafeValidateToolTransforms:
    """Test safe_validate_tool_transforms function."""

    def setup_method(self):
        """Set up test fixtures."""
        registry.register("mock_valid", MockValidTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        if registry.is_registered("mock_valid"):
            registry.unregister("mock_valid")

    def test_safe_validate_none_transforms(self):
        """Test safe validation returns True for None transforms."""
        result = safe_validate_tool_transformer_configs("test_tool", None)
        assert result is True

    def test_safe_validate_valid_transforms(self):
        """Test safe validation returns True for valid transforms."""
        transforms = [{"mock_valid": {}}]
        result = safe_validate_tool_transformer_configs("test_tool", transforms)
        assert result is True

    def test_safe_validate_invalid_transforms(self):
        """Test safe validation returns False and logs warning for invalid transforms."""
        transforms = [{"unknown_transformer": {}}]

        with patch("holmes.core.transformers.validation.logger") as mock_logger:
            result = safe_validate_tool_transformer_configs("test_tool", transforms)

            assert result is False
            mock_logger.warning.assert_called_once()
            # Check that warning message contains tool name and error details
            warning_call = mock_logger.warning.call_args[0][0]
            assert "test_tool" in warning_call
            assert "Transform validation failed" in warning_call

    def test_safe_validate_multiple_invalid_transforms(self):
        """Test safe validation handles multiple validation errors."""
        transforms = [{"unknown_transformer1": {}}, {"unknown_transformer2": {}}]

        with patch("holmes.core.transformers.validation.logger") as mock_logger:
            result = safe_validate_tool_transformer_configs("test_tool", transforms)

            assert result is False
            mock_logger.warning.assert_called_once()


class TestValidationIntegration:
    """Test validation integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        registry.register("mock_valid", MockValidTransformer)
        registry.register("mock_config", MockConfigTransformer)

    def teardown_method(self):
        """Clean up test fixtures."""
        for transformer_name in ["mock_valid", "mock_config"]:
            if registry.is_registered(transformer_name):
                registry.unregister(transformer_name)

    def test_complex_valid_configuration(self):
        """Test validation of complex but valid configuration."""
        transforms = [
            {"mock_valid": {}},
            {"mock_config": {"required_param": "value1"}},
            {"mock_valid": {"optional_param": "value2"}},
        ]

        # All validation functions should pass
        validate_transformer_configs(transforms)
        validate_tool_transformer_configs("complex_tool", transforms)
        result = safe_validate_tool_transformer_configs("complex_tool", transforms)
        assert result is True

    def test_mixed_valid_invalid_configuration(self):
        """Test validation properly identifies errors in mixed configuration."""
        transforms = [
            {"mock_valid": {}},  # Valid
            {"unknown_transformer": {}},  # Invalid - unknown
            {"mock_config": {"required_param": "value"}},  # Valid
            {"mock_config": {}},  # Invalid - missing required param
        ]

        # Should fail at the first invalid transformer (index 1)
        with pytest.raises(
            TransformerValidationError,
            match="Invalid transformer configuration at index 1",
        ):
            validate_transformer_configs(transforms)

    def test_validation_error_propagation(self):
        """Test that validation errors properly propagate through the call stack."""
        transforms = [{"mock_config": {"invalid_param": "invalid"}}]

        # Test error propagation from validate_tool_transforms
        with pytest.raises(TransformerValidationError) as exc_info:
            validate_tool_transformer_configs("error_tool", transforms)

        # Should contain tool name in error message
        assert "error_tool" in str(exc_info.value)

        # Should contain underlying error details from the validation chain
        error_str = str(exc_info.value)
        assert "Field required" in error_str or "required_param" in error_str
