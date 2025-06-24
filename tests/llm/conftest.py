import json
import logging
import os
import pytest
from tests.llm.utils.braintrust import get_experiment_results
from braintrust.span_types import SpanTypeAttribute
from tests.llm.utils.constants import PROJECT


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
            print(f"* test_suite={test_suite}")
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
                    print(
                        f"** {span_name} expected_correctness_score={expected_correctness_score}, correctness_score={correctness_score}, metadata={json.dumps(test_case.get('metadata', {}))}"
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
