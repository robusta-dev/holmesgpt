import pytest
from tests.llm.utils.braintrust import get_experiment_results
from tests.llm.utils.constants import PROJECT
from rich.table import Table
from rich.console import Console


def pytest_configure(config):
    # Register the llm marker if not already registered
    config.addinivalue_line("markers", "llm: mark test as an LLM test")


@pytest.mark.llm
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    table = Table(title="Evals")
    table.add_column("Suite", justify="right", style="cyan", no_wrap=True)
    table.add_column("Test case", style="magenta")
    table.add_column("Pass/Fail", justify="right", style="green")

    for test_suite in ["ask_holmes", "investigate"]:
        results = list(get_experiment_results(PROJECT, test_suite))
        results.sort(key=lambda x: x.get("span_attributes").get("name"))
        for result in results:
            if result.get("scores", {}):
                success_text = (
                    "pass"
                    if result.get("scores").get("correctness", 0) == 1
                    else "fail"
                )
                table.add_row(
                    test_suite, result.get("span_attributes").get("name"), success_text
                )

    with open("evals_report.txt", "w", encoding="utf-8") as file:
        console = Console(file=file)
        console.print(table)
