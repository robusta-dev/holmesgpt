"""
Unit tests for LLMSummarizeTransformer.
"""

import pytest
from unittest.mock import Mock, patch
from pydantic import ValidationError

from holmes.core.transformers.llm_summarize import LLMSummarizeTransformer
from holmes.core.transformers.base import TransformerError


class TestLLMSummarizeTransformer:
    """Test cases for LLMSummarizeTransformer class."""

    def create_mock_llm(self, response_content: str = "Summarized content"):
        """Create a mock LLM that returns the specified response."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()

        mock_message.content = response_content
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_llm.completion.return_value = mock_response

        return mock_llm

    def test_init_with_no_config(self):
        """Test transformer initialization without config."""
        transformer = LLMSummarizeTransformer()
        assert transformer.input_threshold == 1000  # default value
        assert transformer.prompt is None  # default value
        assert transformer.fast_model is None  # default value
        assert transformer.api_key is None  # default value
        assert transformer._fast_llm is None

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_init_with_fast_model_config(self, mock_default_llm):
        """Test transformer initialization with fast_model config."""
        mock_llm_instance = self.create_mock_llm()
        mock_default_llm.return_value = mock_llm_instance

        transformer = LLMSummarizeTransformer(
            input_threshold=500,
            prompt="Custom prompt",
            fast_model="gpt-4o-mini",
            api_key="test-key",
        )

        assert transformer.input_threshold == 500
        assert transformer.prompt == "Custom prompt"
        assert transformer.fast_model == "gpt-4o-mini"
        assert transformer.api_key == "test-key"
        assert transformer._fast_llm is mock_llm_instance
        mock_default_llm.assert_called_once_with("gpt-4o-mini", "test-key")

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_init_with_fast_model_no_api_key(self, mock_default_llm):
        """Test transformer initialization with fast_model but no API key."""
        mock_llm_instance = self.create_mock_llm()
        mock_default_llm.return_value = mock_llm_instance

        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        assert transformer._fast_llm is mock_llm_instance
        mock_default_llm.assert_called_once_with("gpt-4o-mini", None)

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_init_fast_model_creation_failure(self, mock_default_llm):
        """Test transformer initialization handles LLM creation failure."""
        mock_default_llm.side_effect = Exception("LLM creation failed")

        transformer = LLMSummarizeTransformer(fast_model="invalid-model")

        assert transformer._fast_llm is None
        mock_default_llm.assert_called_once_with("invalid-model", None)

    def test_name_property(self):
        """Test transformer name property."""
        transformer = LLMSummarizeTransformer()
        assert transformer.name == "llm_summarize"

    def test_config_validation_success(self):
        """Test successful config validation."""
        with patch("holmes.core.transformers.llm_summarize.DefaultLLM"):
            transformer = LLMSummarizeTransformer(
                input_threshold=100,
                prompt="Valid prompt",
                fast_model="gpt-4o-mini",
            )
            assert transformer.input_threshold == 100
            assert transformer.prompt == "Valid prompt"
            assert transformer.fast_model == "gpt-4o-mini"

    def test_config_validation_invalid_threshold(self):
        """Test config validation with invalid threshold."""
        # Negative threshold
        with pytest.raises(ValidationError):
            LLMSummarizeTransformer(input_threshold=-1)

        # Non-integer threshold
        with pytest.raises(ValidationError):
            LLMSummarizeTransformer(input_threshold="invalid")

        # Non-integer threshold (float) - Pydantic v2 will reject this
        with pytest.raises(ValidationError):
            LLMSummarizeTransformer(input_threshold=100.5)

    def test_config_validation_invalid_prompt(self):
        """Test config validation with invalid prompt."""
        # Empty prompt
        with pytest.raises(ValidationError):
            LLMSummarizeTransformer(prompt="")

        # Non-string prompt
        with pytest.raises(ValidationError):
            LLMSummarizeTransformer(prompt=123)

    def test_config_validation_invalid_fast_model(self):
        """Test config validation with invalid fast_model."""
        # Empty fast_model
        with pytest.raises(ValidationError):
            LLMSummarizeTransformer(fast_model="")

        # Non-string fast_model
        with pytest.raises(ValidationError):
            LLMSummarizeTransformer(fast_model=123)

    def test_should_apply_no_fast_model(self):
        """Test should_apply when no fast model is configured."""
        transformer = LLMSummarizeTransformer()

        # Should not apply regardless of input length
        assert not transformer.should_apply("short")
        assert not transformer.should_apply("a" * 2000)  # Very long input

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_should_apply_with_fast_model_default_threshold(self, mock_default_llm):
        """Test should_apply with fast model and default threshold."""
        mock_default_llm.return_value = self.create_mock_llm()
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        # Default threshold is 1000 characters
        short_text = "a" * 999
        long_text = "a" * 1001

        assert not transformer.should_apply(short_text)
        assert transformer.should_apply(long_text)

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_should_apply_with_custom_threshold(self, mock_default_llm):
        """Test should_apply with custom threshold."""
        mock_default_llm.return_value = self.create_mock_llm()
        transformer = LLMSummarizeTransformer(
            fast_model="gpt-4o-mini", input_threshold=500
        )

        short_text = "a" * 499
        exact_threshold = "a" * 500
        long_text = "a" * 501

        assert not transformer.should_apply(short_text)
        assert not transformer.should_apply(exact_threshold)  # <= threshold, not >
        assert transformer.should_apply(long_text)

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_transform_success_default_prompt(self, mock_default_llm):
        """Test successful transformation with default prompt."""
        mock_llm = self.create_mock_llm("This is a summary")
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        input_text = "Original content to be summarized"
        result = transformer.transform(input_text)

        assert result == "This is a summary"

        # Verify the LLM was called with correct prompt
        mock_llm.completion.assert_called_once()
        call_args = mock_llm.completion.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["role"] == "user"
        assert "Original content to be summarized" in call_args[0]["content"]
        assert transformer.DEFAULT_PROMPT in call_args[0]["content"]

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_transform_success_custom_prompt(self, mock_default_llm):
        """Test successful transformation with custom prompt."""
        mock_llm = self.create_mock_llm("Custom summary")
        mock_default_llm.return_value = mock_llm
        custom_prompt = "Summarize this in a custom way"
        transformer = LLMSummarizeTransformer(
            fast_model="gpt-4o-mini", prompt=custom_prompt
        )

        input_text = "Content to summarize"
        result = transformer.transform(input_text)

        assert result == "Custom summary"

        # Verify custom prompt was used
        call_args = mock_llm.completion.call_args[0][0]
        assert custom_prompt in call_args[0]["content"]
        assert transformer.DEFAULT_PROMPT not in call_args[0]["content"]

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_transform_strips_whitespace(self, mock_default_llm):
        """Test that transformation strips whitespace from response."""
        mock_llm = self.create_mock_llm("  Summary with whitespace  ")
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        result = transformer.transform("input text")
        assert result == "Summary with whitespace"

    def test_transform_no_fast_model(self):
        """Test transform fails when no fast model is configured."""
        transformer = LLMSummarizeTransformer()

        with pytest.raises(
            TransformerError, match="Cannot transform: no fast model configured"
        ):
            transformer.transform("input text")

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_transform_empty_response(self, mock_default_llm):
        """Test transform fails when model returns empty response."""
        mock_llm = self.create_mock_llm("")
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        with pytest.raises(TransformerError, match="Fast model returned empty summary"):
            transformer.transform("input text")

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_transform_whitespace_only_response(self, mock_default_llm):
        """Test transform fails when model returns whitespace-only response."""
        mock_llm = self.create_mock_llm("   ")
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        with pytest.raises(TransformerError, match="Fast model returned empty summary"):
            transformer.transform("input text")

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_transform_llm_exception(self, mock_default_llm):
        """Test transform handles LLM exceptions properly."""
        mock_llm = Mock()
        mock_llm.completion.side_effect = Exception("LLM API error")
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        with pytest.raises(
            TransformerError,
            match="Failed to summarize content with fast model: LLM API error",
        ):
            transformer.transform("input text")

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_transform_malformed_response(self, mock_default_llm):
        """Test transform handles malformed LLM response."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.choices = []  # Empty choices
        mock_llm.completion.return_value = mock_response
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        with pytest.raises(
            TransformerError, match="Failed to summarize content with fast model"
        ):
            transformer.transform("input text")

    def test_default_prompt_content(self):
        """Test that default prompt contains expected guidelines."""
        transformer = LLMSummarizeTransformer()

        # Check key elements of the default prompt
        assert "attention or immediate action" in transformer.DEFAULT_PROMPT
        assert "Group similar entries" in transformer.DEFAULT_PROMPT
        assert (
            "outliers, errors, and non-standard patterns" in transformer.DEFAULT_PROMPT
        )
        assert "exact keywords" in transformer.DEFAULT_PROMPT

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_prompt_construction(self, mock_default_llm):
        """Test that prompts are properly constructed with content."""
        mock_llm = self.create_mock_llm("test response")
        mock_default_llm.return_value = mock_llm
        custom_prompt = "Custom summarization prompt"
        transformer = LLMSummarizeTransformer(
            fast_model="gpt-4o-mini", prompt=custom_prompt
        )

        input_text = "Test content"
        transformer.transform(input_text)

        # Verify prompt structure
        call_args = mock_llm.completion.call_args[0][0]
        full_prompt = call_args[0]["content"]

        assert full_prompt.startswith(custom_prompt)
        assert "Content to summarize:" in full_prompt
        assert full_prompt.endswith(input_text)


class TestLLMSummarizeTransformerIntegration:
    """Integration tests for LLMSummarizeTransformer."""

    def create_mock_llm(self, response_content: str = "Summarized content"):
        """Create a mock LLM that returns the specified response."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()

        mock_message.content = response_content
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_llm.completion.return_value = mock_response

        return mock_llm

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_end_to_end_summarization_workflow(self, mock_default_llm):
        """Test complete summarization workflow."""
        mock_llm = self.create_mock_llm(
            "Summarized: kubectl shows 3 healthy pods, 1 failing"
        )
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(
            fast_model="gpt-4o-mini", input_threshold=100
        )

        # Simulate large kubectl output
        large_output = """
NAME                                READY   STATUS    RESTARTS   AGE
webapp-deployment-abc123-def456     1/1     Running   0          2d
webapp-deployment-abc123-ghi789     1/1     Running   0          2d
webapp-deployment-abc123-jkl012     1/1     Running   0          2d
database-deployment-mno345-pqr678   0/1     Error     3          1d
service/webapp-service              ClusterIP   10.0.1.100   <none>        80/TCP    2d
service/database-service            ClusterIP   10.0.1.101   <none>        5432/TCP  2d
        """.strip()

        # Should apply due to length
        assert transformer.should_apply(large_output)

        # Transform and verify
        result = transformer.transform(large_output)
        assert result == "Summarized: kubectl shows 3 healthy pods, 1 failing"

        # Verify LLM was called with full output
        mock_llm.completion.assert_called_once()
        call_args = mock_llm.completion.call_args[0][0]
        assert large_output in call_args[0]["content"]

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_conditional_application_workflow(self, mock_default_llm):
        """Test that transformation is conditionally applied based on threshold."""
        mock_llm = self.create_mock_llm("Should not be called")
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(
            fast_model="gpt-4o-mini", input_threshold=1000
        )

        # Small output that shouldn't be summarized
        small_output = "pod/webapp-123 is running"

        # Should not apply
        assert not transformer.should_apply(small_output)

        # Large output that should be summarized
        large_output = "a" * 1001
        assert transformer.should_apply(large_output)

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_error_handling_workflow(self, mock_default_llm):
        """Test error handling in real-world scenarios."""
        # Test with failing LLM
        mock_llm = Mock()
        mock_llm.completion.side_effect = ConnectionError("Network timeout")
        mock_default_llm.return_value = mock_llm
        transformer = LLMSummarizeTransformer(fast_model="gpt-4o-mini")

        with pytest.raises(TransformerError) as exc_info:
            transformer.transform("input to summarize")

        # Verify error is properly wrapped and chained
        assert "Failed to summarize content with fast model" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ConnectionError)
        assert "Network timeout" in str(exc_info.value.__cause__)

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_different_threshold_scenarios(self, mock_default_llm):
        """Test various threshold scenarios."""
        mock_llm = self.create_mock_llm("summary")

        test_cases = [
            (0, "x", True),  # Zero threshold, any input > 0 applies
            (1, "", False),  # Empty input, any positive threshold
            (5, "short", False),  # Input exactly at threshold (not >)
            (5, "longer", True),  # Input above threshold
            (1000, "x" * 999, False),  # Just below default
            (1000, "x" * 1000, False),  # Exactly at threshold
            (1000, "x" * 1001, True),  # Above threshold
        ]

        for threshold, input_text, expected in test_cases:
            mock_default_llm.return_value = mock_llm
            transformer = LLMSummarizeTransformer(
                fast_model="gpt-4o-mini", input_threshold=threshold
            )

            result = transformer.should_apply(input_text)
            assert (
                result == expected
            ), f"Failed for threshold={threshold}, input_len={len(input_text)}"

    @patch("holmes.core.transformers.llm_summarize.DefaultLLM")
    def test_multiple_transformer_instances(self, mock_default_llm):
        """Test using multiple transformer instances with different configs."""
        mock_llm1 = self.create_mock_llm("Summary 1")
        mock_llm2 = self.create_mock_llm("Summary 2")

        def mock_llm_side_effect(model, api_key):
            if model == "gpt-4o-mini":
                return mock_llm1
            elif model == "gpt-3.5-turbo":
                return mock_llm2
            return Mock()

        mock_default_llm.side_effect = mock_llm_side_effect

        transformer1 = LLMSummarizeTransformer(
            fast_model="gpt-4o-mini",
            input_threshold=10,
            prompt="Brief summary:",
        )

        transformer2 = LLMSummarizeTransformer(
            fast_model="gpt-3.5-turbo",
            input_threshold=20,
            prompt="Detailed summary:",
        )

        test_input = "This is test input content"

        # Both should apply (length > both thresholds)
        assert transformer1.should_apply(test_input)
        assert transformer2.should_apply(test_input)

        # Transform with both
        result1 = transformer1.transform(test_input)
        result2 = transformer2.transform(test_input)

        assert result1 == "Summary 1"
        assert result2 == "Summary 2"

        # Verify each used their own LLM and prompt
        mock_llm1.completion.assert_called_once()
        mock_llm2.completion.assert_called_once()

        call1 = mock_llm1.completion.call_args[0][0][0]["content"]
        call2 = mock_llm2.completion.call_args[0][0][0]["content"]

        assert "Brief summary:" in call1
        assert "Detailed summary:" in call2
