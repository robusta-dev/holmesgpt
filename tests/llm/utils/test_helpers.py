"""Test helper functions for enhanced output formatting."""

import textwrap
from typing import List, Any


def truncate_output(data: str, max_lines: int = 10, label: str = "lines") -> str:
    """Truncate output to max_lines for readability."""
    lines = data.split("\n")
    if len(lines) > max_lines:
        preview_lines = lines[:max_lines]
        remaining = len(lines) - max_lines
        preview_lines.append(f"... [TRUNCATED: {remaining} more {label} not shown]")
        return "\n".join(preview_lines)
    return data


# Backward compatibility alias
_truncate_tool_output = truncate_output


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


def print_tool_calls_summary(tool_calls: List[Any]) -> None:
    """Print summary of tool calls."""
    if tool_calls:
        print(f"\n🔧 TOOLS CALLED ({len(tool_calls)}):")
        for i, tc in enumerate(tool_calls, 1):
            print(f"   {i}. {tc.description}")
    else:
        print("\n🔧 TOOLS CALLED: None")


def print_expected_output(expected: List[str]) -> None:
    """Print expected output in formatted way."""
    print("\n📝 EXPECTED OUTPUT:")
    for exp in expected:
        print(f"   - {exp}")


def print_correctness_evaluation(correctness_eval: Any) -> None:
    """Print correctness evaluation results."""
    print("\n⚖️ CORRECTNESS EVALUATION:")
    print(f"   Score: {correctness_eval.score}")
    print("   Rationale: ")
    rationale = correctness_eval.metadata.get("rationale", "")
    for line in rationale.split("\n"):
        if line.strip():
            print(f"      {line}")


def log_tool_calls_to_spans(tool_calls: List[Any], parent_span: Any) -> None:
    """Log tool calls to Braintrust spans for traceability."""
    if not tool_calls or not parent_span:
        return

    for tc in tool_calls:
        with parent_span.start_span(name=tc.tool_name, type="tool") as tool_span:
            tool_span.log(
                input={"description": tc.description},
                output={
                    "data": tc.result.data
                    if hasattr(tc.result, "data")
                    else str(tc.result)
                },
            )
