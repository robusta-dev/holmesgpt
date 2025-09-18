from holmes.common.env_vars import TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT
from holmes.core.llm import LLM
from holmes.core.tools import StructuredToolResultStatus
from holmes.core.models import ToolCallResult
from holmes.utils import sentry_helper


def prevent_overly_big_tool_response(tool_call_result: ToolCallResult, llm: LLM):
    if (
        tool_call_result.result.status == StructuredToolResultStatus.SUCCESS
        and 0 < TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT
        and TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT <= 100
    ):
        message = tool_call_result.as_tool_call_message()

        messages_token = llm.count_tokens_for_message(messages=[message])
        context_window_size = llm.get_context_window_size()
        max_tokens_allowed: int = int(
            context_window_size * TOOL_MAX_ALLOCATED_CONTEXT_WINDOW_PCT // 100
        )

        if messages_token > max_tokens_allowed:
            relative_pct = (
                (messages_token - max_tokens_allowed) / messages_token
            ) * 100
            error_message = f"The tool call result is too large to return: {messages_token} tokens.\nThe maximum allowed tokens is {max_tokens_allowed} which is {format(relative_pct, '.1f')}% smaller.\nInstructions for the LLM: try to repeat the query but proactively narrow down the result so that the tool answer fits within the allowed number of tokens."
            tool_call_result.result.status = StructuredToolResultStatus.ERROR
            tool_call_result.result.data = None
            tool_call_result.result.error = error_message

            sentry_helper.capture_toolcall_contains_too_many_tokens(
                tool_call_result, messages_token, max_tokens_allowed
            )
