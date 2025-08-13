import os
from contextlib import contextmanager

import pytest
from pytest_shared_session_scope import (
    shared_session_scope_json,
    SetupToken,
    CleanupToken,
)

from tests.llm.utils.test_results import TestResult
from tests.llm.utils.classifiers import create_llm_client
from tests.llm.utils.mock_toolset import (  # type: ignore[attr-defined]
    MockMode,
    MockGenerationConfig,
    report_mock_operations,
)
from tests.llm.utils.reporting.terminal_reporter import handle_console_output
from tests.llm.utils.reporting.github_reporter import handle_github_output
from tests.llm.utils.braintrust import get_braintrust_url
from tests.llm.utils.setup_cleanup import (
    run_all_test_setup,
    log,
    extract_llm_test_cases,
)
from tests.llm.utils.port_forward import (
    setup_all_port_forwards,
    extract_port_forwards_from_test_cases,
    cleanup_port_forwards_by_config,
    check_port_availability_early,
)


# Configuration constants
DEBUG_SEPARATOR = "=" * 80
LLM_TEST_TYPES = ["test_ask_holmes", "test_investigate", "test_workload_health"]


def is_llm_test(nodeid: str) -> bool:
    """Check if a test nodeid is for an LLM test."""
    return any(
        [
            "test_ask_holmes" in nodeid,
            "test_investigate" in nodeid,
            "test_workload_health" in nodeid,
        ]
    )


@pytest.fixture(scope="session")
def mock_generation_config(request):
    """Session-scoped fixture that provides mock generation configuration and mode."""
    # Safely get options with defaults in case they're not registered
    generate_mocks = request.config.getoption("--generate-mocks")
    regenerate_all_mocks = request.config.getoption("--regenerate-all-mocks")

    # --regenerate-all-mocks implies --generate-mocks
    if regenerate_all_mocks:
        generate_mocks = True

    run_live = os.getenv("RUN_LIVE", "False").lower() in ("true", "1", "t")
    if generate_mocks and not run_live:
        print(
            "⚠️  WARNING: --generate-mocks is set but RUN_LIVE is not set. This will not generate mocks."
        )
        pytest.skip(
            "Skipping test case because --generate-mocks is set but RUN_LIVE is not set."
        )

    # Determine mode based on environment and options

    if generate_mocks:
        mode = MockMode.GENERATE  # live & generate
    elif run_live:
        mode = MockMode.LIVE
    else:
        mode = MockMode.MOCK

    return MockGenerationConfig(generate_mocks, regenerate_all_mocks, mode)


# Handles before_test and after_test
# see https://github.com/StefanBRas/pytest-shared-session-scope
@shared_session_scope_json()
def shared_test_infrastructure(request, mock_generation_config: MockGenerationConfig):
    """Shared session-scoped fixture for test infrastructure setup/cleanup coordination"""
    collect_only = request.config.getoption("--collect-only")
    worker_id = getattr(request.config, "workerinput", {}).get("workerid", None)

    # If we're in collect-only mode or RUN_LIVE is not set, skip setup/cleanup entirely
    if collect_only or mock_generation_config.mode == MockMode.MOCK:
        log(
            f"\n⚙️ Skipping shared test infrastructure setup/cleanup on worker {worker_id} (mode: {mock_generation_config.mode}, collect_only: {collect_only})"
        )
        # Must yield twice even when skipping due to how pytest-shared-session-scope works
        initial = yield
        cleanup_token = yield {"test_cases_for_cleanup": []}
        return

    # First yield: get initial value (SetupToken.FIRST if first worker, data if subsequent)
    initial = yield

    if initial is SetupToken.FIRST:
        # This is the first worker to run the fixture
        # Extract all test cases (we need them all for port forwards)
        test_cases = extract_llm_test_cases(request.session)

        # Clear mock directories if --regenerate-all-mocks is set
        cleared_directories = []
        regenerate_all = request.config.getoption("--regenerate-all-mocks")

        if regenerate_all:
            from tests.llm.utils.mock_toolset import clear_all_mocks  # type: ignore[attr-defined]

            cleared_directories = clear_all_mocks(request.session)

        # Run setup unless --skip-setup is set
        # Check port availability BEFORE running any setup scripts
        # This allows us to fail fast if ports are unavailable
        check_port_availability_early(test_cases)

        # Check skip-setup option
        skip_setup = request.config.getoption("--skip-setup")

        if test_cases and not skip_setup:
            setup_failures = run_all_test_setup(test_cases)
        elif skip_setup:
            log("⚙️ Skipping test setup due to --skip-setup flag")
            setup_failures = {}
        else:
            setup_failures = {}

        # Set up port forwards AFTER namespace/resources are created
        setup_all_port_forwards(test_cases)

        data = {
            "test_cases_for_cleanup": [tc.id for tc in test_cases],
            "cleared_mock_directories": cleared_directories,
            "setup_failures": setup_failures,
            # Store port forward configs for cleanup (not the manager object)
            "port_forward_configs": extract_port_forwards_from_test_cases(test_cases),
        }
    else:
        log(f"⚙️ Skipping before_test/after_test on worker {worker_id}")
        # This is a worker using the fixture after the first worker
        data = initial

    # Actual test runs here when we yield - then we get back a cleanup token from pytest-shared-session-scope
    cleanup_token = yield data

    if cleanup_token is CleanupToken.LAST:
        # This is the last worker to exit - responsible for cleanup
        test_case_ids = data.get("test_cases_for_cleanup", [])
        if not isinstance(test_case_ids, list):
            test_case_ids = []

        # Check skip-cleanup option
        skip_cleanup = request.config.getoption("--skip-cleanup")

        # Always clean up port forwards regardless of skip_cleanup flag
        port_forward_configs = data.get("port_forward_configs", [])
        if port_forward_configs and isinstance(port_forward_configs, list):
            try:
                # Kill any kubectl port-forward processes that match our configs
                cleanup_port_forwards_by_config(port_forward_configs)
            except Exception as e:
                log(f"⚠️ Error cleaning up port forwards: {e}")

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
                from tests.llm.utils.setup_cleanup import (
                    run_all_test_commands,
                    Operation,
                )

                # Only run the after_test commands, not port forward cleanup
                run_all_test_commands(cleanup_test_cases, Operation.CLEANUP)
        elif skip_cleanup:
            log("⚙️ Skipping test cleanup due to --skip-cleanup flag")


# TODO: do we actually need this?
@pytest.fixture(scope="session", autouse=True)
def test_infrastructure_coordination(shared_test_infrastructure):
    """Ensure the shared test infrastructure fixture is used (triggers setup/cleanup)"""
    # This fixture just ensures shared_test_infrastructure runs for all sessions
    # All the actual logic is in shared_test_infrastructure
    yield


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
            error_msg = f"Exception: {type(e).__name__}: {str(e)} - Tried to use AzureAI (model: {classifier_model}) because AZURE_API_BASE was set. Check AZURE_API_BASE, AZURE_API_KEY, AZURE_API_VERSION, or unset them to use OpenAI."

        else:
            error_msg = f"Exception: {type(e).__name__}: {str(e)} - Tried to use OpenAI (model: {classifier_model}). Check OPENAI_API_KEY or set AZURE_API_BASE to use Azure AI."

        return False, error_msg


@pytest.fixture(scope="session", autouse=True)
def llm_availability_check(request):
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

                # Show ASK_HOLMES_TEST_TYPE if relevant for ask_holmes tests
                ask_holmes_tests = [
                    t for t in llm_tests if "test_ask_holmes" in t.nodeid
                ]
                if ask_holmes_tests:
                    test_type = os.environ.get("ASK_HOLMES_TEST_TYPE", "cli").lower()
                    print(f"ASK_HOLMES_TEST_TYPE: {test_type} (use 'cli' or 'server')")
                    print()

                # Check if Braintrust is enabled
                braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
                if braintrust_api_key:
                    print(
                        f"✓ Braintrust is enabled - traces and results will be available at {get_braintrust_url()}"  # type: ignore[no-untyped-call]
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
    braintrust_url = get_braintrust_url(span_id, root_span_id)

    with force_pytest_output(request):
        # Use ANSI escape codes to create a clickable link in terminals that support it
        # Format: \033]8;;URL\033\\TEXT\033]8;;\033\\
        clickable_url = f"\033]8;;{braintrust_url}\033\\{braintrust_url}\033]8;;\033\\"
        print(f"\n🔍 View eval result: \033[94m{clickable_url}\033[0m")
        print()


def show_llm_summary_report(terminalreporter, exitstatus, config):
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
    handle_github_output(sorted_results)

    # Handle console/developer output (Rich table + Braintrust links)
    handle_console_output(sorted_results, terminalreporter)

    # Report mock operation statistics
    report_mock_operations(config, mock_tracking_data, terminalreporter)

    # Display single Braintrust experiment link at the very end
    _display_braintrust_experiment_link(terminalreporter)


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
            # For skipped tests, we need to look at 'setup' phase
            when = getattr(report, "when", None)
            if status == "skipped" and when == "setup":
                # Process skipped tests
                nodeid = getattr(report, "nodeid", "")
                if not is_llm_test(nodeid):
                    continue

                # Extract test type
                if "test_ask_holmes" in nodeid:
                    test_type = "ask"
                elif "test_investigate" in nodeid:
                    test_type = "investigate"
                elif "test_workload_health" in nodeid:
                    test_type = "workload_health"
                else:
                    test_type = "unknown"

                # Extract skip reason
                skip_reason = "Skipped"
                if hasattr(report, "longrepr") and report.longrepr:
                    # longrepr for skipped tests is typically a tuple (file, line, reason)
                    if isinstance(report.longrepr, tuple) and len(report.longrepr) >= 3:
                        skip_reason = str(report.longrepr[2])
                    else:
                        skip_reason = str(report.longrepr)

                # Store minimal result for skipped test
                test_results[nodeid] = {
                    "nodeid": nodeid,
                    "test_type": test_type,
                    "expected": "Test skipped",
                    "actual": skip_reason,
                    "tools_called": [],
                    "expected_correctness_score": 0.0,
                    "user_prompt": "",
                    "actual_correctness_score": 0.0,
                    "status": "skipped",
                    "outcome": "skipped",
                    "execution_time": getattr(report, "duration", None),
                    "mock_data_failure": False,
                    "braintrust_span_id": None,
                    "braintrust_root_span_id": None,
                }
                continue
            elif when != "call":
                # For other statuses, only process 'call' phase
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
                "user_prompt": user_props.get("user_prompt", ""),
                "is_setup_failure": user_props.get("is_setup_failure", False),
                "error_message": str(report.longrepr)
                if hasattr(report, "longrepr") and report.longrepr
                else None,
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
            user_prompt=result["user_prompt"],
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


def _display_braintrust_experiment_link(terminalreporter):
    """Display a single Braintrust experiment link at the end of test output."""
    # Check if Braintrust is enabled
    if not os.environ.get("BRAINTRUST_API_KEY"):
        return

    # Build experiment URL
    experiment_url = get_braintrust_url()

    print("\n" + "=" * 70)
    print("🧠 Braintrust Experiment Summary")
    print("=" * 70)
    # Make it clickable in terminals that support it
    clickable_url = f"\033]8;;{experiment_url}\033\\{experiment_url}\033]8;;\033\\"
    print(f"View full experiment results: \033[94m{clickable_url}\033[0m")
    print("=" * 70 + "\n")
