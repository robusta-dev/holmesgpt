"""
Transformer validation utilities for validating transformer configurations during tool loading.
"""

import logging
from typing import Any, Dict, List, Optional

from .registry import registry

logger = logging.getLogger(__name__)


class TransformerValidationError(Exception):
    """Exception raised when transformer validation fails."""

    pass


def validate_transformer_config(transformer_config: Dict[str, Any]) -> None:
    """
    Validate a single transformer configuration.

    Args:
        transformer_config: Dictionary containing transformer configuration
                         Expected format: {"transformer_name": {...config...}}

    Raises:
        TransformerValidationError: If configuration is invalid
    """
    if not isinstance(transformer_config, dict):
        raise TransformerValidationError("Transform configuration must be a dictionary")

    if len(transformer_config) != 1:
        raise TransformerValidationError(
            "Each transform configuration must contain exactly one transformer type"
        )

    transformer_name = list(transformer_config.keys())[0]
    transformer_config = transformer_config[transformer_name]

    # Check if transformer is registered
    if not registry.is_registered(transformer_name):
        available_transformers = ", ".join(registry.list_transformers())
        raise TransformerValidationError(
            f"Unknown transformer '{transformer_name}'. "
            f"Available transformers: {available_transformers}"
        )

    # Validate transformer configuration by attempting to create it
    try:
        registry.create_transformer(transformer_name, transformer_config)
        logger.debug(f"Successfully validated transformer '{transformer_name}'")
    except Exception as e:
        raise TransformerValidationError(
            f"Invalid configuration for transformer '{transformer_name}': {e}"
        ) from e


def validate_transformer_configs(transformer_configs: List[Dict[str, Any]]) -> None:
    """
    Validate a list of transformer configurations.

    Args:
        transformer_configs: List of transformer configurations

    Raises:
        TransformerValidationError: If any configuration is invalid
    """
    if not isinstance(transformer_configs, list):
        raise TransformerValidationError(
            "Transforms must be a list of transformer configurations"
        )

    for i, transformer_config in enumerate(transformer_configs):
        try:
            validate_transformer_config(transformer_config)
        except TransformerValidationError as e:
            raise TransformerValidationError(
                f"Invalid transformer configuration at index {i}: {e}"
            ) from e


def validate_tool_transformer_configs(
    tool_name: str, transformer_configs: Optional[List[Dict[str, Any]]]
) -> None:
    """
    Validate transformer configurations for a specific tool.

    Args:
        tool_name: Name of the tool being validated
        transformer_configs: Optional list of transformer configurations

    Raises:
        TransformerValidationError: If any configuration is invalid
    """
    if transformer_configs is None:
        return

    try:
        validate_transformer_configs(transformer_configs)
        logger.debug(f"Successfully validated transforms for tool '{tool_name}'")
    except TransformerValidationError as e:
        raise TransformerValidationError(
            f"Validation failed for tool '{tool_name}': {e}"
        ) from e


def safe_validate_tool_transformer_configs(
    tool_name: str, transformer_configs: Optional[List[Dict[str, Any]]]
) -> bool:
    """
    Safely validate transformer configurations for a tool, logging errors instead of raising.

    Args:
        tool_name: Name of the tool being validated
        transformer_configs: Optional list of transformer configurations

    Returns:
        True if validation passes, False if it fails
    """
    try:
        validate_tool_transformer_configs(tool_name, transformer_configs)
        return True
    except TransformerValidationError as e:
        logger.warning(f"Transform validation failed for tool '{tool_name}': {e}")
        return False
