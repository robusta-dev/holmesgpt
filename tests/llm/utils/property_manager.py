"""Manage test properties for pytest reporting."""

from typing import List, Any, Union
from tests.llm.utils.test_case_utils import Evaluation, HolmesTestCase  # type: ignore[attr-defined]


def set_initial_properties(request, test_case: HolmesTestCase) -> None:
    """Set initial properties at the beginning of a test so they're available even if test fails early."""
    expected = test_case.expected_output
    if not isinstance(expected, list):
        expected = [expected]
    debug_expected = "\n-  ".join(expected)

    expected_correctness_score = (
        test_case.evaluation.correctness.expected_score
        if isinstance(test_case.evaluation.correctness, Evaluation)
        else test_case.evaluation.correctness
    )

    # Store basic properties that should always be available
    request.node.user_properties.append(("expected", debug_expected))
    request.node.user_properties.append(
        ("expected_correctness_score", expected_correctness_score)
    )
    request.node.user_properties.append(
        (
            "user_prompt",
            getattr(test_case, "user_prompt", ""),
        )  # only present in AskHolmesTestCase
    )
    request.node.user_properties.append(
        ("actual", "Test not executed")
    )  # Will be overwritten if test runs
    request.node.user_properties.append(
        ("actual_correctness_score", 0)
    )  # Will be overwritten if test runs
    request.node.user_properties.append(
        ("tools_called", [])
    )  # Will be overwritten if test runs


def update_property(request, key: str, value: Any) -> None:
    """Update an existing property value instead of appending a duplicate."""
    for i, (prop_key, prop_value) in enumerate(request.node.user_properties):
        if prop_key == key:
            request.node.user_properties[i] = (key, value)
            return
    # If property doesn't exist, append it
    request.node.user_properties.append((key, value))


def update_test_results(
    request,
    output: str,
    tools_called: Union[List[str], str],
    scores: dict,
    result: Any = None,
) -> None:
    """Update test result properties after test execution.

    Args:
        request: The pytest request object
        output: The test output string
        tools_called: List of tools called or a string description
        scores: Dictionary of scores (e.g., correctness)
        result: Optional result object (LLMResult or InvestigationResult) containing cost info
    """
    update_property(request, "actual", output or "")
    update_property(
        request,
        "tools_called",
        tools_called if isinstance(tools_called, list) else [str(tools_called)],
    )
    update_property(request, "actual_correctness_score", scores.get("correctness", 0))

    # Log test cost information and add to user properties if available
    if result:
        import logging

        # Check for cost tracking in LLMResult (from ask_holmes tests)
        if hasattr(result, "total_cost") and result.total_cost > 0:
            test_case_id = None
            model = None
            # Extract test_case_id and model from user_properties
            for key, value in request.node.user_properties:
                if key == "clean_test_case_id":
                    test_case_id = value
                elif key == "model":
                    model = value

            if test_case_id and model:
                logging.info(
                    f"Test {test_case_id} with {model} - Total cost: ${result.total_cost:.6f}, Total tokens: {result.total_tokens if hasattr(result, 'total_tokens') else 'N/A'}"
                )

            request.node.user_properties.append(("cost", result.total_cost))
            if hasattr(result, "total_tokens"):
                request.node.user_properties.append(
                    ("total_tokens", result.total_tokens)
                )
            if hasattr(result, "prompt_tokens"):
                request.node.user_properties.append(
                    ("prompt_tokens", result.prompt_tokens)
                )
            if hasattr(result, "completion_tokens"):
                request.node.user_properties.append(
                    ("completion_tokens", result.completion_tokens)
                )


def update_mock_error(request, error: Exception) -> None:
    """Update properties when a mock error occurs."""
    update_property(request, "actual", f"Mock data error: {str(error)}")
    request.node.user_properties.append(("mock_data_failure", True))
