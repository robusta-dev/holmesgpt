from typing import List, Any, Union, Optional, Dict
from tests.llm.utils.test_case_utils import Evaluation, HolmesTestCase  # type: ignore[attr-defined]


def set_initial_properties(request, test_case: HolmesTestCase, model: str) -> None:
    """Set initial properties at the beginning of a test so they're available even if test fails early.

    Args:
        request: The pytest request object
        test_case: The test case being executed
        model: The model being used for this test run
    """
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

    # Add model and test identification properties
    request.node.user_properties.append(("model", model))
    # Add clean test case ID (without model suffix that pytest adds during parameterization)
    request.node.user_properties.append(("clean_test_case_id", test_case.id))
    # Add tags for tag-based performance analysis
    request.node.user_properties.append(("tags", test_case.tags or []))


def set_trace_properties(request, eval_span) -> None:
    """Set Braintrust trace properties for test reporting.

    Args:
        request: The pytest request object
        eval_span: The Braintrust evaluation span
    """
    if hasattr(eval_span, "id"):
        request.node.user_properties.append(("braintrust_span_id", str(eval_span.id)))
    if hasattr(eval_span, "root_span_id"):
        request.node.user_properties.append(
            ("braintrust_root_span_id", str(eval_span.root_span_id))
        )


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
    scores: Optional[Dict[str, Any]] = None,
    result: Any = None,
    test_case: Any = None,
    eval_span: Any = None,
    caplog: Any = None,
) -> Dict[str, Any]:
    """Update test result properties after test execution and optionally calculate scores.

    Args:
        request: The pytest request object
        output: The test output string
        tools_called: List of tools called or a string description
        scores: Dictionary of scores (e.g., correctness). If None and test_case is provided, will calculate
        result: Optional result object (LLMResult or InvestigationResult) containing cost info
        test_case: Optional test case for score calculation
        eval_span: Optional Braintrust span for evaluation
        caplog: Optional caplog for evaluation

    Returns:
        dict: The scores dictionary (either passed in or calculated)
    """
    # Calculate scores if not provided but test_case is available
    if scores is None and test_case is not None:
        from tests.llm.utils.classifiers import evaluate_correctness, evaluate_sections

        scores = {}

        # Get expected output
        expected = test_case.expected_output
        if not isinstance(expected, list):
            expected = [expected]

        # Determine evaluation type
        evaluation_type = "strict"
        if hasattr(test_case, "evaluation") and hasattr(
            test_case.evaluation, "correctness"
        ):
            if isinstance(test_case.evaluation.correctness, Evaluation):
                evaluation_type = test_case.evaluation.correctness.type

        # Evaluate correctness
        correctness_eval = evaluate_correctness(
            output=output,
            expected_elements=expected,
            parent_span=eval_span,
            evaluation_type=evaluation_type,
            caplog=caplog,
        )
        scores["correctness"] = correctness_eval.score

        # Evaluate sections if applicable (for investigate tests)
        if hasattr(test_case, "expected_sections") and test_case.expected_sections:
            sections = {
                key: bool(value) for key, value in test_case.expected_sections.items()
            }
            sections_eval = evaluate_sections(
                sections=sections, output=output, parent_span=eval_span
            )
            scores["sections"] = sections_eval.score

    # Default scores if still None
    if scores is None:
        scores = {}

    # Update properties
    update_property(request, "actual", output or "")
    update_property(
        request,
        "tools_called",
        tools_called if isinstance(tools_called, list) else [str(tools_called)],
    )
    update_property(request, "actual_correctness_score", scores.get("correctness", 0))

    if not result:
        return scores

    # Track cost and token usage from LLMResult
    # Tokens are useful even when cost is 0 (e.g., local or free-tier runs)
    # Record token counts when present regardless of total_cost
    if hasattr(result, "total_cost") or hasattr(result, "total_tokens"):
        # Always record cost if present (even if 0)
        if hasattr(result, "total_cost"):
            request.node.user_properties.append(("cost", result.total_cost))
        # Always record tokens if present
        if hasattr(result, "total_tokens"):
            request.node.user_properties.append(("total_tokens", result.total_tokens))
        if hasattr(result, "prompt_tokens"):
            request.node.user_properties.append(("prompt_tokens", result.prompt_tokens))
        if hasattr(result, "completion_tokens"):
            request.node.user_properties.append(
                ("completion_tokens", result.completion_tokens)
            )

    return scores


def update_mock_error(request, error: Exception) -> None:
    """Update properties when a mock error occurs."""
    update_property(request, "actual", f"Mock data error: {str(error)}")
    request.node.user_properties.append(("mock_data_failure", True))


def handle_test_error(
    request,
    error: Exception,
    eval_span=None,
    test_case=None,
    model: Optional[str] = None,
    result=None,
    mock_generation_config=None,
) -> None:
    """Centralized error handling for LLM tests.

    Args:
        request: The pytest request object
        error: The exception that was raised
        eval_span: Optional Braintrust evaluation span for logging
        test_case: The test case being executed
        model: The model being tested
        result: Optional partial result if available
        mock_generation_config: Mock configuration for logging
    """
    # Import here to avoid circular dependency
    from tests.llm.utils.braintrust import log_to_braintrust

    # Log error to Braintrust span if available
    if eval_span is not None and test_case is not None and model is not None:
        try:
            log_to_braintrust(
                eval_span=eval_span,
                test_case=test_case,
                model=model,
                result=result,
                error=error,
                mock_generation_config=mock_generation_config,
            )
        except Exception:
            pass  # Don't fail the test due to logging issues

    # Store error information in user_properties for reporting
    error_type = type(error).__name__
    error_message = str(error)
    request.node.user_properties.append(("error_type", error_type))
    request.node.user_properties.append(("error_message", error_message))

    # Store partial result if available
    if result:
        partial_output = (
            getattr(result, "result", "") or getattr(result, "output", "") or ""
        )
        if partial_output:
            request.node.user_properties.append(("partial_output", partial_output))

    # Check if this is a MockDataError
    is_mock_error = "MockDataError" in error_type or any(
        "MockData" in base.__name__ for base in type(error).__mro__
    )

    if is_mock_error:
        # Update properties for mock error
        update_mock_error(request, error)
