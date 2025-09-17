from unittest.mock import Mock, patch

import pytest

from holmes.core.llm import LLM
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.core.models import ToolCallResult
from holmes.core.tools_utils.tool_context_window_limiter import (
    prevent_overly_big_tool_response,
)


class TestPreventOverlyBigToolResponse:
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM instance."""
        llm = Mock(spec=LLM)
        llm.get_context_window_size.return_value = 4096
        llm.count_tokens_for_message.return_value = 1000
        return llm

    @pytest.fixture
    def success_tool_call_result(self):
        """Create a successful tool call result."""
        result = StructuredToolResult(
            status=StructuredToolResultStatus.SUCCESS,
            data="Some successful output data",
        )
        return ToolCallResult(
            tool_call_id="test-id-1",
            tool_name="test_tool",
            description="Test tool description",
            result=result,
        )

    def test_no_limit_configured(self, mock_llm, success_tool_call_result):
        """Test that function does nothing when TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT is 0."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            0,
        ):
            original_status = success_tool_call_result.result.status
            original_data = success_tool_call_result.result.data
            original_error = success_tool_call_result.result.error

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Should remain unchanged
            assert success_tool_call_result.result.status == original_status
            assert success_tool_call_result.result.data == original_data
            assert success_tool_call_result.result.error == original_error
            mock_llm.count_tokens_for_message.assert_not_called()

    def test_negative_limit_configured(self, mock_llm, success_tool_call_result):
        """Test that function does nothing when TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT is negative."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            -10,
        ):
            original_status = success_tool_call_result.result.status
            original_data = success_tool_call_result.result.data
            original_error = success_tool_call_result.result.error

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Should remain unchanged
            assert success_tool_call_result.result.status == original_status
            assert success_tool_call_result.result.data == original_data
            assert success_tool_call_result.result.error == original_error
            mock_llm.count_tokens_for_message.assert_not_called()

    def test_over_100_percent_limit(self, mock_llm, success_tool_call_result):
        """Test that function does nothing when TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT is over 100."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            150,
        ):
            original_status = success_tool_call_result.result.status
            original_data = success_tool_call_result.result.data
            original_error = success_tool_call_result.result.error

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Should remain unchanged
            assert success_tool_call_result.result.status == original_status
            assert success_tool_call_result.result.data == original_data
            assert success_tool_call_result.result.error == original_error
            mock_llm.count_tokens_for_message.assert_not_called()

    def test_within_token_limit(self, mock_llm, success_tool_call_result):
        """Test that function does nothing when tool result is within token limit."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            50,
        ):
            # Context window: 4096, 50% = 2048 tokens allowed
            # Token count: 1000 (within limit)
            mock_llm.count_tokens_for_message.return_value = 1000

            original_status = success_tool_call_result.result.status
            original_data = success_tool_call_result.result.data
            original_error = success_tool_call_result.result.error

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Should remain unchanged
            assert success_tool_call_result.result.status == original_status
            assert success_tool_call_result.result.data == original_data
            assert success_tool_call_result.result.error == original_error
            mock_llm.count_tokens_for_message.assert_called_once()

    def test_exceeds_token_limit(self, mock_llm, success_tool_call_result):
        """Test that function modifies result when tool result exceeds token limit."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            50,
        ):
            # Context window: 4096, 50% = 2048 tokens allowed
            # Token count: 3000 (exceeds limit)
            mock_llm.count_tokens_for_message.return_value = 3000

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Should be modified
            assert (
                success_tool_call_result.result.status
                == StructuredToolResultStatus.ERROR
            )
            assert success_tool_call_result.result.data is None
            assert "too large to return" in success_tool_call_result.result.error
            assert "3000 tokens" in success_tool_call_result.result.error
            assert "2048" in success_tool_call_result.result.error
            assert (
                "31.7" in success_tool_call_result.result.error
            )  # (3000-2048)/3000 * 100
            mock_llm.count_tokens_for_message.assert_called_once()

    def test_token_calculation_accuracy(self, mock_llm, success_tool_call_result):
        """Test that token calculations are accurate."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            25,
        ):
            # Context window: 4096, 25% = 1024 tokens allowed
            # Token count: 2000 (exceeds limit)
            mock_llm.count_tokens_for_message.return_value = 2000
            mock_llm.get_context_window_size.return_value = 4096

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Calculate expected percentage: (2000-1024)/2000 * 100 = 48.8%
            assert "48.8" in success_tool_call_result.result.error
            assert "2000 tokens" in success_tool_call_result.result.error
            assert "1024" in success_tool_call_result.result.error

    def test_message_construction_calls_as_tool_call_message(
        self, mock_llm, success_tool_call_result
    ):
        """Test that the function calls as_tool_call_message to get the message for token counting."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            50,
        ):
            mock_llm.count_tokens_for_message.return_value = 1000  # Within limit

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Verify that count_tokens_for_message was called with a list containing one message
            mock_llm.count_tokens_for_message.assert_called_once()
            call_args = mock_llm.count_tokens_for_message.call_args
            assert (
                len(call_args[1]["messages"]) == 1
            )  # Should be called with messages kwarg containing 1 message

    def test_different_context_window_sizes(self, mock_llm, success_tool_call_result):
        """Test with different context window sizes."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            40,
        ):
            # Test with smaller context window
            mock_llm.get_context_window_size.return_value = 2048
            mock_llm.count_tokens_for_message.return_value = 1000
            # 40% of 2048 = 819 tokens allowed, 1000 exceeds this

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            assert (
                success_tool_call_result.result.status
                == StructuredToolResultStatus.ERROR
            )
            assert "1000 tokens" in success_tool_call_result.result.error
            assert "819" in success_tool_call_result.result.error

    def test_edge_case_exactly_at_limit(self, mock_llm, success_tool_call_result):
        """Test behavior when token count is exactly at the limit."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            50,
        ):
            mock_llm.get_context_window_size.return_value = 4096
            mock_llm.count_tokens_for_message.return_value = 2048  # Exactly 50% of 4096

            original_status = success_tool_call_result.result.status
            original_data = success_tool_call_result.result.data

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            # Should remain unchanged (not > max_tokens_allowed)
            assert success_tool_call_result.result.status == original_status
            assert success_tool_call_result.result.data == original_data

    def test_error_message_format(self, mock_llm, success_tool_call_result):
        """Test that error message contains all expected components."""
        with patch(
            "holmes.core.tools_utils.tool_context_window_limiter.TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT",
            20,
        ):
            mock_llm.get_context_window_size.return_value = 5000
            mock_llm.count_tokens_for_message.return_value = 2000
            # 20% of 5000 = 1000 tokens allowed

            prevent_overly_big_tool_response(success_tool_call_result, mock_llm)

            error_msg = success_tool_call_result.result.error
            assert "The tool call result is too large to return" in error_msg
            assert "2000 tokens" in error_msg
            assert "1000" in error_msg
            assert "Instructions for the LLM" in error_msg
            assert "try to repeat the query" in error_msg
            assert "narrow down the result" in error_msg

            # Check percentage calculation: (2000-1000)/2000 * 100 = 50.0%
            assert "50" in error_msg
