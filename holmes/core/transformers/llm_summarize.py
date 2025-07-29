"""
LLM Summarize Transformer for fast model summarization of large tool outputs.
"""

import logging
from typing import Any, Dict, Optional

from .base import BaseTransformer, TransformerError
from ..llm import DefaultLLM, LLM

logger = logging.getLogger(__name__)


class LLMSummarizeTransformer(BaseTransformer):
    """
    Transformer that uses a fast LLM model to summarize large tool outputs.

    This transformer applies summarization when:
    1. A fast model is available
    2. The input length exceeds the configured threshold

    Configuration options:
    - input_threshold: Minimum input length to trigger summarization (default: 1000)
    - prompt: Custom prompt template for summarization (optional)
    - fast_model: Fast model name for summarization (e.g., "gpt-4o-mini")
    - api_key: API key for the fast model (optional, uses default if not provided)
    """

    DEFAULT_PROMPT = """Summarize this operational data focusing on:
- What needs attention or immediate action
- Group similar entries into a single line and description
- Make sure to mention outliers, errors, and non-standard patterns
- List normal/healthy patterns as aggregate descriptions
- When listing problematic entries, also try to use aggregate descriptions when possible
- When possible, mention exact keywords, IDs, or patterns so the user can filter/search the original data and drill down on the parts they care about (extraction over abstraction)"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM Summarize Transformer.

        Args:
            config: Configuration dictionary with optional:
                - input_threshold: Minimum input length for summarization
                - prompt: Custom summarization prompt
                - fast_model: Fast model name for summarization (e.g., "gpt-4o-mini")
                - api_key: API key for the fast model (optional)
        """
        super().__init__(config)
        self._fast_llm: Optional[LLM] = None

        # Create fast LLM instance if fast_model is provided
        fast_model = self.config.get("fast_model")
        if fast_model:
            api_key = self.config.get("api_key")
            try:
                self._fast_llm = DefaultLLM(fast_model, api_key)
                logger.debug(f"Created fast LLM instance with model: {fast_model}")
            except Exception as e:
                logger.warning(f"Failed to create fast LLM instance: {e}")
                self._fast_llm = None

    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if "input_threshold" in self.config:
            threshold = self.config["input_threshold"]
            if not isinstance(threshold, int) or threshold < 0:
                raise ValueError("input_threshold must be a non-negative integer")

        if "prompt" in self.config:
            prompt = self.config["prompt"]
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("prompt must be a non-empty string")

        if "fast_model" in self.config:
            fast_model = self.config["fast_model"]
            if not isinstance(fast_model, str) or not fast_model.strip():
                raise ValueError("fast_model must be a non-empty string")

    def should_apply(self, input_text: str) -> bool:
        """
        Determine if summarization should be applied to the input.

        Args:
            input_text: The tool output to check

        Returns:
            True if summarization should be applied, False otherwise
        """
        # Skip if no fast model is configured
        if self._fast_llm is None:
            logger.debug("Skipping summarization: no fast model configured")
            return False

        # Check if input exceeds threshold
        threshold = self.config.get("input_threshold", 1000)
        input_length = len(input_text)

        if input_length <= threshold:
            logger.debug(
                f"Skipping summarization: input length {input_length} <= threshold {threshold}"
            )
            return False

        logger.debug(
            f"Applying summarization: input length {input_length} > threshold {threshold}"
        )
        return True

    def transform(self, input_text: str) -> str:
        """
        Transform the input text by summarizing it with the fast model.

        Args:
            input_text: The tool output to summarize

        Returns:
            Summarized text

        Raises:
            TransformerError: If summarization fails
        """
        if self._fast_llm is None:
            raise TransformerError("Cannot transform: no fast model configured")

        try:
            # Get the prompt to use
            prompt = self.config.get("prompt", self.DEFAULT_PROMPT)

            # Construct the full prompt with the content
            full_prompt = f"{prompt}\n\nContent to summarize:\n{input_text}"

            # Perform the summarization
            logger.debug(f"Summarizing {len(input_text)} characters with fast model")

            response = self._fast_llm.completion(
                [{"role": "user", "content": full_prompt}]
            )
            summarized_text = response.choices[0].message.content  # type: ignore

            if not summarized_text or not summarized_text.strip():
                raise TransformerError("Fast model returned empty summary")

            logger.debug(
                f"Summarization complete: {len(input_text)} -> {len(summarized_text)} characters"
            )

            return summarized_text.strip()

        except Exception as e:
            error_msg = f"Failed to summarize content with fast model: {e}"
            logger.error(error_msg)
            raise TransformerError(error_msg) from e

    @property
    def name(self) -> str:
        """Get the transformer name."""
        return "llm_summarize"
