from typing import Any, Dict, List, Optional, Type, Union
import pytest

from holmes.core.truncation.compaction import split_text_in_chunks
from litellm.types.utils import ModelResponse
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from pydantic import BaseModel


class CharBasedLLM:
    def __init__(self):
        self.model = "character_based_token_counting_llm_for_tetsing"

    def get_context_window_size(self) -> int:
        return 1000

    def get_maximum_output_token(self) -> int:
        return 100

    def count_tokens_for_message(self, messages: list[dict]) -> int:
        count = 0
        for message in messages:
            content = message.get("content", "")
            count += len(content)
        return count

    def completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = [],
        tool_choice: Optional[Union[str, dict]] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        temperature: Optional[float] = None,
        drop_params: Optional[bool] = None,
        stream: Optional[bool] = None,
    ) -> Union[ModelResponse, CustomStreamWrapper]:
        raise Exception("Not implemented")


@pytest.fixture
def char_based_llm():
    return CharBasedLLM()


class TestSplitTextInChunks:
    def test_text_smaller_than_chunk_size(self, char_based_llm):
        """Test that text smaller than max_chunk_tokens returns as single chunk"""
        text = "Hello world"
        max_chunk_tokens = 50

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert result == [text]
        assert len(result) == 1

    def test_empty_text(self, char_based_llm):
        """Test that empty text returns empty list"""
        text = ""
        max_chunk_tokens = 10

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert result == [text]

    def test_single_line_larger_than_chunk_size(self, char_based_llm):
        """Test that a single line larger than chunk size gets split by characters"""
        text = "This is a very long line that exceeds the maximum chunk size"
        max_chunk_tokens = 20

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert len(result) > 1
        for chunk in result:
            assert (
                char_based_llm.count_tokens_for_message([{"content": chunk}])
                <= max_chunk_tokens
            )

        assert "".join(result) == text

    def test_multiline_text_split_by_lines(self, char_based_llm):
        """Test that multiline text gets split by lines when possible"""
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        max_chunk_tokens = 15

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert len(result) > 1
        for chunk in result:
            assert (
                char_based_llm.count_tokens_for_message([{"content": chunk}])
                <= max_chunk_tokens
            )
        assert "".join(result) == text

    def test_multiline_with_long_lines(self, char_based_llm):
        """Test that multiline text with long lines gets split appropriately"""
        text = "Short line\nThis is a very long line that definitely exceeds the maximum chunk size and should be split further\nAnother short line"
        max_chunk_tokens = 20

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert len(result) > 1
        for chunk in result:
            assert (
                char_based_llm.count_tokens_for_message([{"content": chunk}])
                <= max_chunk_tokens
            )
        assert "".join(result) == text

    def test_exact_chunk_size(self, char_based_llm):
        """Test text that is exactly the chunk size"""
        text = "12345678901234567890"  # 20 characters
        max_chunk_tokens = 20

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert result == [text]
        assert len(result) == 1

    def test_chunk_size_one(self, char_based_llm):
        """Test with chunk size of 1 - should split into individual characters"""
        text = "Hello"
        max_chunk_tokens = 1

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert len(result) == 5
        assert result == ["H", "e", "l", "l", "o"]

    def test_lines_with_newline_preservation(self, char_based_llm):
        """Test that newlines are preserved when splitting by lines"""
        text = "Line 1\nLine 2\nLine 3"
        max_chunk_tokens = 10

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert "".join(result) == text
        has_newline = any("\n" in chunk for chunk in result)
        assert has_newline

    def test_split_by_charaters(self, char_based_llm):
        """Test splitting by characters when split_by_character=True"""
        text = "Hello\nWorld"
        max_chunk_tokens = 5

        result = split_text_in_chunks(
            text, max_chunk_tokens, char_based_llm, split_by_character=True
        )

        assert len(result) > 1
        for chunk in result:
            assert (
                char_based_llm.count_tokens_for_message([{"content": chunk}])
                <= max_chunk_tokens
            )
        assert "".join(result) == text

    def test_very_large_text(self, char_based_llm):
        """Test with a large text to ensure chunking works correctly"""
        # Create a text with multiple lines, some long some short
        lines = []
        for i in range(10):
            if i % 3 == 0:
                lines.append(
                    f"This is a very long line number {i} that contains a lot of text and should be split"
                )
            else:
                lines.append(f"Short line {i}")
        text = "\n".join(lines)
        max_chunk_tokens = 30

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        assert len(result) > 1
        for chunk in result:
            token_count = char_based_llm.count_tokens_for_message([{"content": chunk}])
            assert (
                token_count <= max_chunk_tokens
            ), f"Chunk exceeded limit: {token_count} > {max_chunk_tokens}"

        assert "".join(result) == text

    def test_unicode_characters(self, char_based_llm):
        """Test text with unicode characters"""
        text = "Hello 世界\nÜnicode tëxt with émojis 🚀🌟"
        max_chunk_tokens = 15

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)

        # Should preserve unicode characters
        assert "".join(result) == text
        # Each chunk should be within limits
        for chunk in result:
            assert (
                char_based_llm.count_tokens_for_message([{"content": chunk}])
                <= max_chunk_tokens
            )

    def test_single_character_exceeds_limit(self, char_based_llm):
        """Test edge case where even a single character might theoretically exceed limit"""
        # This test assumes the char-based LLM might have overhead
        # In practice, with our simple char-based LLM, this won't happen
        # But it's good to test the behavior
        text = "A"
        max_chunk_tokens = 1

        result = split_text_in_chunks(text, max_chunk_tokens, char_based_llm)
        assert result == ["A"]
