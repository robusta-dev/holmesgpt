import logging
import os
import pytest
import textwrap
import warnings
from pytest_shared_session_scope import (
    shared_session_scope_json,
    SetupToken,
    CleanupToken,
)
from tests.llm.utils.braintrust import get_experiment_results
from braintrust.span_types import SpanTypeAttribute
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.classifiers import create_llm_client

# Constants
MAX_ERROR_LINES = 10
MAX_WORKERS = 30

# Configure logging levels for cleaner test output
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# see https://github.com/StefanBRas/pytest-shared-session-scope
@shared_session_scope_json()
def shared_test_infrastructure(request):
    """Shared session-scoped fixture for test infrastructure setup/cleanup coordination"""
    if not os.environ.get("RUN_LIVE") or request.config.getoption("--collect-only"):
        print(
            "Skipping test infrastructure setup/cleanup - RUN_LIVE not set or collect-only mode"
        )
        yield None
        return

    data = yield

    if data is SetupToken.FIRST:
        print("🎯 Running setup (first worker)")
        test_cases = _extract_test_cases_needing_setup(request.session)
        if test_cases:
            print(f"Setting up infrastructure for {len(test_cases)} test cases")
            _run_test_setup(test_cases)
            data = {"test_cases_for_cleanup": [tc.id for tc in test_cases]}
        else:
            print("No test cases found needing setup")
            data = {"test_cases_for_cleanup": []}
    else:
        print("⏭️ Setup already done by another worker")

    cleanup_token = yield data

    if cleanup_token is CleanupToken.LAST:
        print("🧹 Running cleanup (last worker)")
        test_case_ids = data.get("test_cases_for_cleanup", [])
        if test_case_ids:
            print(f"Cleaning up infrastructure for {len(test_case_ids)} test cases")
            # Reconstruct test cases from IDs
            from tests.llm.utils.mock_utils import HolmesTestCase

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
                print("✅ Cleanup completed")
            else:
                print("No test cases found for cleanup")
        else:
            print("No test case IDs found for cleanup")
    else:
        print("⏭️ Cleanup will be done by another worker")


@pytest.fixture(scope="session", autouse=True)
def test_infrastructure_coordination(shared_test_infrastructure):
    """Ensure the shared test infrastructure fixture is used (triggers setup/cleanup)"""
    # This fixture just ensures shared_test_infrastructure runs for all sessions
    # All the actual logic is in shared_test_infrastructure
    yield


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
        yield
        return

    # Check if LLM marker is being excluded
    markexpr = request.config.getoption("-m", default="")
    if "not llm" in markexpr:
        yield
        return  # Don't show warning if explicitly excluding LLM tests

    # session.items contains the final filtered list of tests that will actually run
    session = request.session
    llm_tests = [item for item in session.items if item.get_closest_marker("llm")]

    if llm_tests:
        # Check API connectivity and show appropriate message
        api_available, error_msg = check_llm_api_with_test_call()

        if api_available:
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
            print("=" * 70 + "\n")
        else:
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

    yield  # Tests run here


def _format_error_output(error_details: str) -> str:
    """Format error details with truncation if needed"""
    error_lines = error_details.split("\n")
    if len(error_lines) > MAX_ERROR_LINES:
        truncated_error = "\n".join(error_lines[:MAX_ERROR_LINES])
        truncated_error += f"\n... [TRUNCATED: {len(error_lines) - MAX_ERROR_LINES} more lines not shown]"
    else:
        truncated_error = error_details
    return truncated_error


def _run_test_setup(test_cases):
    """Run before_test for each test case in parallel"""
    from tests.llm.utils.commands import before_test
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    print(f"\nSetting up infrastructure for {len(test_cases)} test cases")

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
                    exit_info = (
                        f"exit {result.exit_code}"
                        if result.exit_code is not None
                        else "no exit code"
                    )
                    print(
                        f"❌ Setup {test_case.id}: FAILED ({exit_info}, {result.elapsed_time:.2f}s); setups remaining: {remaining_cases}"
                    )

                    # Limit error details to 10 lines and add proper formatting
                    truncated_error = _format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] Setup failed: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"Setup failed for test {test_case.id}: Command '{result.command}' failed with {exit_info} in {result.elapsed_time:.2f}s. Output: {result.error_details}",
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

    print("\nCleaning up test infrastructure after tests")
    print(f"\nCleaning up infrastructure for {len(test_cases)} test cases")

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
                    exit_info = (
                        f"exit {result.exit_code}"
                        if result.exit_code is not None
                        else "no exit code"
                    )
                    print(
                        f"❌ Cleanup {test_case.id}: FAILED ({exit_info}, {result.elapsed_time:.2f}s); cleanups remaining: {remaining_cases}"
                    )

                    # Limit error details to 10 lines and add proper formatting
                    truncated_error = _format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] Cleanup failed: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"Cleanup failed for test {test_case.id}: Command '{result.command}' failed with {exit_info} in {result.elapsed_time:.2f}s. Output: {result.error_details}",
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
    from tests.llm.utils.mock_utils import HolmesTestCase

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


def markdown_table(headers, rows):
    markdown = "| " + " | ".join(headers) + " |\n"
    markdown += "| " + " | ".join(["---" for _ in headers]) + " |\n"
    for row in rows:
        markdown += "| " + " | ".join(str(cell) for cell in row) + " |\n"
    return markdown


@pytest.mark.llm
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not os.environ.get("PUSH_EVALS_TO_BRAINTRUST"):
        # The code fetches the evals from Braintrust to print out a summary.
        # Skip running it if the evals have not been uploaded to Braintrust
        return

    headers = ["Test suite", "Test case", "Status"]
    rows = []

    # Do not change the title below without updating the github workflow that references it
    markdown = "## Results of HolmesGPT evals\n"

    for test_suite in ["ask_holmes", "investigate"]:
        try:
            result = get_experiment_results(PROJECT, test_suite)
            result.records.sort(key=lambda x: x.get("span_attributes", {}).get("name"))
            total_test_cases = 0
            successful_test_cases = 0
            for record in result.records:
                scores = record.get("scores", None)
                span_id = record.get("id")
                span_attributes = record.get("span_attributes")
                if scores and span_attributes:
                    span_type = span_attributes.get("type")
                    if span_type != SpanTypeAttribute.EVAL:
                        continue

                    span_name = span_attributes.get("name")
                    test_case = next(
                        (tc for tc in result.test_cases if tc.get("id") == span_name),
                        {},
                    )
                    correctness_score = scores.get("correctness", 0)
                    expected_correctness_score = (
                        test_case.get("metadata", {})
                        .get("test_case", {})
                        .get("evaluation", {})
                        .get("correctness", 0)
                    )
                    if isinstance(expected_correctness_score, dict):
                        expected_correctness_score = expected_correctness_score.get(
                            "expected_score", 1
                        )
                    total_test_cases += 1
                    status_text = ":x:"
                    if correctness_score == 1:
                        successful_test_cases += 1
                        status_text = ":white_check_mark:"
                    elif correctness_score >= expected_correctness_score:
                        status_text = ":warning:"
                    rows.append(
                        [
                            f"[{test_suite}](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/{result.experiment_name})",
                            f"[{span_name}](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/{result.experiment_name}?r={span_id})",
                            status_text,
                        ]
                    )
            markdown += f"\n- [{test_suite}](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/{result.experiment_name}): {successful_test_cases}/{total_test_cases} test cases were successful"

        except ValueError:
            logging.info(
                f"Failed to fetch braintrust experiment {PROJECT}-{test_suite}"
            )

    if len(rows) > 0:
        markdown += "\n\n"
        markdown += markdown_table(headers, rows)
        markdown += "\n\n**Legend**\n"
        markdown += "\n- :white_check_mark: the test was successful"
        markdown += (
            "\n- :warning: the test failed but is known to be flakky or known to fail"
        )
        markdown += "\n- :x: the test failed and should be fixed before merging the PR"

        with open("evals_report.txt", "w", encoding="utf-8") as file:
            file.write(markdown)
