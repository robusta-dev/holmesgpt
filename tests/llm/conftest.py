import logging
import os
import pytest
from tests.llm.utils.braintrust import get_experiment_results
from braintrust.span_types import SpanTypeAttribute
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.classifiers import create_llm_client


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
            api_type = "AzureAI"
            relevant_env_vars = "Check AZURE_API_BASE, AZURE_API_KEY, AZURE_API_VERSION or unset AZURE_API_BASE to use OpenAI"
        else:
            api_type = "OpenAI"
            relevant_env_vars = "Check OPENAI_API_KEY or use AzureAI by setting AZURE_API_BASE, AZURE_API_KEY, and AZURE_API_VERSION"

        error_msg = f"Tried to use {api_type} (model: {classifier_model})\n  Exception: {type(e).__name__}: {str(e)[:200]}...\n  How to fix: {relevant_env_vars}"
        return False, error_msg


def pytest_collection_modifyitems(config, items):
    """Show warning when LLM evaluation tests are collected"""
    # Check if LLM marker is being excluded
    markexpr = config.getoption("-m", default="")
    if "not llm" in markexpr:
        return  # Don't show warning if explicitly excluding LLM tests

    llm_tests = [item for item in items if item.get_closest_marker("llm")]

    if llm_tests:
        # Do EXACT same check as session fixture - create client and make API test call
        api_available, error_msg = check_llm_api_with_test_call()

        if api_available:
            print("\n" + "=" * 70)
            print(f"⚠️  WARNING: About to run {len(llm_tests)} LLM evaluation tests")
            print("These tests use AI models and may take 10-30+ minutes.")
            print("Skip with: poetry run pytest -m 'not llm'")
            print("=" * 70 + "\n")
        else:
            print("\n" + "=" * 70)
            print(f"ℹ️  INFO: {len(llm_tests)} LLM evaluation tests will be skipped")
            print()
            print(f"  Reason: {error_msg}")
            print("=" * 70 + "\n")


@pytest.fixture(scope="session")
def llm_api_check():
    """Test LLM API connectivity once per session"""
    api_available, error_msg = check_llm_api_with_test_call()

    if not api_available:
        pytest.skip(error_msg)

    # Fixture succeeds silently when API is available


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
