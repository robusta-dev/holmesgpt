import logging
from math import ceil
from typing import Optional
from holmes.common.env_vars import (
    ENABLE_CONVERSATION_HISTORY_COMPACTION,
    MAX_NUMBER_OF_LLM_SUBCALLS_IN_TOOL_OUTPUT_SUMMARIZATION,
)
from holmes.core.llm import LLM
from holmes.core.models import ToolCallResult
from holmes.core.tools_utils.tool_context_window_limiter import is_tool_call_too_big
from holmes.plugins.prompts import load_and_render_prompt
from litellm.types.utils import ModelResponse

TOKENS_RESERVED_FOR_SUMMARIZATION_PROMPT = 500


def strip_system_prompt(
    conversation_history: list[dict],
) -> tuple[list[dict], Optional[dict]]:
    first_message = conversation_history[0]
    if first_message and first_message.get("role") == "system":
        return conversation_history[1:], first_message
    return conversation_history[:], None  # TODO: return same object instead of a copy?


def compact_conversation_history(
    original_conversation_history: list[dict], llm: LLM
) -> list[dict]:
    if not ENABLE_CONVERSATION_HISTORY_COMPACTION:
        return original_conversation_history

    conversation_history, system_prompt_message = strip_system_prompt(
        original_conversation_history
    )
    compaction_instructions = load_and_render_prompt(
        prompt="builtin://conversation_history_compaction.jinja2", context={}
    )
    conversation_history.append({"role": "user", "content": compaction_instructions})

    response: ModelResponse = llm.completion(conversation_history)  # type: ignore
    response_message = None
    if (
        response
        and response.choices
        and response.choices[0]
        and response.choices[0].message
    ):  # type:ignore
        response_message = response.choices[0].message  # type:ignore
    else:
        logging.error(
            "Failed to compact conversation history. Unexpected LLM's response for compaction"
        )
        return conversation_history

    compacted_conversation_history: list[dict] = []
    if system_prompt_message:
        compacted_conversation_history.append(system_prompt_message)
    compacted_conversation_history.append(
        response_message.model_dump(
            exclude_defaults=True, exclude_unset=True, exclude_none=True
        )
    )
    compacted_conversation_history.append(
        {
            "role": "system",
            "content": "The conversation history has been compacted to preserve available space in the context window. Continue.",
        }
    )
    return compacted_conversation_history


def split_text_in_chunks(
    text: str, max_chunk_tokens: int, llm: LLM, split_by_character: bool = False
) -> list[str]:
    text_tokens = llm.count_tokens_for_message([{"content": text}])
    if text_tokens <= max_chunk_tokens:
        return [text]

    chunk_count = ceil(text_tokens / max_chunk_tokens)
    elements: list[str] = []
    if split_by_character:
        elements = list(text)
    else:
        elements = text.splitlines(keepends=True)

    chunks = []
    max_chunk_size = max(len(elements) // chunk_count, 1)

    while len(elements) > 0:
        chunk_size = min(
            len(elements), max_chunk_size
        )  # ensure the count does not exceeds the number of elements
        chunk_elements = elements[:chunk_size]
        del elements[:chunk_size]
        chunk = "".join(chunk_elements)
        chunk_tokens = llm.count_tokens_for_message([{"content": chunk}])
        if chunk_tokens > max_chunk_tokens:
            # Happens when splitting by line is not working/not granular enough. Fall back on chunking the test by character
            sub_chunks = split_text_in_chunks(
                text=chunk,
                max_chunk_tokens=max_chunk_tokens,
                llm=llm,
                split_by_character=True,
            )
            chunks.extend(sub_chunks)
        else:
            chunks.append(chunk)

    return chunks


def summarize_tool_output(
    tool_result: ToolCallResult, fast_llm: LLM, original_user_prompt: str, tasks: str
) -> ToolCallResult:
    if MAX_NUMBER_OF_LLM_SUBCALLS_IN_TOOL_OUTPUT_SUMMARIZATION < 1:
        return tool_result

    tool_call_result_is_too_big, tool_call_metadata = is_tool_call_too_big(
        tool_call_result=tool_result, llm=fast_llm
    )
    if not tool_call_result_is_too_big or not tool_call_metadata:
        return tool_result

    max_input_tokens = (
        fast_llm.get_context_window_size() - fast_llm.get_maximum_output_token()
    )
    max_chunk_tokens = max_input_tokens - TOKENS_RESERVED_FOR_SUMMARIZATION_PROMPT
    chunks = split_text_in_chunks(
        text=tool_result.result.get_stringified_data(),
        max_chunk_tokens=max_chunk_tokens,
        llm=fast_llm,
    )
    if (
        len(chunks) > 1 and True
    ):  # len(chunks) <= MAX_NUMBER_OF_LLM_SUBCALLS_IN_TOOL_OUTPUT_SUMMARIZATION:
        iterative_summary: str = ""
        for idx, chunk in enumerate(chunks):
            system_prompt = load_and_render_prompt(
                prompt="builtin://tool_output_summarization_system_prompt.jinja2",
                context={
                    "original_user_prompt": original_user_prompt,
                    "tasks": tasks,
                    "tool_call_summary": iterative_summary,
                },
            )
            user_prompt = load_and_render_prompt(
                prompt="builtin://tool_output_summarization_user_prompt.jinja2",
                context={
                    "chunk_data": chunk,
                    "chunk_id": idx + 1,
                    "total_chunks": len(chunks),
                },
            )

            response: ModelResponse = fast_llm.completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )  # type: ignore

            if (
                response
                and response.choices
                and response.choices[0]
                and response.choices[0].message
                and response.choices[0].message.content
            ):  # type:ignore
                iterative_summary = response.choices[0].message.content  # type:ignore
            else:
                logging.error(
                    "Failed to summarize tool output. Unexpected LLM's response."
                )
                return tool_result

        if iterative_summary:
            llm_data = "The raw data for this tool result was too big. It has been summarized:\n"
            llm_data += iterative_summary
            tool_result.result.data = llm_data
        else:
            return tool_result
    elif len(chunks) > MAX_NUMBER_OF_LLM_SUBCALLS_IN_TOOL_OUTPUT_SUMMARIZATION:
        logging.info(
            f"Tool call is too big to be summarized. {len(chunks)} LLM calls would be needed to summarize this tool result but max is {TOKENS_RESERVED_FOR_SUMMARIZATION_PROMPT}. Increase the env var TOKENS_RESERVED_FOR_SUMMARIZATION_PROMPT to solve this issue."
        )

    return tool_result
