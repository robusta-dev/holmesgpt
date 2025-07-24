import logging
import os
import textwrap
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional

import pytest
from litellm import completion
from rich.console import Console
from rich.table import Table
from pytest_shared_session_scope import (
    shared_session_scope_json,
    SetupToken,
    CleanupToken,
)

from tests.llm.utils.braintrust import get_experiment_name
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.classifiers import create_llm_client
from tests.llm.utils.mock_toolset import MockMode, MockGenerationConfig  # type: ignore[attr-defined]

# Configuration constants
DEBUG_SEPARATOR = "=" * 80
LLM_TEST_TYPES = ["test_ask_holmes", "test_investigate", "test_workload_health"]
MAX_ERROR_LINES = 10
MAX_WORKERS = 30


def is_llm_test(nodeid: str) -> bool:
    """Check if a test nodeid is for an LLM test."""
    return any(
        [
            "test_ask_holmes" in nodeid,
            "test_investigate" in nodeid,
            "test_workload_health" in nodeid,
        ]
    )


# Status determination types
class TestStatus:
    """Encapsulates test status determination logic."""

    def __init__(self, result: dict):
        self.actual_score = int(result.get("actual_correctness_score", 0))
        self.expected_score = int(result.get("expected_correctness_score", 1))
        self.is_mock_failure = result.get("mock_data_failure", False)

    @property
    def passed(self) -> bool:
        return (
            self.actual_score == 1
        )  # TODO: possibly add `and not self.is_mock_failure`

    @property
    def is_regression(self) -> bool:
        if self.passed or self.is_mock_failure:
            return False
        # Known failure (expected to fail)
        if self.actual_score == 0 and self.expected_score == 0:
            return False
        return True

    @property
    def markdown_symbol(self) -> str:
        if self.is_mock_failure:
            return ":wrench:"
        elif self.passed:
            return ":white_check_mark:"
        elif self.actual_score == 0 and self.expected_score == 0:
            return ":warning:"
        else:
            return ":x:"

    @property
    def console_status(self) -> str:
        if self.is_mock_failure:
            return "[yellow]MOCK FAILURE[/yellow]"
        elif self.passed:
            return "[green]PASS[/green]"
        else:
            return "[red]FAIL[/red]"

    @property
    def short_status(self) -> str:
        if self.is_mock_failure:
            return "MOCK FAILURE"
        elif self.passed:
            return "PASS"
        else:
            return "FAIL"


@pytest.fixture(scope="session")
def mock_generation_config(request):
    """Session-scoped fixture that provides mock generation configuration and mode."""
    # Safely get options with defaults in case they're not registered
    generate_mocks = request.config.getoption("--generate-mocks")
    regenerate_all_mocks = request.config.getoption("--regenerate-all-mocks")

    # --regenerate-all-mocks implies --generate-mocks
    if regenerate_all_mocks:
        generate_mocks = True

    # Determine mode based on environment and options
    if os.getenv("RUN_LIVE", "False").lower() in ("true", "1", "t"):
        mode = MockMode.LIVE
    elif generate_mocks:
        mode = MockMode.GENERATE
    else:
        mode = MockMode.MOCK

    return MockGenerationConfig(generate_mocks, regenerate_all_mocks, mode)


# Handles before_test and after_test
# see https://github.com/StefanBRas/pytest-shared-session-scope
@shared_session_scope_json()
def shared_test_infrastructure(request, mock_generation_config: MockGenerationConfig):
    """Shared session-scoped fixture for test infrastructure setup/cleanup coordination"""
    collect_only = request.config.getoption("--collect-only")

    # If we're in collect-only mode or RUN_LIVE is not set, skip setup/cleanup entirely
    if collect_only or mock_generation_config.mode == MockMode.MOCK:
        print(
            f"Skipping shared test infrastructure setup/cleanup (mode: {mock_generation_config.mode}, collect_only: {collect_only})"
        )
        # Must yield twice even when skipping due to ohw pytest-shared-session-scope works
        initial = yield
        cleanup_token = yield {"test_cases_for_cleanup": []}
        return
    print(
        f"Running shared test infrastructure setup/cleanup (mode: {mock_generation_config.mode}, collect_only: {collect_only})"
    )

    # First yield: get initial value (SetupToken.FIRST if first worker, data if subsequent)
    initial = yield

    if initial is SetupToken.FIRST:
        # This is the first worker to run the fixture
        test_cases = _extract_test_cases_needing_setup(request.session)

        # Clear mock directories if --regenerate-all-mocks is set
        cleared_directories = []
        regenerate_all = request.config.getoption("--regenerate-all-mocks")

        if regenerate_all:
            cleared_directories = _clear_mock_directories(request.session)

        # Run setup unless --skip-setup is set
        # Check skip-setup option
        skip_setup = request.config.getoption("--skip-setup")

        if test_cases and not skip_setup:
            _run_test_setup(test_cases)
        elif skip_setup:
            print("\n⏭️  Skipping test setup due to --skip-setup flag")

        data = {
            "test_cases_for_cleanup": [tc.id for tc in test_cases],
            "cleared_mock_directories": cleared_directories,
        }
    else:
        # This is a worker using the fixture after the first worker
        data = initial

    # Actual test runs here when we yield - then we get back a cleanup token from pytest-shared-session-scope
    cleanup_token = yield data

    if cleanup_token is CleanupToken.LAST:
        # This is the last worker to exit - responsible for cleanup
        test_case_ids = data.get("test_cases_for_cleanup", [])

        # Check skip-cleanup option
        skip_cleanup = request.config.getoption("--skip-cleanup")

        if test_case_ids and not skip_cleanup:
            # Reconstruct test cases from IDs
            from tests.llm.utils.test_case_utils import HolmesTestCase  # type: ignore[attr-defined]  # type: ignore[attr-defined]

            cleanup_test_cases = []

            for item in request.session.items:
                if (
                    item.get_closest_marker("llm")
                    and hasattr(item, "callspec")
                    and "test_case" in item.callspec.params
                ):
                    test_case = item.callspec.params["test_case"]
                    if (
                        isinstance(test_case, HolmesTestCase)
                        and test_case.id in test_case_ids
                        and test_case not in cleanup_test_cases
                    ):
                        cleanup_test_cases.append(test_case)

            if cleanup_test_cases:
                _run_test_cleanup(cleanup_test_cases)
        elif skip_cleanup:
            print("\n⏭️  Skipping test cleanup due to --skip-cleanup flag")


@pytest.fixture(scope="session", autouse=True)
def test_infrastructure_coordination(shared_test_infrastructure):
    """Ensure the shared test infrastructure fixture is used (triggers setup/cleanup)"""
    # This fixture just ensures shared_test_infrastructure runs for all sessions
    # All the actual logic is in shared_test_infrastructure
    yield


@dataclass
class TestResult:
    nodeid: str
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

    @property
    def test_id(self) -> str:
        """Extract test ID from pytest nodeid.

        Example: 'test_ask_holmes[01_how_many_pods]' -> '01'
        """
        if "[" in self.nodeid and "]" in self.nodeid:
            test_case = self.nodeid.split("[")[1].split("]")[0]
            # Extract number from start of test case name
            return test_case.split("_")[0] if "_" in test_case else test_case
        return "unknown"

    @property
    def test_name(self) -> str:
        """Extract readable test name from pytest nodeid.

        Example: 'test_ask_holmes[01_how_many_pods]' -> 'how_many_pods'
        """
        try:
            if "[" in self.nodeid and "]" in self.nodeid:
                test_case = self.nodeid.split("[")[1].split("]")[0]
                # Remove number prefix and convert underscores to spaces
                parts = test_case.split("_")[1:] if "_" in test_case else [test_case]
                return "_".join(parts)
        except (IndexError, AttributeError):
            pass
        return self.nodeid.split("::")[-1] if "::" in self.nodeid else self.nodeid


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
def llm_availablity_check(request):
    """Handle LLM test session setup: show warning, check API, and skip if needed"""
    # Don't show messages during collection-only mode
    # Check if we're in collect-only mode
    collect_only = request.config.getoption("--collect-only")

    if collect_only:
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
    test_path = str(request.node.fspath)
    test_suite = None
    for test_type in LLM_TEST_TYPES:
        if test_type.replace("test_", "") in test_path:
            test_suite = test_type.replace("test_", "")
            break

    if not test_suite:
        return  # Unknown test suite

    # Create a temporary TestResult to extract test ID and name
    temp_result = TestResult(
        nodeid=request.node.nodeid,
        expected="",
        actual="",
        pass_fail="",
        tools_called=[],
        logs="",
    )

    # Extract span IDs from user properties
    span_id = None
    root_span_id = None
    if hasattr(request.node, "user_properties"):
        for key, value in request.node.user_properties:
            if key == "braintrust_span_id":
                span_id = value
            elif key == "braintrust_root_span_id":
                root_span_id = value

    # Construct Braintrust URL for this specific test
    # NATAN - this link is correct
    braintrust_url = get_braintrust_url(
        test_suite, temp_result.test_id, temp_result.test_name, span_id, root_span_id
    )

    with force_pytest_output(request):
        print(f"\n🔍 View eval result: {braintrust_url}")
        print()


def _safe_print(terminalreporter, message=""):
    """Safely print to terminal reporter to avoid I/O errors"""
    try:
        terminalreporter.write_line(message)
    except Exception:
        # If write_line fails, try direct write
        try:
            terminalreporter._tw.write(message + "\n")
        except Exception:
            # Last resort - ignore if all writing fails
            pass


def xxxxxpytest_terminal_summary2(terminalreporter, exitstatus, config):
    """Generate GitHub Actions report and Rich summary table from terminalreporter.stats (xdist compatible)"""
    if not hasattr(terminalreporter, "stats"):
        return

    # When using xdist, only the master process should display the summary
    # Check if we're in a worker process
    worker_id = (
        getattr(config, "workerinput", {}).get("workerid", None)
        if hasattr(config, "workerinput")
        else None
    )
    if worker_id is not None:
        # We're in a worker process, don't display summary
        return

    # Collect and sort test results from terminalreporter.stats
    sorted_results, mock_tracking_data = _collect_test_results_from_stats(
        terminalreporter
    )

    if not sorted_results:
        return

    # Handle GitHub/CI output (markdown + file writing)
    _handle_github_output(sorted_results)

    # Handle console/developer output (Rich table + Braintrust links)
    _handle_console_output(sorted_results, terminalreporter)

    # Report mock operation statistics
    _report_mock_operations(config, mock_tracking_data, terminalreporter)


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
    mock_tracking_data = {
        "generated_mocks": [],
        "cleared_directories": set(),
        "mock_failures": [],
    }

    MOCK_ERROR_TYPES = [
        "MockDataError",
        "MockDataNotFoundError",
        "MockDataCorruptedError",
    ]

    for status, reports in terminalreporter.stats.items():
        for report in reports:
            # Only process 'call' phase reports for actual test results
            if getattr(report, "when", None) != "call":
                continue

            # Only process LLM evaluation tests
            nodeid = getattr(report, "nodeid", "")
            if not is_llm_test(nodeid):
                continue

            # Extract test data from user_properties
            user_props = dict(getattr(report, "user_properties", []))
            if not user_props:  # Skip if no user_properties
                continue

            # Collect mock tracking data
            mock_data_failure = user_props.get("mock_data_failure", False)

            if "generated_mock_file" in user_props:
                mock_tracking_data["generated_mocks"].append(
                    user_props["generated_mock_file"]
                )

            if "mocks_cleared" in user_props:
                folder, count = user_props["mocks_cleared"].split(":", 1)
                mock_tracking_data["cleared_directories"].add(folder)

            if "mock_failure" in user_props:
                mock_tracking_data["mock_failures"].append(user_props["mock_failure"])

            # Check for mock errors if not already found
            if not mock_data_failure:
                # Check in longrepr
                if hasattr(report, "longrepr") and report.longrepr:
                    longrepr_str = str(report.longrepr)
                    mock_data_failure = any(
                        error in longrepr_str for error in MOCK_ERROR_TYPES
                    )

                # Check in captured logs
                if not mock_data_failure and hasattr(report, "sections"):
                    for section_name, section_content in report.sections:
                        if "log" in section_name and any(
                            error in section_content for error in MOCK_ERROR_TYPES
                        ):
                            mock_data_failure = True
                            break

            # Extract test type
            if "test_ask_holmes" in nodeid:
                test_type = "ask"
            elif "test_investigate" in nodeid:
                test_type = "investigate"
            elif "test_workload_health" in nodeid:
                test_type = "workload_health"
            else:
                test_type = "unknown"

            # Store result (use nodeid as key to avoid duplicates)
            test_results[nodeid] = {
                "nodeid": nodeid,
                "test_type": test_type,
                "expected": user_props.get("expected", "Unknown"),
                "actual": user_props.get("actual", "Unknown"),
                "tools_called": user_props.get("tools_called", []),
                "expected_correctness_score": float(
                    user_props.get("expected_correctness_score", 1.0)
                ),
                "actual_correctness_score": float(
                    user_props.get("actual_correctness_score", 0.0)
                ),
                "status": status,
                "outcome": getattr(report, "outcome", "unknown"),
                "execution_time": getattr(report, "duration", None),
                "mock_data_failure": mock_data_failure,
                "braintrust_span_id": user_props.get("braintrust_span_id"),
                "braintrust_root_span_id": user_props.get("braintrust_root_span_id"),
            }

    # Create TestResult objects to get test_id and test_name properties
    results_with_ids = []
    for result in test_results.values():
        # Create a temporary TestResult to extract IDs
        temp_result = TestResult(
            nodeid=result["nodeid"],
            expected=result["expected"],
            actual=result["actual"],
            pass_fail="",  # Will be set later
            tools_called=result["tools_called"],
            logs="",  # Will be set later
            test_type=result["test_type"],
            execution_time=result["execution_time"],
            expected_correctness_score=result["expected_correctness_score"],
            actual_correctness_score=result["actual_correctness_score"],
            mock_data_failure=result["mock_data_failure"],
        )

        # Add extracted IDs to the result dict
        result["test_id"] = temp_result.test_id
        result["test_name"] = temp_result.test_name
        results_with_ids.append(result)

    # Sort results by test_type then test_id for consistent ordering
    sorted_results = sorted(
        results_with_ids,
        key=lambda r: (
            r["test_type"],
            int(r["test_id"]) if r["test_id"].isdigit() else 999,
            r["test_name"],
        ),
    )

    return sorted_results, mock_tracking_data


def get_braintrust_url(
    test_suite: str,
    test_id: str,
    test_name: str,
    span_id: Optional[str] = None,
    root_span_id: Optional[str] = None,
) -> Optional[str]:
    """Generate Braintrust URL for a test.

    Args:
        test_suite: Either "ask_holmes" or "investigate"
        test_id: Test ID like "01"
        test_name: Test name like "how_many_pods"

    Returns:
        Braintrust URL string, or None if Braintrust is not configured
    """
    braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not braintrust_api_key:
        return None

    experiment_name = get_experiment_name(test_suite)
    braintrust_org = os.environ.get("BRAINTRUST_ORG", "robustadev")

    # Build URL with available parameters
    url = f"https://www.braintrust.dev/app/{braintrust_org}/p/{PROJECT}/experiments/{experiment_name}?c="

    # Add span IDs if available
    if span_id and root_span_id:
        # Use span_id as r parameter and root_span_id as s parameter
        url += f"&r={span_id}&s={root_span_id}"

    return url


def _generate_markdown_report(sorted_results):
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
        test_name = f"{result['test_id']}: {result['test_name']}"

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


def _handle_console_output(sorted_results, terminalreporter=None):
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


def _get_analysis_for_result(result):
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


def _report_mock_operations(config, mock_tracking_data, terminalreporter=None):
    """Report mock file operations and statistics."""
    # Use default parameter to safely handle missing options
    generate_mocks = False
    regenerate_all_mocks = False

    try:
        generate_mocks = config.getoption("--generate-mocks", default=False)
        regenerate_all_mocks = config.getoption("--regenerate-all-mocks", default=False)
    except (AttributeError, ValueError):
        # Options not available, use defaults
        pass

    if not generate_mocks and not regenerate_all_mocks:
        return

    regenerate_mode = regenerate_all_mocks
    generated_mocks = mock_tracking_data["generated_mocks"]
    mock_failures = mock_tracking_data["mock_failures"]

    # If no terminalreporter, skip output
    if not terminalreporter:
        return

    # Header
    _safe_print(terminalreporter, f"\n{'=' * 80}")
    _safe_print(
        terminalreporter,
        f"{'🔄 MOCK REGENERATION SUMMARY' if regenerate_mode else '🔧 MOCK GENERATION SUMMARY'}",
    )
    _safe_print(terminalreporter, f"{'=' * 80}")

    # Note: Cleared directories are now handled by shared_test_infrastructure fixture
    # and reported during setup phase to ensure single execution across workers

    # Generated mocks
    if generated_mocks:
        _safe_print(
            terminalreporter, f"✅ Generated {len(generated_mocks)} mock files:\n"
        )

        # Group by test case
        by_test_case = {}
        for mock_info in generated_mocks:
            parts = mock_info.split(":", 2)
            if len(parts) == 3:
                test_case, tool_name, filename = parts
                by_test_case.setdefault(test_case, []).append(
                    f"{tool_name} -> {filename}"
                )

        for test_case, mock_files in sorted(by_test_case.items()):
            _safe_print(terminalreporter, f"📁 {test_case}:")
            for mock_file in mock_files:
                _safe_print(terminalreporter, f"   - {mock_file}")
            _safe_print(terminalreporter)
    else:
        mode_text = "regeneration" if regenerate_mode else "generation"
        _safe_print(
            terminalreporter,
            f"✅ Mock {mode_text} was enabled but no new mock files were created",
        )

    # Failures
    if mock_failures:
        _safe_print(
            terminalreporter, f"⚠️  {len(mock_failures)} mock-related failures occurred:"
        )
        for failure in mock_failures:
            _safe_print(terminalreporter, f"   - {failure}")
        _safe_print(terminalreporter)

    # Checklist
    checklist = [
        "Review generated mock files before committing",
        "Ensure mock data represents realistic scenarios",
        "Check data consistency across related mocks (e.g., if a pod appears in",
        "  one mock, it should appear in all related mocks from the same test run)",
        "Verify timestamps, IDs, and names match between interconnected mock files",
        "If pod/resource names change across tool calls, regenerate ALL mocks with --regenerate-all-mocks",
    ]

    _safe_print(terminalreporter, "📋 REVIEW CHECKLIST:")
    for item in checklist:
        _safe_print(terminalreporter, f"   □ {item}")
    _safe_print(terminalreporter, "=" * 80)


def _format_error_output(error_details: str) -> str:
    """Format error details with truncation if needed"""
    from tests.llm.utils.test_helpers import truncate_output

    return truncate_output(error_details, max_lines=MAX_ERROR_LINES)


def _run_test_setup(test_cases):
    """Run before_test for each test case in parallel"""
    from tests.llm.utils.commands import before_test
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    print(f"Setting up infrastructure for {len(test_cases)} test cases")

    start_time = time.time()
    successful_test_cases = 0
    failed_test_cases = 0
    timed_out_test_cases = 0

    with ThreadPoolExecutor(max_workers=min(len(test_cases), MAX_WORKERS)) as executor:
        # Submit all setup tasks
        future_to_test_case = {
            executor.submit(before_test, test_case): test_case
            for test_case in test_cases
        }

        # Wait for all tasks to complete and handle results
        for future in as_completed(future_to_test_case):
            test_case = future_to_test_case[future]
            try:
                result = future.result()  # Single CommandResult for the test case
                remaining_cases = (
                    len(test_cases)
                    - successful_test_cases
                    - failed_test_cases
                    - timed_out_test_cases
                )
                if result.success:
                    successful_test_cases += 1
                    print(
                        f"✅ Setup {test_case.id}: {result.command} ({result.elapsed_time:.2f}s); setups remaining: {remaining_cases}"
                    )
                elif result.error_type == "timeout":
                    timed_out_test_cases += 1
                    print(
                        f"⏰ Setup {test_case.id}: TIMEOUT after {result.elapsed_time:.2f}s; setups remaining: {remaining_cases}"
                    )

                    # Show the exact command that timed out
                    truncated_error = _format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] Setup timeout: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"Setup timeout for test {test_case.id}: Command '{result.command}' timed out after {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )
                else:
                    failed_test_cases += 1
                    print(
                        f"❌ Setup {test_case.id}: FAILED ({result.exit_info}, {result.elapsed_time:.2f}s); setups remaining: {remaining_cases}"
                    )

                    # Limit error details to 10 lines and add proper formatting
                    truncated_error = _format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] Setup failed: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"Setup failed for test {test_case.id}: Command '{result.command}' failed with {result.exit_info} in {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )

            except Exception as e:
                failed_test_cases += 1
                print(f"❌ Setup {test_case.id}: EXCEPTION - {e}")
                logging.error(f"Setup exception for {test_case.id}: {str(e)}")

                # Emit warning to make it visible in pytest output
                warnings.warn(
                    f"Setup exception for test {test_case.id}: {str(e)}",
                    UserWarning,
                    stacklevel=2,
                )

    elapsed_time = time.time() - start_time
    print(
        f"\n🕐 Setup completed in {elapsed_time:.2f}s: {successful_test_cases} successful, {failed_test_cases} failed, {timed_out_test_cases} timeout"
    )


def _run_test_cleanup(test_cases):
    """Run after_test for each test case in parallel"""
    from tests.llm.utils.commands import after_test
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    print(f"Cleaning up infrastructure after tests for {len(test_cases)} test cases")

    start_time = time.time()
    successful_test_cases = 0
    failed_test_cases = 0
    timed_out_test_cases = 0

    with ThreadPoolExecutor(max_workers=min(len(test_cases), MAX_WORKERS)) as executor:
        # Submit all cleanup tasks
        future_to_test_case = {
            executor.submit(after_test, test_case): test_case
            for test_case in test_cases
        }

        # Wait for all tasks to complete and handle results
        for future in as_completed(future_to_test_case):
            test_case = future_to_test_case[future]
            try:
                result = future.result()  # Single CommandResult for the test case
                remaining_cases = (
                    len(test_cases)
                    - successful_test_cases
                    - failed_test_cases
                    - timed_out_test_cases
                )

                if result.success:
                    successful_test_cases += 1
                    print(
                        f"✅ Cleanup {test_case.id}: {result.command} ({result.elapsed_time:.2f}s); cleanups remaining: {remaining_cases}"
                    )
                elif result.error_type == "timeout":
                    timed_out_test_cases += 1
                    print(
                        f"⏰ Cleanup {test_case.id}: TIMEOUT after {result.elapsed_time:.2f}s; cleanups remaining: {remaining_cases}"
                    )

                    # Show the exact command that timed out
                    truncated_error = _format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] Cleanup timeout: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"Cleanup timeout for test {test_case.id}: Command '{result.command}' timed out after {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )
                else:
                    failed_test_cases += 1
                    print(
                        f"❌ Cleanup {test_case.id}: FAILED ({result.exit_info}, {result.elapsed_time:.2f}s); cleanups remaining: {remaining_cases}"
                    )

                    # Limit error details to 10 lines and add proper formatting
                    truncated_error = _format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] Cleanup failed: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"Cleanup failed for test {test_case.id}: Command '{result.command}' failed with {result.exit_info} in {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )

            except Exception as e:
                failed_test_cases += 1
                print(f"❌ Cleanup {test_case.id}: EXCEPTION - {e}")
                logging.error(f"Cleanup exception for {test_case.id}: {str(e)}")

                # Emit warning to make it visible in pytest output
                warnings.warn(
                    f"Cleanup exception for test {test_case.id}: {str(e)}",
                    UserWarning,
                    stacklevel=2,
                )

    elapsed_time = time.time() - start_time
    print(
        f"\n🕐 Cleanup completed in {elapsed_time:.2f}s: {successful_test_cases} successful, {failed_test_cases} failed, {timed_out_test_cases} timeout"
    )


def _extract_test_cases_needing_setup(session):
    """Extract unique test cases that need setup from session items"""
    from tests.llm.utils.test_case_utils import HolmesTestCase  # type: ignore[attr-defined]

    seen_ids = set()
    test_cases = []

    for item in session.items:
        if (
            item.get_closest_marker("llm")
            and hasattr(item, "callspec")
            and "test_case" in item.callspec.params
        ):
            test_case = item.callspec.params["test_case"]
            if (
                isinstance(test_case, HolmesTestCase)
                and test_case.before_test
                and test_case.id not in seen_ids
            ):
                test_cases.append(test_case)
                seen_ids.add(test_case.id)

    return test_cases


def _clear_mock_directories(session):
    """Clear mock directories for all test cases when --regenerate-all-mocks is set"""
    from tests.llm.utils.test_case_utils import HolmesTestCase  # type: ignore[attr-defined]
    import glob

    print("\n🧹 Clearing mock files for --regenerate-all-mocks")

    cleared_directories = set()
    total_files_removed = 0

    # Extract all unique test case folders
    test_folders = set()
    for item in session.items:
        if (
            item.get_closest_marker("llm")
            and hasattr(item, "callspec")
            and "test_case" in item.callspec.params
        ):
            test_case = item.callspec.params["test_case"]
            if isinstance(test_case, HolmesTestCase):
                test_folders.add(test_case.folder)

    # Clear mock files from each folder
    for folder in test_folders:
        patterns = [
            os.path.join(folder, "*.txt"),
            os.path.join(folder, "*.json"),
        ]

        folder_files_removed = 0
        for pattern in patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    folder_files_removed += 1
                    total_files_removed += 1
                except Exception as e:
                    logging.warning(f"Could not remove {file_path}: {e}")

        if folder_files_removed > 0:
            cleared_directories.add(folder)
            print(
                f"   ✅ Cleared {folder_files_removed} mock files from {os.path.basename(folder)}"
            )

    print(
        f"   📊 Total: Cleared {total_files_removed} files from {len(cleared_directories)} directories\n"
    )

    return list(cleared_directories)
