"""
Base transformer abstract class for tool output transformation.
"""

__all__ = ["BaseTransformer", "TransformerError"]

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TransformerError(Exception):
    """Exception raised when transformer operations fail."""

    pass


class BaseTransformer(ABC):
    """
    Abstract base class for all tool output transformers.

    Transformers process tool outputs before they are returned to the LLM,
    enabling operations like summarization, filtering, or format conversion.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the transformer with optional configuration.

        Args:
            config: Optional configuration dictionary for the transformer
        """
        self.config = config or {}
        self._validate_config()

    @abstractmethod
    def transform(self, input_text: str) -> str:
        """
        Transform the input text and return the transformed output.

        Args:
            input_text: The raw tool output to transform

        Returns:
            The transformed output text

        Raises:
            TransformerError: If transformation fails
        """
        pass

    @abstractmethod
    def should_apply(self, input_text: str) -> bool:
        """
        Determine whether this transformer should be applied to the input.

        Args:
            input_text: The raw tool output to check

        Returns:
            True if the transformer should be applied, False otherwise
        """
        pass

    def _validate_config(self) -> None:
        """
        Validate the transformer configuration.

        Subclasses should override this method to implement
        transformer-specific validation logic.

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @property
    def name(self) -> str:
        """
        Get the transformer name.

        Returns:
            The transformer name (class name by default)
        """
        return self.__class__.__name__
