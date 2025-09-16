import sentry_sdk
from holmes.core.models import ToolCallResult, TruncationMetadata


def capture_tool_truncations(truncations: list[TruncationMetadata]):
    for truncation in truncations:
        _capture_tool_truncation(truncation)


def _capture_tool_truncation(truncation: TruncationMetadata):
    sentry_sdk.capture_message(
        f"Tool {truncation.tool_name} was truncated",
        level="warning",
        tags={
            "tool_name": truncation.tool_name,
            "tool_original_token_count": truncation.original_token_count,
            "tool_new_token_count": truncation.end_index,
        },
    )


def capture_toolcall_contains_too_many_tokens(
    tool_call_result: ToolCallResult, token_count: int, max_allowed_token_count: int
):
    sentry_sdk.capture_message(
        f"Tool call {tool_call_result.tool_name} contains too many tokens",
        level="warning",
        tags={
            "tool_name": tool_call_result.tool_name,
            "tool_original_token_count": token_count,
            "tool_max_allowed_token_count": max_allowed_token_count,
            "tool_description": tool_call_result.description,
        },
    )


def capture_structured_output_incorrect_tool_call():
    sentry_sdk.capture_message(
        "Structured output incorrect tool call",
        level="warning",
    )
