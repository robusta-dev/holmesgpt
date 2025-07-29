# type: ignore
import os
from pathlib import Path
from typing import Optional

import pytest

from holmes.core.investigation_structured_output import DEFAULT_SECTIONS
from holmes.core.tools_utils.tool_executor import ToolExecutor
from holmes.core.tool_calling_llm import IssueInvestigator
from holmes.core.tracing import TracingFactory
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
    MockHelper,
    check_and_skip_test,
)
from tests.llm.utils.property_manager import set_initial_properties, update_test_results
from os import path
from unittest.mock import patch

from tests.llm.utils.tags import add_tags_to_eval
from holmes.core.tracing import SpanType

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_investigate"))
)


class MockConfig(Config):
    def __init__(self, test_case: InvestigateTestCase, tracer, mock_generation_config):
        super().__init__()
        self._test_case = test_case
        self._tracer = tracer
        self._mock_generation_config = mock_generation_config

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        mock = MockToolsetManager(
            test_case_folder=self._test_case.folder,
            mock_generation_config=self._mock_generation_config,
            mock_policy=self._test_case.mock_policy,
        )

        # With the new file-based mock system, mocks are loaded from disk automatically
        # No need to call mock_tool() anymore
        return ToolExecutor(mock.toolsets)

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


def get_test_cases():
    mh = MockHelper(TEST_CASES_FOLDER)

    # dataset_name = braintrust_util.get_dataset_name("investigate")
    # if os.environ.get("UPLOAD_DATASET") and os.environ.get("BRAINTRUST_API_KEY"):
    #     bt_helper = braintrust_util.BraintrustEvalHelper(
    #         project_name=BRAINTRUST_PROJECT, dataset_name=dataset_name
    #     )
    #     bt_helper.upload_test_cases(mh.load_test_cases())

    test_cases = mh.load_investigate_test_cases()
    iterations = int(os.environ.get("ITERATIONS", "1"))
    return [add_tags_to_eval(test_case) for test_case in test_cases] * iterations


def idfn(val):
    if isinstance(val, InvestigateTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.parametrize("test_case", get_test_cases(), ids=idfn)
def test_investigate(
    test_case: InvestigateTestCase,
    caplog,
    request,
    mock_generation_config,
    shared_test_infrastructure,  # type: ignore
):
    # Set initial properties early so they're available even if test fails
    set_initial_properties(request, test_case)

    # Check if test should be skipped
    check_and_skip_test(test_case)

    # Check for setup failures
    setup_failures = shared_test_infrastructure.get("setup_failures", {})
    if test_case.id in setup_failures:
        request.node.user_properties.append(("is_setup_failure", True))
        pytest.fail(f"Test setup failed: {setup_failures[test_case.id]}")

    tracer = TracingFactory.create_tracer("braintrust")
    config = MockConfig(test_case, tracer, mock_generation_config)
    config.model = os.environ.get("MODEL", "gpt-4o")
    metadata = {"model": config.model or "Unknown"}
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

    with patch.dict(
        os.environ, {"HOLMES_STRUCTURED_OUTPUT_CONVERSION_FEATURE_FLAG": "False"}
    ):
        with tracer.start_trace(
            name=test_case.id, span_type=SpanType.EVAL
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
                with eval_span.start_span("Holmes Run", type=SpanType.LLM):
                    result = investigate_issues(
                        investigate_request=investigate_request,
                        config=config,
                        dal=mock_dal,
                    )
    assert result, "No result returned by investigate_issues()"

    output = result.analysis

    scores = {}

    debug_expected = "\n-  ".join(expected)

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
        eval_span.log(
            input=input,
            output=output or "",
            expected=str(expected),
            dataset_record_id=test_case.id,
            scores=scores,
            tags=test_case.tags,
        )
    tools_called = [t.tool_name for t in result.tool_calls]
    print(f"\n** TOOLS CALLED **\n{tools_called}")
    print(f"\n** OUTPUT **\n{output}")
    print(f"\n** SCORES **\n{scores}")

    # Store data for summary plugin
    # Update test results
    update_test_results(request, output, tools_called, scores)

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
