"""Property management utilities for cleaner test metadata handling."""

from typing import Any, List, Tuple


class TestPropertyManager:
    """Helper class for managing test properties in a cleaner way."""

    def __init__(self, request):
        self.request = request

    def add(self, key: str, value: Any) -> None:
        """Add a property to the test node."""
        if hasattr(self.request.node, "user_properties"):
            self.request.node.user_properties.append((key, value))

    def add_multiple(self, properties: List[Tuple[str, Any]]) -> None:
        """Add multiple properties at once."""
        for key, value in properties:
            self.add(key, value)

    def add_test_result(
        self,
        expected: str,
        actual: str,
        tools_called: List[str],
        expected_score: float = 1.0,
        actual_score: float = 0.0,
        mock_failure: bool = False,
    ) -> None:
        """Add standard test result properties."""
        self.add_multiple(
            [
                ("expected", expected),
                ("actual", actual),
                ("tools_called", tools_called),
                ("expected_correctness_score", expected_score),
                ("actual_correctness_score", actual_score),
                ("mock_data_failure", mock_failure),
            ]
        )

    def add_braintrust_info(self, span_id: str, root_span_id: str) -> None:
        """Add Braintrust tracking information."""
        self.add_multiple(
            [
                ("braintrust_span_id", span_id),
                ("braintrust_root_span_id", root_span_id),
            ]
        )

    def mark_mock_failure(
        self, expected: str, actual_msg: str = "Mock data not found"
    ) -> None:
        """Mark a test as failed due to mock data issues."""
        self.add_test_result(
            expected=expected,
            actual=actual_msg,
            tools_called=[],
            actual_score=0,
            mock_failure=True,
        )


# Pytest fixture for easy access
def pytest_plugin():
    """Plugin registration for property manager fixture."""
    import pytest

    @pytest.fixture
    def test_props(request):
        """Provide a TestPropertyManager instance for the current test."""
        return TestPropertyManager(request)

    return test_props
