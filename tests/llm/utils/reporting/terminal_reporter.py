"""Terminal reporting functionality for test results."""

import textwrap
from typing import List, Dict
from collections import defaultdict

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
    table.add_column("User Prompt", style="white", width=22)
    table.add_column("Expected", style="green", width=22)
    table.add_column("Actual", style="yellow", width=22)

    # Add rows to table
    for result in sorted_results:
        status = TestStatus(result)
        pass_fail = (
            "✅ PASS" if status.passed else "❌ FAIL"
        )  # Still needed for TestResult

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
        user_prompt_wrapped = (
            "\n".join(textwrap.wrap(result["user_prompt"], width=20))
            if result["user_prompt"]
            else ""
        )
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

        # Disabled for now - get analysis for failed tests with openai
        # analysis = _get_analysis_for_result(test_result)

        table.add_row(
            test_name_wrapped,
            status.console_status,
            time_str,
            user_prompt_wrapped,
            expected_wrapped,
            actual_wrapped,
        )

    # Use force_terminal to ensure output is displayed even when captured
    console.print(table)

    # Print summary statistics table
    _print_summary_statistics(sorted_results, console)


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


def _print_summary_statistics(sorted_results: List[dict], console: Console) -> None:
    """Print a summary statistics table similar to pytest coverage reports."""
    if not sorted_results:
        return

    # Group results by test name (without iteration number)
    test_groups: Dict[str, List[dict]] = defaultdict(list)

    for result in sorted_results:
        # Extract test name without iteration number
        nodeid = result.get("nodeid", "")
        # Remove iteration suffix like "0", "1", etc.
        if "[" in nodeid:
            base_name = nodeid.split("[")[1].split("]")[0]
            # Remove trailing numbers
            if base_name and base_name[-1].isdigit():
                base_name = base_name.rstrip("0123456789")
        else:
            base_name = nodeid

        test_groups[base_name].append(result)

    # Create summary table
    summary_table = Table(
        title="\n📊 TEST SUMMARY STATISTICS",
        show_header=True,
        header_style="bold cyan",
        show_lines=False,
        padding=(0, 1),
    )

    # Add columns (removed Skip column, added failure breakdown)
    summary_table.add_column("Test Name", style="bright_blue", width=40)
    summary_table.add_column("Runs", justify="center", width=6)
    summary_table.add_column("Pass", justify="center", style="green", width=6)
    summary_table.add_column("Fail", justify="center", style="red", width=6)
    summary_table.add_column("Setup Fail", justify="center", style="magenta", width=10)
    summary_table.add_column("Mock Fail", justify="center", style="yellow", width=10)
    summary_table.add_column("Pass %", justify="right", width=8)
    summary_table.add_column("Avg Time", justify="right", width=10)

    # Calculate statistics for each test
    total_runs = 0
    total_pass = 0
    total_fail = 0
    total_setup_fail = 0
    total_mock_fail = 0
    total_skip = 0

    for test_name in sorted(test_groups.keys()):
        results = test_groups[test_name]

        # Skip entirely skipped tests
        if all(r.get("status") == "skipped" for r in results):
            total_skip += len(results)
            continue

        runs = len(results)
        passed = sum(1 for r in results if TestStatus(r).passed)

        # Count different failure types
        setup_failures = sum(1 for r in results if r.get("is_setup_failure", False))
        mock_failures = sum(1 for r in results if r.get("mock_data_failure", False))
        other_failures = sum(
            1
            for r in results
            if not TestStatus(r).passed
            and not r.get("mock_data_failure", False)
            and not r.get("is_setup_failure", False)
            and r.get("status") != "skipped"
        )

        # Calculate pass percentage
        if runs > 0:
            pass_pct = (passed / runs) * 100
        else:
            pass_pct = 0

        # Calculate average execution time
        times = [r.get("execution_time", 0) for r in results if r.get("execution_time")]
        avg_time = sum(times) / len(times) if times else 0

        # Update totals
        total_runs += runs
        total_pass += passed
        total_fail += other_failures
        total_setup_fail += setup_failures
        total_mock_fail += mock_failures

        # Format values
        pass_pct_str = f"{pass_pct:.1f}%"
        avg_time_str = f"{avg_time:.1f}s" if avg_time > 0 else "N/A"

        # Add row
        summary_table.add_row(
            test_name,
            str(runs),
            str(passed) if passed > 0 else "-",
            str(other_failures) if other_failures > 0 else "-",
            str(setup_failures) if setup_failures > 0 else "-",
            str(mock_failures) if mock_failures > 0 else "-",
            pass_pct_str,
            avg_time_str,
        )

    # Add separator
    summary_table.add_row(
        "─" * 38,
        "─" * 4,
        "─" * 4,
        "─" * 4,
        "─" * 8,
        "─" * 8,
        "─" * 6,
        "─" * 8,
        style="dim",
    )

    # Add totals row
    total_actual_runs = total_runs
    total_pass_pct = (
        (total_pass / total_actual_runs) * 100 if total_actual_runs > 0 else 0
    )
    summary_table.add_row(
        "TOTAL",
        str(total_runs),
        str(total_pass),
        str(total_fail),
        str(total_setup_fail),
        str(total_mock_fail),
        f"{total_pass_pct:.1f}%",
        "",
        style="bold",
    )

    console.print(summary_table)

    # Print quick summary line with failure breakdown
    if total_fail > 0 or total_setup_fail > 0 or total_mock_fail > 0:
        failure_parts = []
        if total_fail > 0:
            failure_parts.append(f"{total_fail} real failures")
        if total_setup_fail > 0:
            failure_parts.append(f"{total_setup_fail} setup failures")
        if total_mock_fail > 0:
            failure_parts.append(f"{total_mock_fail} mock data failures")

        total_failures = total_fail + total_setup_fail + total_mock_fail
        console.print(
            f"\n[bold red]FAIL[/bold red] {total_failures} out of {total_actual_runs} tests failed ({', '.join(failure_parts)})"
        )
    else:
        console.print(
            f"\n[bold green]SUCCESS[/bold green] All {total_actual_runs} tests passed!"
        )

    # Print skip info if any
    if total_skip > 0:
        console.print(
            f"[dim]Note: {total_skip // max(len(test_groups.get(name, [])) for name in test_groups)} tests were skipped entirely[/dim]"
        )

    # Print iteration info if multiple runs detected
    max_iterations = max(len(results) for results in test_groups.values())
    if max_iterations > 1:
        # TODO this is wrong - in case you run with 1 Iterations it says '2' instead of '1'
        console.print(
            f"[dim]Note: Tests were run with {max_iterations} iterations[/dim]"
        )
