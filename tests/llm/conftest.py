import json
import logging
import os
import pytest
from filelock import FileLock
from functools import wraps
import tempfile
from pathlib import Path
from tests.llm.utils.braintrust import get_experiment_results
from braintrust.span_types import SpanTypeAttribute
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.classifiers import create_llm_client


def xdist_once_per_session(setup_func, cleanup_func):
    """
    Decorator that ensures setup/cleanup functions run only once per test session,
    even when using pytest-xdist with multiple workers.

    Args:
        setup_func: Function to run once at session start
        cleanup_func: Function to run once at session end (after all workers finish)

    Returns:
        Decorated fixture function that handles xdist coordination
    """

    def decorator(fixture_func):
        @wraps(fixture_func)
        def wrapper(request, tmp_path_factory, worker_id):
            # Skip if not needed
            if not os.environ.get("RUN_LIVE") or request.config.getoption(
                "--collect-only"
            ):
                yield
                return

            # Get data for setup/cleanup
            setup_data = fixture_func(request, tmp_path_factory, worker_id)
            if not setup_data:
                yield
                return

            if worker_id == "master":
                # Single worker mode - run setup/cleanup directly
                setup_func(setup_data)
                yield
                cleanup_func(setup_data)
            else:
                # xdist mode - coordinate via files
                _coordinate_xdist_setup_cleanup(
                    setup_data, setup_func, cleanup_func, request.session
                )
                yield

        return wrapper

    return decorator


def _coordinate_xdist_setup_cleanup(setup_data, setup_func, cleanup_func, session):
    """Handle xdist coordination for setup/cleanup"""
    root_tmp_dir = Path(tempfile.gettempdir())
    setup_file = root_tmp_dir / "holmesgpt_setup_done.txt"
    data_file = root_tmp_dir / "holmesgpt_setup_data.json"
    worker_count_file = root_tmp_dir / "holmesgpt_worker_count.txt"

    # Setup coordination
    with FileLock(str(setup_file) + ".lock"):
        if not setup_file.exists():
            setup_func(setup_data)

            # Save setup data (serialize test case IDs) and worker count
            serializable_data = [tc.id for tc in setup_data] if setup_data else []
            data_file.write_text(json.dumps(serializable_data))
            worker_count_file.write_text("1")
            setup_file.write_text("done")
        else:
            # Increment worker count
            with FileLock(str(worker_count_file) + ".lock"):
                current_count = int(worker_count_file.read_text().strip())
                worker_count_file.write_text(str(current_count + 1))


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


def _run_test_setup(test_cases):
    """Run before_test for each test case"""
    from tests.llm.utils.commands import before_test

    print(f"\nSetting up infrastructure for {len(test_cases)} test cases")
    for test_case in test_cases:
        before_test(test_case)


def _run_test_cleanup(test_cases):
    """Run after_test for each test case in reverse order"""
    from tests.llm.utils.commands import after_test

    print(f"\nCleaning up test infrastructure for {len(test_cases)} test cases")
    for test_case in reversed(test_cases):
        after_test(test_case)


@pytest.fixture(scope="session", autouse=True)
@xdist_once_per_session(_run_test_setup, _run_test_cleanup)
def test_infrastructure_setup(request, tmp_path_factory, worker_id):
    """Set up test infrastructure once per session (xdist-safe)"""
    return _extract_test_cases_needing_setup(request.session)


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


def pytest_sessionfinish(session, exitstatus):
    """Clean up test infrastructure when the last worker finishes (xdist-safe)"""
    # Only run if RUN_LIVE is set
    if not os.environ.get("RUN_LIVE"):
        return

    root_tmp_dir = Path(tempfile.gettempdir())
    data_file = root_tmp_dir / "holmesgpt_setup_data.json"
    worker_count_file = root_tmp_dir / "holmesgpt_worker_count.txt"
    finished_workers_file = root_tmp_dir / "holmesgpt_finished_workers.txt"
    cleanup_done_file = root_tmp_dir / "holmesgpt_cleanup_done.txt"

    # Only do cleanup if we have data and cleanup hasn't been done yet
    if not data_file.exists() or cleanup_done_file.exists():
        return

    # Track finished workers and cleanup when last one finishes
    with FileLock(str(finished_workers_file) + ".lock"):
        if cleanup_done_file.exists():
            return  # Another worker already did cleanup

        # Increment finished worker count
        if finished_workers_file.exists():
            finished_count = int(finished_workers_file.read_text().strip()) + 1
        else:
            finished_count = 1
        finished_workers_file.write_text(str(finished_count))

        # Get total worker count
        if worker_count_file.exists():
            total_workers = int(worker_count_file.read_text().strip())
        else:
            total_workers = 1  # Fallback

        # Only cleanup if this is the last worker
        if finished_count >= total_workers:
            # Read setup data and perform cleanup
            test_case_ids = json.loads(data_file.read_text())

            if test_case_ids:
                # Reconstruct test cases from IDs
                from tests.llm.utils.mock_utils import HolmesTestCase

                cleanup_test_cases = []

                for item in session.items:
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

                # Clean up coordination files
                data_file.unlink()
                worker_count_file.unlink()
                finished_workers_file.unlink()
                setup_file = root_tmp_dir / "holmesgpt_setup_done.txt"
                if setup_file.exists():
                    setup_file.unlink()

            # Mark cleanup as done
            cleanup_done_file.write_text("done")


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
