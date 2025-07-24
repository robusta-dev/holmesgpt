"""GitHub Actions reporting functionality."""

import os
from typing import List, Tuple

from tests.llm.utils.test_results import TestStatus
from tests.llm.utils.braintrust import get_braintrust_url


def handle_github_output(sorted_results: List[dict]) -> None:
    """Generate and write GitHub Actions report files."""
    # Generate markdown report
    markdown, _, total_regressions = generate_markdown_report(sorted_results)

    # Write report files if Braintrust is configured
    braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
    if braintrust_api_key:
        with open("evals_report.txt", "w", encoding="utf-8") as file:
            file.write(markdown)

        # Write regressions file if needed
        if total_regressions > 0:
            with open("regressions.txt", "w", encoding="utf-8") as file:
                file.write(f"{total_regressions}")


def generate_markdown_report(sorted_results: List[dict]) -> Tuple[str, List[dict], int]:
    """Generate markdown report from sorted test results."""
    markdown = "## Results of HolmesGPT evals\n\n"

    # Count results by test type and status
    ask_holmes_total = ask_holmes_passed = ask_holmes_regressions = (
        ask_holmes_mock_failures
    ) = 0
    investigate_total = investigate_passed = investigate_regressions = (
        investigate_mock_failures
    ) = 0
    workload_health_total = workload_health_passed = workload_health_regressions = (
        workload_health_mock_failures
    ) = 0

    for result in sorted_results:
        status = TestStatus(result)

        if result["test_type"] == "ask":
            ask_holmes_total += 1
            if status.passed:
                ask_holmes_passed += 1
            elif status.is_regression:
                ask_holmes_regressions += 1
            elif status.is_mock_failure:
                ask_holmes_mock_failures += 1
        elif result["test_type"] == "investigate":
            investigate_total += 1
            if status.passed:
                investigate_passed += 1
            elif status.is_regression:
                investigate_regressions += 1
            elif status.is_mock_failure:
                investigate_mock_failures += 1
        elif result["test_type"] == "workload_health":
            workload_health_total += 1
            if status.passed:
                workload_health_passed += 1
            elif status.is_regression:
                workload_health_regressions += 1
            elif status.is_mock_failure:
                workload_health_mock_failures += 1

    # Generate summary lines
    if ask_holmes_total > 0:
        markdown += f"- ask_holmes: {ask_holmes_passed}/{ask_holmes_total} test cases were successful, {ask_holmes_regressions} regressions"
        if ask_holmes_mock_failures > 0:
            markdown += f", {ask_holmes_mock_failures} mock failures"
        markdown += "\n"
    if investigate_total > 0:
        markdown += f"- investigate: {investigate_passed}/{investigate_total} test cases were successful, {investigate_regressions} regressions"
        if investigate_mock_failures > 0:
            markdown += f", {investigate_mock_failures} mock failures"
        markdown += "\n"
    if workload_health_total > 0:
        markdown += f"- workload_health: {workload_health_passed}/{workload_health_total} test cases were successful, {workload_health_regressions} regressions"
        if workload_health_mock_failures > 0:
            markdown += f", {workload_health_mock_failures} mock failures"
        markdown += "\n"

    # Generate detailed table
    markdown += "\n\n| Test suite | Test case | Status |\n"
    markdown += "| --- | --- | --- |\n"

    for result in sorted_results:
        test_suite = result["test_type"]
        test_name = f"{result['test_id']}_{result['test_name']}"

        # Add Braintrust link to test name if available
        test_suite_full = (
            "ask_holmes" if result["test_type"] == "ask" else "investigate"
        )
        braintrust_url = get_braintrust_url(
            test_suite_full,
            result["test_id"],
            result["test_name"],
            result.get("braintrust_span_id"),
            result.get("braintrust_root_span_id"),
        )
        if braintrust_url:
            test_name = f"[{test_name}]({braintrust_url})"

        status = TestStatus(result)
        markdown += f"| {test_suite} | {test_name} | {status.markdown_symbol} |\n"

    markdown += "\n\n**Legend**\n"
    markdown += "\n- :white_check_mark: the test was successful"
    markdown += (
        "\n- :warning: the test failed but is known to be flaky or known to fail"
    )
    markdown += (
        "\n- :wrench: the test failed due to mock data issues (not a code regression)"
    )
    markdown += "\n- :x: the test failed and should be fixed before merging the PR"

    return (
        markdown,
        sorted_results,
        ask_holmes_regressions + investigate_regressions + workload_health_regressions,
    )
