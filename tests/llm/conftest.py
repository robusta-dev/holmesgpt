# Standard library imports
import glob
import logging
import os
import textwrap
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional

# Third-party imports
import pytest
from litellm import completion
from rich.console import Console
from rich.table import Table

# Local imports
from tests.llm.utils.braintrust import get_experiment_name
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.classifiers import create_llm_client

# Configuration constants
DEBUG_SEPARATOR = "=" * 80

# Global variable to track generated mock files during test session
_session_mock_tracker = None


@pytest.fixture(scope="session")
def mock_generation_config(request):
    """Session-scoped fixture that provides mock generation configuration and tracking."""
    global _session_mock_tracker
    generate_mocks = request.config.getoption("--generate-mocks")
    regenerate_all_mocks = request.config.getoption("--regenerate-all-mocks")

    # --regenerate-all-mocks implies --generate-mocks
    if regenerate_all_mocks:
        generate_mocks = True

    class MockGenerationTracker:
        def __init__(self, generate_mocks_enabled, regenerate_all_enabled):
            self.generate_mocks = generate_mocks_enabled
            self.regenerate_all_mocks = regenerate_all_enabled
            self.generated_files = []
            self.cleared_directories = set()  # Track directories we've cleared

        def track_generated_file(self, file_path, tool_name, test_case):
            """Track a newly generated mock file."""
            self.generated_files.append(
                {"file_path": file_path, "tool_name": tool_name, "test_case": test_case}
            )

        def clear_existing_mocks(self, test_case_folder):
            """Clear existing mock files in a test case folder if in regenerate mode."""
            if not self.regenerate_all_mocks:
                return

            # Only clear each directory once per session
            if test_case_folder in self.cleared_directories:
                return

            # Clear all mock data files (.txt for tools, .json for DAL)
            mock_files = []
            mock_files.extend(
                glob.glob(os.path.join(test_case_folder, "*.txt"))
            )  # Tool mocks
            mock_files.extend(
                glob.glob(os.path.join(test_case_folder, "*.json"))
            )  # DAL mocks

            cleared_files = []

            for file_path in mock_files:
                try:
                    os.remove(file_path)
                    cleared_files.append(os.path.basename(file_path))
                except Exception as e:
                    print(f"Warning: Could not remove {file_path}: {e}")

            if cleared_files:
                test_case_name = os.path.basename(test_case_folder)
                print(
                    f"🧹 Cleared {len(cleared_files)} existing mock files from {test_case_name}"
                )

            self.cleared_directories.add(test_case_folder)

    tracker = MockGenerationTracker(generate_mocks, regenerate_all_mocks)
    _session_mock_tracker = tracker
    return tracker


@dataclass
class TestResult:
    test_id: str
    test_name: str
    expected: str
    actual: str
    pass_fail: str
    tools_called: List[str]
    logs: str
    test_type: str = ""
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    expected_correctness_score: float = 1.0
    actual_correctness_score: float = 0.0
    mock_data_failure: bool = False


def pytest_addoption(parser):
    """Add custom pytest command line options"""
    parser.addoption(
        "--generate-mocks",
        action="store_true",
        default=False,
        help="Generate mock data files during test execution instead of using existing mocks",
    )
    parser.addoption(
        "--regenerate-all-mocks",
        action="store_true",
        default=False,
        help="Regenerate all mock data files, replacing existing ones (implies --generate-mocks)",
    )


def pytest_configure(config):
    """Configure pytest settings"""
    # Suppress noisy LiteLLM logs during testing
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)


@contextmanager
def force_pytest_output(request):
    """Context manager to force output display even when pytest captures stdout"""
    capman = request.config.pluginmanager.getplugin("capturemanager")
    if capman:
        capman.suspend_global_capture(in_=True)
    try:
        yield
    finally:
        if capman:
            capman.resume_global_capture()


def check_llm_api_with_test_call():
    """Check if LLM API is available by creating client and making test call"""
    try:
        client, model = create_llm_client()
        client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "test"}], max_tokens=1
        )
        return True, None
    except Exception as e:
        # Gather environment info for better error message
        azure_base = os.environ.get("AZURE_API_BASE")
        classifier_model = os.environ.get(
            "CLASSIFIER_MODEL", os.environ.get("MODEL", "gpt-4o")
        )

        if azure_base:
            error_msg = f"Tried to use AzureAI (model: {classifier_model}) because AZURE_API_BASE was set - and failed. Check AZURE_API_BASE, AZURE_API_KEY, AZURE_API_VERSION, or unset them to use OpenAI. Exception: {type(e).__name__}: {str(e)}"

        else:
            error_msg = f"Tried to use OpenAI (model: {classifier_model}) Check OPENAI_API_KEY or set AZURE_API_BASE to use Azure AI. Exception: {type(e).__name__}: {str(e)}"

        return False, error_msg


@pytest.fixture(scope="session", autouse=True)
def llm_session_setup(request):
    """Handle LLM test session setup: show warning, check API, and skip if needed"""
    # Don't show messages during collection-only mode
    if request.config.getoption("--collect-only"):
        return

    # Check if LLM marker is being excluded
    markexpr = request.config.getoption("-m", default="")
    if "not llm" in markexpr:
        return  # Don't show warning if explicitly excluding LLM tests

    # session.items contains the final filtered list of tests that will actually run
    session = request.session
    llm_tests = [item for item in session.items if item.get_closest_marker("llm")]

    if llm_tests:
        # Check API connectivity and show appropriate message
        api_available, error_msg = check_llm_api_with_test_call()

        if api_available:
            with force_pytest_output(request):
                print("\n" + "=" * 70)
                print(f"⚠️  WARNING: About to run {len(llm_tests)} LLM evaluation tests")
                print(
                    "These tests use AI models and may take 10-30+ minutes when all evals run."
                )
                print()
                print("To see all available evals:")
                print(
                    "  poetry run pytest -m llm --collect-only -q --no-cov --disable-warnings"
                )
                print()
                print("To run just one eval for faster execution:")
                print("  poetry run pytest --no-cov -k 01_how_many_pods")
                print()
                print("Skip all LLM tests with: poetry run pytest -m 'not llm'")
                print()

                # Check if Braintrust is enabled
                braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
                if braintrust_api_key:
                    print(
                        "✓ Braintrust is enabled - traces and results will be available at braintrust.dev"
                    )
                else:
                    print(
                        "NOTE: Braintrust is disabled. To see LLM traces and results in Braintrust,"
                    )
                    print(
                        "set BRAINTRUST_API_KEY environment variable with a key from https://braintrust.dev"
                    )
                print("=" * 70 + "\n")
        else:
            with force_pytest_output(request):
                print("\n" + "=" * 70)
                print(f"ℹ️  INFO: {len(llm_tests)} LLM evaluation tests will be skipped")
                print()
                print(f"  Reason: {error_msg}")
                print()
                print("To see all available evals:")
                print(
                    "  poetry run pytest -m llm --collect-only -q --no-cov --disable-warnings"
                )
                print()
                print("To run a specific eval:")
                print("  poetry run pytest --no-cov -k 01_how_many_pods")
                print("=" * 70 + "\n")

            # Skip all LLM tests if API is not available
            pytest.skip(error_msg)

    return


@pytest.fixture(autouse=True)
def braintrust_eval_link(request):
    """Automatically print Braintrust eval link after each LLM test if Braintrust is enabled."""
    yield  # Run the test

    # Only run for LLM tests and if Braintrust is enabled
    if not request.node.get_closest_marker("llm"):
        return

    braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not braintrust_api_key:
        return

    # Extract test suite from test path
    test_suite = None
    test_path = str(request.node.fspath)
    if "ask_holmes" in test_path:
        test_suite = "ask_holmes"
    elif "investigate" in test_path:
        test_suite = "investigate"
    else:
        return  # Unknown test suite

    # Get experiment name and test case ID
    experiment_name = get_experiment_name(test_suite)
    test_case_id = request.node.name

    # Construct Braintrust URL for this specific test
    braintrust_org = os.environ.get("BRAINTRUST_ORG", "robustadev")
    braintrust_url = f"https://www.braintrust.dev/app/{braintrust_org}/p/{PROJECT}/experiments/{experiment_name}?r=&s=&c={test_case_id}"

    with force_pytest_output(request):
        print(f"\n🔍 View eval result: {braintrust_url}")
        print()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Generate GitHub Actions report and Rich summary table from terminalreporter.stats (xdist compatible)"""
    if not hasattr(terminalreporter, "stats"):
        return

    # Collect and sort test results from terminalreporter.stats
    sorted_results = _collect_test_results_from_stats(terminalreporter)

    if not sorted_results:
        return

    # Handle GitHub/CI output (markdown + file writing)
    _handle_github_output(sorted_results)

    # Handle console/developer output (Rich table + Braintrust links)
    _handle_console_output(sorted_results)

    # Report generated mock files if any
    _report_generated_mocks(config)


def markdown_table(headers, rows):
    """Generate a markdown table from headers and rows."""
    markdown = "| " + " | ".join(headers) + " |\n"
    markdown += "| " + " | ".join(["---" for _ in headers]) + " |\n"
    for row in rows:
        markdown += "| " + " | ".join(str(cell) for cell in row) + " |\n"
    return markdown


def _collect_test_results_from_stats(terminalreporter):
    """Collect and parse test results from terminalreporter.stats."""
    test_results = {}

    for status, reports in terminalreporter.stats.items():
        for report in reports:
            # Only process 'call' phase reports for actual test results
            if getattr(report, "when", None) != "call":
                continue

            # Only process LLM evaluation tests
            nodeid = getattr(report, "nodeid", "")
            if not ("test_ask_holmes" in nodeid or "test_investigate" in nodeid):
                continue

            # Extract test data from user_properties
            user_props = dict(getattr(report, "user_properties", {}))
            if not user_props:  # Skip if no user_properties
                continue

            # Extract test info
            test_id = _extract_test_id_from_nodeid(nodeid)
            test_name = _extract_test_name_from_nodeid(nodeid)
            test_type = "ask" if "test_ask_holmes" in nodeid else "investigate"

            # Check if this is a MockDataError failure
            mock_data_failure = False
            if hasattr(report, "longrepr") and report.longrepr:
                # Check for MockDataError in the exception chain
                longrepr_str = str(report.longrepr)
                if "MockDataError" in longrepr_str:
                    mock_data_failure = True

            # Get test data from user_properties
            expected = user_props.get("expected", "Unknown")
            actual = user_props.get("actual", "Unknown")
            tools_called = user_props.get("tools_called", [])
            expected_correctness_score = float(
                user_props.get("expected_correctness_score", 1.0)
            )
            actual_correctness_score = float(
                user_props.get("actual_correctness_score", 0.0)
            )

            # Store result (use nodeid as key to avoid duplicates)
            test_results[nodeid] = {
                "test_id": test_id,
                "test_name": test_name,
                "test_type": test_type,
                "expected": expected,
                "actual": actual,
                "tools_called": tools_called,
                "expected_correctness_score": expected_correctness_score,
                "actual_correctness_score": actual_correctness_score,
                "status": status,  # passed, failed, error, etc.
                "outcome": getattr(report, "outcome", "unknown"),
                "execution_time": getattr(report, "duration", None),
                "mock_data_failure": mock_data_failure,
            }

    # Sort results by test_type then test_id for consistent ordering
    sorted_results = sorted(
        test_results.values(),
        key=lambda r: (
            r["test_type"],
            int(r["test_id"]) if r["test_id"].isdigit() else 999,
            r["test_name"],
        ),
    )

    return sorted_results


def _get_braintrust_url(result):
    """Generate Braintrust URL for a test result.

    Args:
        result: Test result dictionary

    Returns:
        Braintrust URL string, or None if Braintrust is not configured
    """
    braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not braintrust_api_key:
        return None

    test_suite = "ask_holmes" if result["test_type"] == "ask" else "investigate"
    experiment_name = get_experiment_name(test_suite)
    test_case_id = f"test_{test_suite}[{result['test_id']}_{result['test_name']}]"

    braintrust_org = os.environ.get("BRAINTRUST_ORG", "robustadev")
    return (
        f"https://www.braintrust.dev/app/{braintrust_org}/p/{PROJECT}/"
        f"experiments/{experiment_name}?r=&s=&c={test_case_id}"
    )


def _generate_markdown_report(sorted_results):
    """Generate markdown report from sorted test results."""
    markdown = "## Results of HolmesGPT evals\n\n"

    # Count results by test type and status using proper regression logic
    ask_holmes_total = ask_holmes_passed = ask_holmes_regressions = 0
    investigate_total = investigate_passed = investigate_regressions = 0

    for result in sorted_results:
        actual_score = int(result["actual_correctness_score"])
        expected_score = int(result["expected_correctness_score"])
        is_mock_data_failure = result.get("mock_data_failure", False)

        if result["test_type"] == "ask":
            ask_holmes_total += 1
            if actual_score == 1:
                ask_holmes_passed += 1
            elif actual_score == 0 and expected_score == 0:
                # Known failure, not a regression
                pass
            elif is_mock_data_failure:
                # Mock data issue, not a regression
                pass
            else:
                ask_holmes_regressions += 1
        elif result["test_type"] == "investigate":
            investigate_total += 1
            if actual_score == 1:
                investigate_passed += 1
            elif actual_score == 0 and expected_score == 0:
                # Known failure, not a regression
                pass
            elif is_mock_data_failure:
                # Mock data issue, not a regression
                pass
            else:
                investigate_regressions += 1

    # Generate summary lines
    if ask_holmes_total > 0:
        markdown += f"- ask_holmes: {ask_holmes_passed}/{ask_holmes_total} test cases were successful, {ask_holmes_regressions} regressions\n"
    if investigate_total > 0:
        markdown += f"- investigate: {investigate_passed}/{investigate_total} test cases were successful, {investigate_regressions} regressions\n"

    # Generate detailed table
    markdown += "\n\n| Test suite | Test case | Status |\n"
    markdown += "| --- | --- | --- |\n"

    for result in sorted_results:
        test_suite = result["test_type"]
        test_name = f"{result['test_id']}: {result['test_name']}"

        # Add Braintrust link to test name if available
        braintrust_url = _get_braintrust_url(result)
        if braintrust_url:
            test_name = f"[{test_name}]({braintrust_url})"

        actual_score = int(result["actual_correctness_score"])
        expected_score = int(result["expected_correctness_score"])

        if result.get("mock_data_failure", False):
            status = ":wrench:"  # Mock data failure
        elif actual_score == 1:
            status = ":white_check_mark:"
        elif actual_score == 0 and expected_score == 0:
            status = ":warning:"  # Known failure
        else:
            status = ":x:"  # Regression

        markdown += f"| {test_suite} | {test_name} | {status} |\n"

    markdown += "\n\n**Legend**\n"
    markdown += "\n- :white_check_mark: the test was successful"
    markdown += (
        "\n- :warning: the test failed but is known to be flaky or known to fail"
    )
    markdown += (
        "\n- :wrench: the test failed due to mock data issues (not a code regression)"
    )
    markdown += "\n- :x: the test failed and should be fixed before merging the PR"

    return markdown, sorted_results, ask_holmes_regressions + investigate_regressions


def _handle_github_output(sorted_results):
    """Generate and write GitHub Actions report files."""
    # Generate markdown report
    markdown, _, total_regressions = _generate_markdown_report(sorted_results)

    # Write report files if Braintrust is configured
    braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
    if braintrust_api_key:
        with open("evals_report.txt", "w", encoding="utf-8") as file:
            file.write(markdown)

        # Write regressions file if needed
        if total_regressions > 0:
            with open("regressions.txt", "w", encoding="utf-8") as file:
                file.write(f"{total_regressions}")


def _extract_test_id_from_nodeid(nodeid: str) -> str:
    """Extract test ID from pytest nodeid.

    Args:
        nodeid: Pytest node ID like 'test_ask_holmes[01_how_many_pods]'

    Returns:
        Test ID like '01', or 'unknown' if not found
    """
    if "[" in nodeid and "]" in nodeid:
        test_case = nodeid.split("[")[1].split("]")[0]
        # Extract number from start of test case name
        return test_case.split("_")[0] if "_" in test_case else test_case
    return "unknown"


def _extract_test_name_from_nodeid(nodeid: str) -> str:
    """Extract readable test name from pytest nodeid.

    Args:
        nodeid: Pytest node ID like 'test_ask_holmes[01_how_many_pods]'

    Returns:
        Test name like 'how_many_pods'
    """
    try:
        if "[" in nodeid and "]" in nodeid:
            test_case = nodeid.split("[")[1].split("]")[0]
            # Remove number prefix and convert underscores to spaces
            parts = test_case.split("_")[1:] if "_" in test_case else [test_case]
            return "_".join(parts)
    except (IndexError, AttributeError):
        pass
    return nodeid.split("::")[-1] if "::" in nodeid else nodeid


def _handle_console_output(sorted_results):
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

    # Add columns with specific widths
    table.add_column("Test", style="cyan", width=25)
    table.add_column("Status", justify="center", width=4)
    table.add_column("Time", justify="right", width=6)
    table.add_column("Expected", style="green", width=35)
    table.add_column("Actual", style="yellow", width=35)
    table.add_column("Analysis", style="red", width=40)

    # Add rows to table
    for result in sorted_results:
        # Determine pass/fail status
        actual_score = int(result["actual_correctness_score"])
        pass_fail = "✅ PASS" if actual_score == 1 else "❌ FAIL"

        # Create TestResult object for analysis function
        test_result = TestResult(
            test_id=result["test_id"],
            test_name=result["test_name"],
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
            "\n".join(textwrap.wrap(result["expected"], width=33))
            if result["expected"]
            else ""
        )
        actual_wrapped = (
            "\n".join(textwrap.wrap(result["actual"], width=33))
            if result["actual"]
            else ""
        )

        # Combine test ID and name
        combined_test_name = (
            f"{result['test_id']}_{result['test_name']} ({result['test_type']})"
        )
        # Wrap test name to fit column
        test_name_wrapped = "\n".join(textwrap.wrap(combined_test_name, width=23))

        # Convert pass/fail to check/x status with colors
        if result.get("mock_data_failure", False):
            status = "[yellow]🔧[/yellow]"  # Mock data failure
        elif "PASS" in pass_fail:
            status = "[green]✓[/green]"
        else:
            status = "[red]✗[/red]"

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
            status,
            time_str,
            expected_wrapped,
            actual_wrapped,
            analysis,
        )

    console.print(table)

    # Print Braintrust links if enabled
    if os.environ.get("BRAINTRUST_API_KEY"):
        print("🔍 BRAINTRUST EVAL LINKS:")
        for result in sorted_results:
            braintrust_url = _get_braintrust_url(result)
            if braintrust_url:
                print(
                    f"* {result['test_id']}_{result['test_name']} "
                    f"({result['test_type']}) - {braintrust_url}"
                )
        print(DEBUG_SEPARATOR)


def _get_analysis_for_result(result):
    """Get analysis text for a test result, with proper text wrapping."""
    if "PASS" in result.pass_fail:
        return ""

    try:
        analysis = _get_llm_analysis(result)
        # Wrap analysis text for table readability
        return "\n".join(textwrap.wrap(analysis, width=38))
    except Exception as e:
        return f"Analysis failed: {str(e)}"


def _get_llm_analysis(result: TestResult) -> str:
    """Get LLM analysis of test failure using GPT-4o.

    Args:
        result: TestResult object containing test details

    Returns:
        Analysis text explaining why the test failed
    """
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
          To fix: Run with RUN_LIVE=true, or use --generate-mocks (may cause inconsistent data), or use --regenerate-all-mocks (ensures consistency)
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


def _report_generated_mocks(config):
    """Report generated mock files and check for potential conflicts."""
    global _session_mock_tracker

    if not config.getoption("--generate-mocks") and not config.getoption(
        "--regenerate-all-mocks"
    ):
        return

    regenerate_mode = config.getoption("--regenerate-all-mocks")

    print("\n" + "=" * 80)
    if regenerate_mode:
        print("🔄 MOCK REGENERATION SUMMARY")
    else:
        print("🔧 MOCK GENERATION SUMMARY")
    print("=" * 80)

    if not _session_mock_tracker or not _session_mock_tracker.generated_files:
        if regenerate_mode:
            print("✅ Mock regeneration was enabled but no new mock files were created")
        else:
            print("✅ Mock generation was enabled but no new mock files were created")
        print("=" * 80)
        return

    generated_files = _session_mock_tracker.generated_files
    cleared_dirs = (
        len(_session_mock_tracker.cleared_directories) if _session_mock_tracker else 0
    )

    if regenerate_mode:
        print(f"🧹 Cleared existing mocks from {cleared_dirs} test directories")
        print(f"✅ Regenerated {len(generated_files)} mock files:")
    else:
        print(f"✅ Generated {len(generated_files)} mock files:")
    print()

    # Group by test case for better readability
    by_test_case = {}
    for file_info in generated_files:
        test_case = file_info["test_case"]
        if test_case not in by_test_case:
            by_test_case[test_case] = []
        by_test_case[test_case].append(file_info)

    for test_case, files in by_test_case.items():
        print(f"📁 {test_case}:")
        for file_info in files:
            print(f"   - {file_info['tool_name']}: {file_info['file_path']}")
        print()

    # Check for potential conflicts (skip if we regenerated everything)
    if not regenerate_mode:
        _check_mock_conflicts(generated_files)
    else:
        print("🔍 CONFLICT DETECTION:")
        print("   ✅ No conflicts expected - all mocks were regenerated fresh")
        print()

    print("📋 REVIEW CHECKLIST:")
    print("   □ Review generated mock files before committing")
    print("   □ Ensure mock data represents realistic scenarios")
    print("   □ Check that timestamps/IDs are consistent across related mocks")
    if regenerate_mode:
        print("   □ All mocks now represent the same system state")
    else:
        print("   □ Remove or update conflicting older mock files if needed")
    print("=" * 80)


def _check_mock_conflicts(generated_files):
    """Check for potential mock data conflicts and warn the user."""

    print("🔍 CONFLICT DETECTION:")

    # Check each directory for existing mock files that weren't just generated
    conflicts_found = False

    for file_info in generated_files:
        test_dir = os.path.dirname(file_info["file_path"])
        if not os.path.exists(test_dir):
            continue

        # Look for other .txt files in the same directory
        existing_mocks = []
        for filename in os.listdir(test_dir):
            if filename.endswith(".txt"):
                file_path = os.path.join(test_dir, filename)
                # Check if this file was NOT just generated (more than 5 minutes old)
                if os.path.getmtime(file_path) < time.time() - 300:  # 5 minutes ago
                    existing_mocks.append(filename)

        if existing_mocks:
            conflicts_found = True
            test_case = file_info["test_case"]
            print(f"   ⚠️  {test_case}: Found {len(existing_mocks)} existing mock files")
            print(f"      New: {os.path.basename(file_info['file_path'])}")
            print(
                f"      Existing: {', '.join(existing_mocks[:3])}{'...' if len(existing_mocks) > 3 else ''}"
            )

    if conflicts_found:
        print()
        print("   🚨 POTENTIAL MOCK DATA CONFLICTS DETECTED!")
        print("   - Generated mocks may represent different system states")
        print("   - Consider regenerating ALL mocks to ensure consistency")
        print("   - Or carefully review timestamps and data coherence")
    else:
        print("   ✅ No obvious conflicts detected")

    print()
