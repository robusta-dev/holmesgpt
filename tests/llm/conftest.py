import logging
import os
import pytest
from tests.llm.utils.braintrust import get_experiment_results
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
        return

    headers = ["Suite", "Test case", "Status"]
    rows = []

    # markdown = (
    #     f"## Results of HolmesGPT evals\n"
    #     f"https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/${experiment_id}"

    # )

    for test_suite in ["ask_holmes", "investigate"]:

        try:
            result = get_experiment_results(PROJECT, test_suite)
            result.records.sort(key=lambda x: x.get("span_attributes", {}).get("name"))
            for record in result.records:
                # print(record)
                scores = record.get("scores", None)
                span_id = record.get("id")
                span_attributes = record.get("span_attributes")
                if scores and span_attributes:
                    span_name = span_attributes.get("name")
                    status_text = (
                        ":white_check_mark:"
                        if scores.get("correctness", 0) == 1
                        else ":x:"
                    )
                    rows.append([
                        f"[{test_suite}](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/{result.experiment_name})",
                        f"[{span_name}](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/{result.experiment_name}?r={span_id})",
                        status_text
                    ])

        except ValueError:
            logging.info(f"Failed to fetch braintrust experiment {PROJECT}-{test_suite}")

    if len(rows) > 0:
        # markdown = (
        #     f"## Results of HolmesGPT evals\n"
        #     f"https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/${experiment_id}"

        # )


        with open("evals_report.txt", "w", encoding="utf-8") as file:
            file.write(markdown_table(headers, rows))
