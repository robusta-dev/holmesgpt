# type: ignore
import os
import time
from pathlib import Path
from typing import Optional

import pytest

from holmes.core.investigation_structured_output import DEFAULT_SECTIONS
from holmes.core.tools_utils.tool_executor import ToolExecutor
from holmes.core.tool_calling_llm import IssueInvestigator
from holmes.core.tracing import TracingFactory, SpanType
from holmes.config import Config
from holmes.core.investigation import investigate_issues
from holmes.core.supabase_dal import SupabaseDal
from tests.llm.utils.classifiers import (
    evaluate_correctness,
    evaluate_sections,
)
from tests.llm.utils.commands import set_test_env_vars
from tests.llm.utils.mock_dal import MockSupabaseDal
from tests.llm.utils.mock_toolset import MockToolsetManager
from tests.llm.utils.test_case_utils import (
    InvestigateTestCase,
    check_and_skip_test,
)
from tests.llm.utils.property_manager import set_initial_properties, update_test_results
from os import path
from unittest.mock import patch

from tests.llm.utils.iteration_utils import get_test_cases
from tests.llm.utils.braintrust import log_to_braintrust

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_investigate"))
)


class MockConfig(Config):
    def __init__(self, test_case: InvestigateTestCase, tracer, mock_generation_config):
        super().__init__()
        self._test_case = test_case
        self._tracer = tracer
        self._mock_generation_config = mock_generation_config
        self._cached_tool_executor: Optional[ToolExecutor] = None

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        if not self._cached_tool_executor:
            mock = MockToolsetManager(
                test_case_folder=self._test_case.folder,
                mock_generation_config=self._mock_generation_config,
                mock_policy=self._test_case.mock_policy,
            )

            # With the new file-based mock system, mocks are loaded from disk automatically
            # No need to call mock_tool() anymore
            self._cached_tool_executor = ToolExecutor(mock.toolsets)
        return self._cached_tool_executor

    def create_issue_investigator(
        self,
        dal: Optional[SupabaseDal] = None,
        model: Optional[str] = None,
        tracer=None,
    ) -> IssueInvestigator:
        # Use our tracer instead of the passed one
        return super().create_issue_investigator(
            dal=dal, model=model, tracer=self._tracer
        )


def get_investigate_test_cases():
    return get_test_cases(TEST_CASES_FOLDER)


def get_models():
    """Get list of models to test from MODELS env var."""
    models_str = os.environ.get("MODELS", "gpt-4o")
    return models_str.split(",")


@pytest.mark.llm
@pytest.mark.parametrize("model", get_models())
@pytest.mark.parametrize("test_case", get_investigate_test_cases())
def test_investigate(
    model: str,
    test_case: InvestigateTestCase,
    caplog,
    request,
    mock_generation_config,
    shared_test_infrastructure,  # type: ignore
):
    # Set initial properties early so they're available even if test fails
    set_initial_properties(request, test_case)

    # Add model to user properties for reporting
    request.node.user_properties.append(("model", model))
    # Add clean test case ID (without model suffix)
    request.node.user_properties.append(("clean_test_case_id", test_case.id))
    # Add tags for tag-based performance analysis
    request.node.user_properties.append(("tags", test_case.tags or []))

    # Check if test should be skipped
    check_and_skip_test(test_case)

    # Check for setup failures
    setup_failures = shared_test_infrastructure.get("setup_failures", {})
    if test_case.id in setup_failures:
        request.node.user_properties.append(("is_setup_failure", True))
        pytest.fail(f"Test setup failed: {setup_failures[test_case.id]}")

    tracer = TracingFactory.create_tracer("braintrust")
    config = MockConfig(test_case, tracer, mock_generation_config)
    config.model = model
    metadata = {"model": model}
    tracer.start_experiment(additional_metadata=metadata)

    mock_dal = MockSupabaseDal(
        test_case_folder=Path(test_case.folder),
        generate_mocks=mock_generation_config.generate_mocks,
        issue_data=test_case.issue_data,
        resource_instructions=test_case.resource_instructions,
    )

    input = test_case.investigate_request
    expected = test_case.expected_output
    result = None

    investigate_request = test_case.investigate_request
    if not investigate_request.sections:
        investigate_request.sections = DEFAULT_SECTIONS

    try:
        with patch.dict(
            os.environ, {"HOLMES_STRUCTURED_OUTPUT_CONVERSION_FEATURE_FLAG": "False"}
        ):
            with tracer.start_trace(
                name=f"{test_case.id}[{model}]", span_type=SpanType.EVAL
            ) as eval_span:
                # Store span info in user properties for conftest to access
                if hasattr(eval_span, "id"):
                    request.node.user_properties.append(
                        ("braintrust_span_id", str(eval_span.id))
                    )
                if hasattr(eval_span, "root_span_id"):
                    request.node.user_properties.append(
                        ("braintrust_root_span_id", str(eval_span.root_span_id))
                    )

                with set_test_env_vars(test_case):
                    with eval_span.start_span(
                        "Caching tools executor for create_issue_investigator",
                        type=SpanType.TASK.value,
                    ):
                        config.create_tool_executor(mock_dal)
                    with eval_span.start_span(
                        "Holmes Run", type=SpanType.TASK.value
                    ) as holmes_span:
                        start_time = time.time()
                        result = investigate_issues(
                            investigate_request=investigate_request,
                            config=config,
                            dal=mock_dal,
                            trace_span=holmes_span,
                        )
                        holmes_duration = time.time() - start_time
                    # Log duration directly to eval_span
                    eval_span.log(metadata={"holmes_duration": holmes_duration})
    except Exception as e:
        # Log error to span if available
        try:
            if "eval_span" in locals():
                log_to_braintrust(
                    eval_span=eval_span,
                    test_case=test_case,
                    model=model,
                    result=result,
                    error=e,
                    mock_generation_config=mock_generation_config,
                )
        except Exception:
            pass  # Don't fail the test due to logging issues

        # Store error information in user_properties for reporting
        error_type = type(e).__name__
        error_message = str(e)
        request.node.user_properties.append(("error_type", error_type))
        request.node.user_properties.append(("error_message", error_message))

        # Store partial result if available
        if result and hasattr(result, "analysis"):
            request.node.user_properties.append(
                ("partial_output", result.analysis or "")
            )

        # Check if this is a MockDataError
        is_mock_error = "MockDataError" in error_type or any(
            "MockData" in base.__name__ for base in type(e).__mro__
        )

        if is_mock_error:
            # Update properties for mock error (would need to import update_mock_error)
            from tests.llm.utils.property_manager import update_mock_error

            update_mock_error(request, e)

        raise

    assert result, "No result returned by investigate_issues()"

    output = result.analysis

    scores = {}

    debug_expected = "\n-  ".join(expected)

    print(f"\n🧪 TEST: {test_case.id}")
    print(f"   • Model: {model}")
    print(f"** EXPECTED **\n-  {debug_expected}")
    correctness_eval = evaluate_correctness(
        output=output,
        expected_elements=expected,
        parent_span=eval_span,
        caplog=caplog,
        evaluation_type="strict",
    )
    print(
        f"\n** CORRECTNESS **\nscore = {correctness_eval.score}\nrationale = {correctness_eval.metadata.get('rationale', '')}"
    )
    scores["correctness"] = correctness_eval.score

    if test_case.expected_sections:
        sections = {
            key: bool(value) for key, value in test_case.expected_sections.items()
        }
        sections_eval = evaluate_sections(
            sections=sections, output=output, parent_span=eval_span
        )
        scores["sections"] = sections_eval.score

    # Log evaluation results directly to the span
    if eval_span:
        log_to_braintrust(
            eval_span=eval_span,
            test_case=test_case,
            model=model,
            result=result,
            scores=scores,
            mock_generation_config=mock_generation_config,
        )
    tools_called = [t.tool_name for t in result.tool_calls]
    print(f"\n** TOOLS CALLED **\n{tools_called}")
    print(f"\n** OUTPUT **\n{output}")
    print(f"\n** SCORES **\n{scores}")

    # Store data for summary plugin
    # Update test results (including cost tracking)
    update_test_results(request, output, tools_called, scores, result)

    assert result.sections, "Missing sections"
    assert (
        len(result.sections) >= len(investigate_request.sections)
    ), f"Received {len(result.sections)} sections but expected {len(investigate_request.sections)}. Received: {result.sections.keys()}"
    for expected_section_title in investigate_request.sections:
        assert (
            expected_section_title in result.sections
        ), f"Expected title {expected_section_title} in sections"

    assert (
        int(scores.get("correctness", 0)) == 1
    ), f"Test {test_case.id} failed (score: {scores.get('correctness', 0)})"

    if test_case.expected_sections:
        for (
            expected_section_title,
            expected_section_array_content,
        ) in test_case.expected_sections.items():
            if expected_section_array_content:
                assert (
                    expected_section_title in result.sections
                ), f"Expected to see section [{expected_section_title}] in result but that section is missing"
                for expected_content in expected_section_array_content:
                    assert (
                        expected_content
                        in result.sections.get(expected_section_title, "")
                    ), f"Expected to see content [{expected_content}] in section [{expected_section_title}] but could not find such content"
