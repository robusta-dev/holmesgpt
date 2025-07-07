# type: ignore
import textwrap
from typing import Optional, Any, List
from braintrust import Span
from braintrust.span_types import SpanTypeAttribute
from pydantic import BaseModel


def log_tool_calls_to_spans(tool_calls: list, eval_span: Optional[Span]) -> None:
    """
    Log tool calls to Braintrust spans for both ask_holmes and investigate tests.

    Args:
        tool_calls: List of tool call objects with tool_name, description, and result
        eval_span: Optional Braintrust span for logging
    """
    if not tool_calls or not eval_span:
        return

    for tool_call in tool_calls:
        # TODO: mock this instead so span start time & end time will be accurate.
        # Also to include calls to llm spans
        with eval_span.start_span(
            name=tool_call.tool_name, type=SpanTypeAttribute.TOOL
        ) as tool_span:
            _log_tool_result_to_span(tool_call, tool_span)


def _log_tool_result_to_span(tool_call: Any, tool_span: Span) -> None:
    """Log a single tool call result to a span, handling different result types."""
    result = tool_call.result

    # Handle BaseModel results (ask_holmes pattern)
    if isinstance(result, BaseModel):
        tool_span.log(
            input=tool_call.description,
            output=result.model_dump_json(indent=2),
            error=getattr(result, "error", None),
        )
    # Handle dict results (investigate pattern)
    elif isinstance(result, dict):
        import json

        tool_span.log(
            input=tool_call.description,
            output=json.dumps(result, indent=2),
            error=result.get("error"),
        )
    # Handle other result types
    else:
        tool_span.log(
            input=tool_call.description,
            output=result,
            error=getattr(result, "error", None),
        )


def print_expected_output(expected: Any) -> None:
    """Print expected output in a consistent format across test files."""
    if not isinstance(expected, list):
        expected = [expected]

    debug_expected = "\n-  ".join(expected)
    print("\n📝 EXPECTED OUTPUT:")
    print(f"-  {debug_expected}")


def print_correctness_evaluation(correctness_eval: Any) -> None:
    """Print correctness evaluation results in a consistent format."""
    print("\n⚖️  CORRECTNESS EVALUATION:")
    print(f"Score: {correctness_eval.score}")
    if correctness_eval.metadata.get("rationale"):
        print(
            f"Rationale: \n{textwrap.indent(correctness_eval.metadata.get('rationale', ''), '  ')}"
        )


def print_tool_calls_summary(tool_calls: List[Any]) -> None:
    """Print a summary of tool calls."""
    if tool_calls:
        tools_called = [tc.description for tc in tool_calls]
        print(f"\n🔧 TOOLS CALLED ({len(tools_called)}):")
        for i, tool in enumerate(tools_called, 1):
            print(f"   {i}. {tool}")
    else:
        print("\n🔧 TOOLS CALLED: None")


def _truncate_tool_output(data: str, max_lines: int = 10) -> str:
    """Truncate tool output to specified number of lines with warning if needed"""
    data_lines = data.split("\n")
    if len(data_lines) > max_lines:
        truncated_data = "\n".join(data_lines[:max_lines])
        truncated_data += (
            f"\n... [TRUNCATED: {len(data_lines) - max_lines} more lines not shown]"
        )
        return truncated_data
    return data


def print_tool_calls_detailed(tool_calls: List[Any]) -> None:
    """Print detailed tool output for debugging (limited to 10 lines per tool)"""
    if tool_calls:
        print("\n🔧 TOOLS CALLED (DETAILED):")
        for tc in tool_calls:
            truncated_data = _truncate_tool_output(tc.result.data)
            print(f"\n<tool description='{tc.description}'>")
            print(textwrap.indent(truncated_data, "  "))
            print("</tool>")
    else:
        print("\n🔧 TOOLS CALLED: None")
