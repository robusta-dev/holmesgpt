"""Data models and utilities for test result processing."""

from dataclasses import dataclass
from typing import List, Optional


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


class TestStatus:
    """Encapsulates test status determination logic."""

    def __init__(self, result: dict):
        self.actual_score = int(result.get("actual_correctness_score", 0))
        self.expected_score = int(result.get("expected_correctness_score", 1))
        self.is_mock_failure = result.get("mock_data_failure", False)
        self.status = result.get(
            "status", ""
        )  # pytest status (passed, failed, skipped, etc.)

    @property
    def passed(self) -> bool:
        return (
            self.actual_score == 1
        )  # TODO: possibly add `and not self.is_mock_failure`

    @property
    def is_skipped(self) -> bool:
        return self.status == "skipped"

    @property
    def is_regression(self) -> bool:
        if self.is_skipped or self.passed or self.is_mock_failure:
            return False
        # Known failure (expected to fail)
        if self.actual_score == 0 and self.expected_score == 0:
            return False
        return True

    @property
    def markdown_symbol(self) -> str:
        if self.is_skipped:
            return ":arrow_right_hook:"
        elif self.is_mock_failure:
            return ":wrench:"
        elif self.passed:
            return ":white_check_mark:"
        elif self.actual_score == 0 and self.expected_score == 0:
            return ":warning:"
        else:
            return ":x:"

    @property
    def console_status(self) -> str:
        if self.is_skipped:
            return "[cyan]SKIPPED[/cyan]"
        elif self.is_mock_failure:
            return "[yellow]MOCK FAILURE[/yellow]"
        elif self.passed:
            return "[green]PASS[/green]"
        else:
            return "[red]FAIL[/red]"

    @property
    def short_status(self) -> str:
        if self.is_skipped:
            return "SKIPPED"
        elif self.is_mock_failure:
            return "MOCK FAILURE"
        elif self.passed:
            return "PASS"
        else:
            return "FAIL"
