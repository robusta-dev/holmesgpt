from typing import Optional
from holmes.common.env_vars import (
    TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT,
    TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_TOKENS,
)
from holmes.core.llm import LLM
from holmes.core.tools import StructuredToolResultStatus
from holmes.core.models import ToolCallResult
from holmes.utils import sentry_helper


def get_pct_token_count(percent_of_total_context_window: float, llm: LLM) -> int:
    context_window_size = llm.get_context_window_size()

    if 0 < percent_of_total_context_window and percent_of_total_context_window <= 100:
        return int(context_window_size * percent_of_total_context_window // 100)
    else:
        return context_window_size


def get_max_token_count_for_single_tool(llm: LLM) -> int:
    return min(
        TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_TOKENS,
        get_pct_token_count(
            percent_of_total_context_window=TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT,
            llm=llm,
        ),
    )


def prevent_overly_big_tool_response(tool_call_result: ToolCallResult, llm: LLM):
    max_tokens_allowed = get_max_token_count_for_single_tool(llm)

    message = tool_call_result.as_tool_call_message()

    tokens = llm.count_tokens(messages=[message])
    messages_token = tokens.total_tokens

    if messages_token > max_tokens_allowed:
        relative_pct = ((messages_token - max_tokens_allowed) / messages_token) * 100

        error_message: Optional[str] = (
            f"The tool call result is too large to return: {messages_token} tokens.\nThe maximum allowed tokens is {max_tokens_allowed} which is {format(relative_pct, '.1f')}% smaller.\nInstructions for the LLM: try to repeat the query but proactively narrow down the result so that the tool answer fits within the allowed number of tokens."
        )

        if tool_call_result.result.status == StructuredToolResultStatus.NO_DATA:
            error_message = None
            # tool_call_result.result.data is set to None below which is expected to fix the issue
        elif tool_call_result.result.status == StructuredToolResultStatus.ERROR:
            original_error = (
                tool_call_result.result.error
                or tool_call_result.result.data
                or "Unknown error"
            )
            truncated_error = str(original_error)[:100]
            error_message = f"The tool call returned an error it is too large to return\nThe following original error is truncated:\n{truncated_error}"

        tool_call_result.result.status = StructuredToolResultStatus.ERROR
        tool_call_result.result.data = None
        tool_call_result.result.error = error_message

        sentry_helper.capture_toolcall_contains_too_many_tokens(
            tool_call_result, messages_token, max_tokens_allowed
        )
