"""Terminal reporting functionality for test results."""

import textwrap
from typing import List, Dict, Optional, Any
from collections import defaultdict

from rich.console import Console
from rich.table import Table

from tests.llm.utils.test_results import TestStatus, TestResult


def _calculate_p90(times: List[float]) -> float:
    """Calculate the 90th percentile of a list of times.

    Args:
        times: List of execution times

    Returns:
        P90 time value, or 0 if times is empty
    """
    if not times:
        return 0

    sorted_times = sorted(times)
    p90_index = int(len(sorted_times) * 0.9)
    # Handle edge case for small sample sizes
    if p90_index >= len(sorted_times):
        p90_index = len(sorted_times) - 1
    return sorted_times[p90_index]


def _calculate_valid_runs(results: List[dict]) -> int:
    """Calculate the number of valid test runs (excluding skipped and setup failures).

    Args:
        results: List of test results

    Returns:
        Number of valid runs
    """
    setup_failures = sum(1 for r in results if r.get("is_setup_failure", False))
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    return len(results) - setup_failures - skipped


def _calculate_pass_percentage(passed: int, valid_runs: int) -> float:
    """Calculate pass percentage from passed count and valid runs.

    Args:
        passed: Number of passed tests
        valid_runs: Number of valid test runs

    Returns:
        Pass percentage (0-100)
    """
    if valid_runs > 0:
        return (passed / valid_runs) * 100
    return 0


def _get_failure_indicators(
    mock_failures: int, setup_failures: int, runs: Optional[int] = None
) -> str:
    """Get emoji indicators for failure types.

    Args:
        mock_failures: Number of mock data failures
        setup_failures: Number of setup failures
        runs: Total number of runs (optional, for partial setup failure detection)

    Returns:
        String with emoji indicators (e.g., " 📦" or " 🔧")
    """
    indicators = ""
    if mock_failures > 0:
        indicators = " 📦"
    elif setup_failures > 0:
        # Only show setup indicator if it's partial (not all runs failed setup)
        if runs is None or setup_failures < runs:
            indicators = " 🔧"
    return indicators


def _parse_test_name(nodeid: str, remove_iteration: bool = True) -> str:
    """Parse test name from nodeid, optionally removing iteration numbers.

    This function extracts the test case identifier from a pytest nodeid.

    Args:
        nodeid: Full node ID from pytest (e.g., 'test_ask_holmes[01_how_many_pods0]')
        remove_iteration: Whether to remove iteration numbers

    Returns:
        Parsed test name (e.g., '01_how_many_pods')
    """
    if "[" in nodeid and "]" in nodeid:
        # Extract the parametrized part between brackets
        test_case = nodeid.split("[")[1].split("]")[0]

        # Remove trailing iteration numbers if requested
        if remove_iteration and test_case:
            # Remove trailing digits (iteration numbers added by pytest)
            # Iteration numbers are appended directly to the end without separator
            while test_case and test_case[-1].isdigit():
                test_case = test_case[:-1]

        return test_case
    else:
        # No parameters, use the test function name
        return nodeid.split("::")[-1] if "::" in nodeid else nodeid


def handle_console_output(sorted_results: List[dict], terminalreporter=None) -> None:
    """Display Rich table and Braintrust links for developers."""
    if not sorted_results:
        return

    # Group results by test name to calculate P90
    test_time_groups = defaultdict(list)
    for result in sorted_results:
        test_key = result.get("nodeid", "")
        if result.get("execution_time"):
            test_time_groups[test_key].append(result.get("execution_time"))

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
    table.add_column("Time", justify="right", width=10)
    table.add_column("User Prompt", style="white", width=20)
    table.add_column("Expected", style="green", width=20)
    table.add_column("Actual", style="yellow", width=20)

    # Add rows to table
    for result in sorted_results:
        status = TestStatus(result)

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

        # Use test_case_name and model that are already in the result dict
        test_case_name = result["test_case_name"]
        model = result.get("model", "")
        if model:
            combined_test_name = f"{test_case_name} ({model})"
        else:
            combined_test_name = f"{test_case_name} ({result['test_type']})"
        # Wrap test name to fit column
        test_name_wrapped = "\n".join(textwrap.wrap(combined_test_name, width=10))

        # Format execution time with P90 if available
        exec_time = result.get("execution_time")
        if exec_time:
            # Get the test case name to look up all times for this test
            test_case_name = result["test_case_name"]
            # Find all execution times for this specific test case (across all models)
            test_times = []
            for r in sorted_results:
                if r["test_case_name"] == test_case_name and r.get("execution_time"):
                    test_times.append(r["execution_time"])

            # Calculate average time for multiple runs
            if len(test_times) > 1:
                avg_time = sum(test_times) / len(test_times)
                p90 = _calculate_p90(test_times)
                time_str = f"Avg: {avg_time:.1f}s\nP90: {p90:.1f}s"
            else:
                time_str = f"{exec_time:.1f}s"
        else:
            time_str = "N/A"

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
        TEST: {result.test_case_name}
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


def _get_status_emoji(
    pass_pct: float, setup_fail: bool = False, all_skipped: bool = False
) -> str:
    """Get the appropriate emoji based on pass percentage and status.

    Args:
        pass_pct: Pass percentage (0-100)
        setup_fail: Whether all runs were setup failures
        all_skipped: Whether all runs were skipped

    Returns:
        Emoji string representing the status
    """
    if all_skipped:
        return "⏭️"
    if setup_fail:
        return "🔧"
    if pass_pct == 100.0:
        return "✅"
    elif pass_pct == 0.0:
        return "❌"
    else:
        return "⚠️"


def _detect_multiple_models(sorted_results: List[dict]) -> bool:
    """Detect if results contain multiple models.

    Args:
        sorted_results: List of test results

    Returns:
        True if multiple models are present
    """
    models = set()
    for result in sorted_results:
        model = result.get("model", "Unknown")
        models.add(model)
    return len(models) > 1


def _print_model_comparison_table(sorted_results: List[dict], console: Console) -> None:
    """Print a model comparison table when multiple models are detected."""
    if not sorted_results:
        return

    # Group results by test case and model
    test_model_groups: Dict[str, Dict[str, List[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    models = set()

    for result in sorted_results:
        model = result.get("model", "Unknown")
        models.add(model)

        # Use the test_case_name which is already clean
        test_case = result["test_case_name"]

        test_model_groups[test_case][model].append(result)

    # Sort models for consistent column order
    sorted_models = sorted(models)

    # Create comparison table
    comparison_table = Table(
        title="\n📊 MODEL COMPARISON RESULTS",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
        padding=(0, 1),
    )

    # Add columns
    comparison_table.add_column("Test Case", style="bright_blue", width=30)
    for model in sorted_models:
        comparison_table.add_column(model, justify="center", width=22)

    # Process each test case
    model_totals: Dict[str, Dict[str, Any]] = {
        model: {
            "runs": 0,
            "pass": 0,
            "times": [],
            "setup_fail": 0,
            "mock_fail": 0,
            "skip": 0,
        }
        for model in sorted_models
    }

    for test_case in sorted(test_model_groups.keys()):
        row_data = [test_case]

        for model in sorted_models:
            results = test_model_groups[test_case].get(model, [])

            if not results:
                row_data.append("—")
                continue

            # Calculate statistics for this test/model combination
            runs = len(results)
            passed = sum(1 for r in results if TestStatus(r).passed)
            skipped = sum(1 for r in results if r.get("status") == "skipped")
            setup_failures = sum(1 for r in results if r.get("is_setup_failure", False))
            mock_failures = sum(1 for r in results if r.get("mock_data_failure", False))

            # Calculate times
            times = [
                r.get("execution_time", 0) for r in results if r.get("execution_time")
            ]
            avg_time = sum(times) / len(times) if times else 0

            # Update model totals
            model_totals[model]["runs"] += runs
            model_totals[model]["pass"] += passed
            model_totals[model]["times"].extend(times)
            model_totals[model]["setup_fail"] += setup_failures
            model_totals[model]["mock_fail"] += mock_failures
            model_totals[model]["skip"] += skipped

            # Determine display based on status
            if skipped == runs:
                cell_text = "[cyan]Skipped[/cyan]"
            elif setup_failures == runs:
                cell_text = "[magenta]Setup Fail[/magenta]"
            else:
                # Calculate pass percentage from valid runs
                valid_runs = _calculate_valid_runs(results)
                pass_pct = _calculate_pass_percentage(passed, valid_runs)

                # Choose color based on pass percentage
                if pass_pct == 100:
                    color = "green"
                elif pass_pct >= 50:
                    color = "yellow"
                else:
                    color = "red"

                # Format as 3 lines: Score, Pass count, Avg time
                cell_lines = []
                cell_lines.append(f"[{color}]{pass_pct:.0f}%[/{color}]")
                cell_lines.append(f"{passed}/{valid_runs}")
                if avg_time > 0:
                    cell_lines.append(f"Avg: {avg_time:.1f}s")

                cell_text = "\n".join(cell_lines)

            row_data.append(cell_text)

        comparison_table.add_row(*row_data)

    # Add separator
    separator_row = ["─" * 28] + ["─" * 18] * len(sorted_models)
    comparison_table.add_row(*separator_row, style="dim")

    # Add model average row
    average_row = ["Model Average"]
    for model in sorted_models:
        totals = model_totals[model]
        if totals["runs"] > 0:
            # Calculate pass percentage from valid runs
            valid_runs = totals["runs"] - totals["setup_fail"] - totals["skip"]
            pass_pct = _calculate_pass_percentage(totals["pass"], valid_runs)
            if valid_runs > 0:
                # Choose color based on pass percentage
                if pass_pct == 100:
                    color = "bold green"
                elif pass_pct >= 50:
                    color = "bold yellow"
                else:
                    color = "bold red"
                average_row.append(f"[{color}]{pass_pct:.1f}%[/{color}]")
            else:
                average_row.append("—")
        else:
            average_row.append("—")
    comparison_table.add_row(*average_row)

    # Add average time row
    time_row = ["Average Time"]
    for model in sorted_models:
        times = model_totals[model]["times"]
        if times:
            avg_time = sum(times) / len(times)
            time_row.append(f"{avg_time:.1f}s")
        else:
            time_row.append("—")
    comparison_table.add_row(*time_row)

    # Add P90 time row
    p90_row = ["P90 Time"]
    for model in sorted_models:
        times = model_totals[model]["times"]
        if times:
            p90_time = _calculate_p90(times)
            p90_row.append(f"{p90_time:.1f}s")
        else:
            p90_row.append("—")
    comparison_table.add_row(*p90_row)

    console.print(comparison_table)

    # Print summary
    total_tests = len(test_model_groups)
    console.print(
        f"\n[dim]Compared {len(sorted_models)} models across {total_tests} test cases[/dim]"
    )

    # Find best performing model(s)
    best_models = []
    best_pass_pct = 0.0
    for model in sorted_models:
        totals = model_totals[model]
        valid_runs = totals["runs"] - totals["setup_fail"] - totals["skip"]
        pass_pct = _calculate_pass_percentage(totals["pass"], valid_runs)
        if valid_runs > 0:
            if pass_pct > best_pass_pct:
                best_pass_pct = pass_pct
                best_models = [model]
            elif pass_pct == best_pass_pct:
                best_models.append(model)

    if best_models:
        if len(best_models) == 1:
            console.print(
                f"[bold green]Best performing model: {best_models[0]} ({best_pass_pct:.1f}% pass rate)[/bold green]"
            )
        else:
            models_str = ", ".join(best_models)
            console.print(
                f"[bold green]Best performing models: {models_str} ({best_pass_pct:.1f}% pass rate)[/bold green]"
            )


def _print_summary_statistics(sorted_results: List[dict], console: Console) -> None:
    """Print a summary statistics table similar to pytest coverage reports."""
    if not sorted_results:
        return

    # Check if we should use model comparison view
    if _detect_multiple_models(sorted_results):
        _print_model_comparison_table(sorted_results, console)
        return

    # Group results by test name (without iteration number)
    test_groups: Dict[str, List[dict]] = defaultdict(list)

    for result in sorted_results:
        # Use test_case_name from result dict
        base_name = result["test_case_name"]
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
    summary_table.add_column("P90 Time", justify="right", width=10)

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

        # Determine pass percentage display
        all_skipped = all(r.get("status") == "skipped" for r in results)
        all_setup_fail = setup_failures == runs

        # Calculate pass percentage from valid runs
        valid_runs = _calculate_valid_runs(results)
        pass_pct = _calculate_pass_percentage(passed, valid_runs)

        # Calculate average and P90 execution time
        times = [r.get("execution_time", 0) for r in results if r.get("execution_time")]
        avg_time = sum(times) / len(times) if times else 0
        p90_time = _calculate_p90(times)

        # Update totals
        total_runs += runs
        total_pass += passed
        total_fail += other_failures
        total_setup_fail += setup_failures
        total_mock_fail += mock_failures

        # Format pass percentage with emoji
        if all_skipped:
            pass_pct_str = "⏭️ Skipped"
        elif all_setup_fail:
            pass_pct_str = "🔧 Setup Fail"
        else:
            emoji = _get_status_emoji(pass_pct)
            indicators = _get_failure_indicators(mock_failures, setup_failures, runs)
            pass_pct_str = f"{emoji} {pass_pct:.1f}%{indicators}"

        avg_time_str = f"{avg_time:.1f}s" if avg_time > 0 else "N/A"
        p90_time_str = f"{p90_time:.1f}s" if p90_time > 0 else "N/A"

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
            p90_time_str,
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
        "─" * 8,
        style="dim",
    )

    # Add totals row
    total_actual_runs = total_runs
    total_pass_pct = _calculate_pass_percentage(total_pass, total_actual_runs)

    # Format total pass percentage with emoji
    total_emoji = _get_status_emoji(total_pass_pct)
    # For totals, always show indicators if any failures exist
    total_indicators = ""
    if total_mock_fail > 0:
        total_indicators += " 📦"
    if total_setup_fail > 0:
        total_indicators += " 🔧"

    summary_table.add_row(
        "TOTAL",
        str(total_runs),
        str(total_pass),
        str(total_fail),
        str(total_setup_fail),
        str(total_mock_fail),
        f"{total_emoji} {total_pass_pct:.1f}%{total_indicators}",
        "",
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
