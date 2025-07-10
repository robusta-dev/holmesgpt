"""
Transformer system for processing tool outputs.

This module provides the infrastructure for transforming tool outputs
before they are passed to the LLM for analysis.
"""

from .base import BaseTransformer, TransformerError
from .registry import TransformerRegistry, registry
from .llm_summarize import LLMSummarizeTransformer
from .validation import (
    TransformerValidationError,
    validate_transformer_config,
    validate_transformer_configs,
    validate_tool_transformer_configs,
    safe_validate_tool_transformer_configs,
)

# Register built-in transformers
registry.register("llm_summarize", LLMSummarizeTransformer)

__all__ = [
    "BaseTransformer",
    "TransformerError",
    "TransformerRegistry",
    "registry",
    "LLMSummarizeTransformer",
    "TransformerValidationError",
    "validate_transformer_config",
    "validate_transformer_configs",
    "validate_tool_transformer_configs",
    "safe_validate_tool_transformer_configs",
]
