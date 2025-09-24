from holmes.core.llm import LLM
from holmes.core.models import format_tool_result_data
from holmes.core.tools import StructuredToolResult


def count_tool_response_tokens(
    llm: LLM, structured_tool_result: StructuredToolResult
) -> int:
    message = {
        "role": "tool",
        "content": format_tool_result_data(structured_tool_result),
    }
    return llm.count_tokens_for_message([message])
