"""Terminal reporting functionality for test results."""

import textwrap
from typing import List

from rich.console import Console
from rich.table import Table

from tests.llm.utils.test_results import TestStatus, TestResult


def handle_console_output(sorted_results: List[dict], terminalreporter=None) -> None:
    """Display Rich table and Braintrust links for developers."""
    if not sorted_results:
        return

    # Create Rich table
    console = Console()
    table = Table(
        title="🔍 HOLMES TESTS SUMMARY",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
    )

    # Add columns with specific widths (reduced to fit terminal width)
    table.add_column("Test", style="cyan", width=12)
    table.add_column("Status", justify="center", width=13)
    table.add_column("Time", justify="right", width=5)
    table.add_column("Expected", style="green", width=22)
    table.add_column("Actual", style="yellow", width=22)
    table.add_column("Analysis", style="red", width=28)

    # Add rows to table
    for result in sorted_results:
        status = TestStatus(result)
        pass_fail = "✅ PASS" if status.passed else "❌ FAIL"

        # Create TestResult object for analysis function
        test_result = TestResult(
            nodeid=result.get("nodeid", ""),
            expected=result["expected"],
            actual=result["actual"],
            pass_fail=pass_fail,
            tools_called=result["tools_called"],
            logs="",  # We don't have logs in this context
            test_type=result["test_type"],
            error_message=None,
            execution_time=result.get("execution_time"),
            expected_correctness_score=result["expected_correctness_score"],
            actual_correctness_score=result["actual_correctness_score"],
            mock_data_failure=result.get("mock_data_failure", False),
        )

        # Wrap long content for table readability
        expected_wrapped = (
            "\n".join(textwrap.wrap(result["expected"], width=20))
            if result["expected"]
            else ""
        )
        actual_wrapped = (
            "\n".join(textwrap.wrap(result["actual"], width=20))
            if result["actual"]
            else ""
        )

        # Combine test ID and name using TestResult properties
        combined_test_name = (
            f"{test_result.test_id}_{test_result.test_name} ({result['test_type']})"
        )
        # Wrap test name to fit column
        test_name_wrapped = "\n".join(textwrap.wrap(combined_test_name, width=10))

        # Format execution time
        time_str = (
            f"{result.get('execution_time'):.1f}s"
            if result.get("execution_time")
            else "N/A"
        )

        # Get analysis for failed tests
        analysis = _get_analysis_for_result(test_result)

        table.add_row(
            test_name_wrapped,
            status.console_status,
            time_str,
            expected_wrapped,
            actual_wrapped,
            analysis,
        )

    # Use force_terminal to ensure output is displayed even when captured
    console.print(table)


def _get_analysis_for_result(result: TestResult) -> str:
    """Get analysis text for a test result, with proper text wrapping."""
    if "PASS" in result.pass_fail:
        return ""

    try:
        analysis = _get_llm_analysis(result)
        # Wrap analysis text for table readability
        return "\n".join(textwrap.wrap(analysis, width=26))
    except Exception as e:
        return f"Analysis failed: {str(e)}"


def _get_llm_analysis(result: TestResult) -> str:
    """Get LLM analysis of test failure using GPT-4o.

    Args:
        result: TestResult object containing test details

    Returns:
        Analysis text explaining why the test failed
    """
    from litellm import completion

    # Check if this is a MockDataError case and add context
    mock_data_context = ""
    if result.mock_data_failure:
        mock_data_context = "\n\nIMPORTANT CONTEXT: This test failed due to MockDataError - no mock data files were found for the tool calls that the agent tried to make. This is a test infrastructure issue, not a problem with the agent's logic."

    prompt = textwrap.dedent(f"""\
        Analyze this failed eval for an AIOps agent why it failed.
        TEST: {result.test_name}
        EXPECTED: {result.expected}
        ACTUAL: {result.actual}
        TOOLS CALLED: {', '.join(result.tools_called)}
        ERROR: {result.error_message or 'Test assertion failed'}

        LOGS:
        {result.logs if result.logs else 'No logs available'}{mock_data_context}

        Please provide a concise analysis (2-3 sentences) and categorize this as one of:
        - MockDataError - the test failed because mock data files were missing for the tool calls (this is a test infrastructure issue).
          To fix (show bullet points with each option - any are valid solutions so user should see all options):
          - Run with RUN_LIVE=true
          - Use --generate-mocks (may cause inconsistent data)
          - Use --regenerate-all-mocks (ensures consistency)
        - Problem with mock data - the test is failing due to incorrect or incomplete mock data, but the agent itself did the correct queries you would expect it to do
        - Setup issue - the test is failing due to an issue with the test setup, such as missing tools or incorrect before_test/after_test configuration
        - Real failure - the test is failing because the agent did not perform as expected, and this is a real issue that needs to be fixed
        """)

    try:
        response = completion(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Analysis failed: {e}"
