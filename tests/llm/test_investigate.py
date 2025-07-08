# type: ignore
import os
from pathlib import Path
from typing import Optional

import pytest

from holmes.core.investigation_structured_output import DEFAULT_SECTIONS
from holmes.core.tools_utils.tool_executor import ToolExecutor
import tests.llm.utils.braintrust as braintrust_util
from holmes.config import Config
from holmes.core.investigation import investigate_issues
from holmes.core.supabase_dal import SupabaseDal
from tests.llm.utils.classifiers import (
    evaluate_correctness,
    evaluate_sections,
)
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.system import get_machine_state_tags
from tests.llm.utils.mock_dal import MockSupabaseDal
from tests.llm.utils.mock_toolset import MockToolsets
from tests.llm.utils.mock_utils import Evaluation, InvestigateTestCase, MockHelper
from os import path
from braintrust import Span, SpanTypeAttribute
from unittest.mock import patch

from tests.llm.utils.tags import add_tags_to_eval

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_investigate"))
)


class MockConfig(Config):
    def __init__(self, test_case: InvestigateTestCase, parent_span: Span):
        super().__init__()
        self._test_case = test_case
        self._parent_span = parent_span

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        mock = MockToolsets(
            generate_mocks=self._test_case.generate_mocks,
            test_case_folder=self._test_case.folder,
            parent_span=self._parent_span,
        )

        expected_tools = []
        for tool_mock in self._test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

        return ToolExecutor(mock.enabled_toolsets)


def get_test_cases():
    experiment_name = braintrust_util.get_experiment_name("investigate")
    dataset_name = braintrust_util.get_dataset_name("investigate")

    mh = MockHelper(TEST_CASES_FOLDER)

    if os.environ.get("UPLOAD_DATASET") and os.environ.get("BRAINTRUST_API_KEY"):
        bt_helper = braintrust_util.BraintrustEvalHelper(
            project_name=PROJECT, dataset_name=dataset_name
        )
        bt_helper.upload_test_cases(mh.load_test_cases())

    test_cases = mh.load_investigate_test_cases()

    iterations = int(os.environ.get("ITERATIONS", "0"))
    if iterations:
        test_cases_tuples = []
        for i in range(0, iterations):
            test_cases_tuples.extend(
                [
                    add_tags_to_eval(experiment_name, test_case)
                    for test_case in test_cases
                ]
            )
        return test_cases_tuples
    else:
        return [
            add_tags_to_eval(experiment_name, test_case) for test_case in test_cases
        ]


def idfn(val):
    if isinstance(val, InvestigateTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_investigate(experiment_name: str, test_case: InvestigateTestCase, caplog):
    dataset_name = braintrust_util.get_dataset_name("investigate")
    bt_helper = braintrust_util.BraintrustEvalHelper(
        project_name=PROJECT, dataset_name=dataset_name
    )
    eval_span = bt_helper.start_evaluation(experiment_name, name=test_case.id)

    config = MockConfig(test_case, eval_span)
    config.model = os.environ.get("MODEL", "gpt-4o")

    mock_dal = MockSupabaseDal(
        test_case_folder=Path(test_case.folder),
        generate_mocks=test_case.generate_mocks,
        issue_data=test_case.issue_data,
        resource_instructions=test_case.resource_instructions,
    )

    input = test_case.investigate_request
    expected = test_case.expected_output
    result = None

    metadata = get_machine_state_tags()
    metadata["model"] = config.model or "Unknown"

    investigate_request = test_case.investigate_request
    if not investigate_request.sections:
        investigate_request.sections = DEFAULT_SECTIONS

    with patch.dict(
        os.environ, {"HOLMES_STRUCTURED_OUTPUT_CONVERSION_FEATURE_FLAG": "False"}
    ):
        with eval_span.start_span("Holmes Run", type=SpanTypeAttribute.LLM):
            result = investigate_issues(
                investigate_request=investigate_request, config=config, dal=mock_dal
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

    if bt_helper and eval_span:
        bt_helper.end_evaluation(
            input=input,
            output=output or "",
            expected=str(expected),
            id=test_case.id,
            scores=scores,
            prompt=None,
            tags=test_case.tags,
        )
    tools_called = [t.tool_name for t in result.tool_calls]
    print(f"\n** TOOLS CALLED **\n{tools_called}")
    print(f"\n** OUTPUT **\n{output}")
    print(f"\n** SCORES **\n{scores}")

    assert result.sections, "Missing sections"
    assert (
        len(result.sections) >= len(investigate_request.sections)
    ), f"Received {len(result.sections)} sections but expected {len(investigate_request.sections)}. Received: {result.sections.keys()}"
    for expected_section_title in investigate_request.sections:
        assert (
            expected_section_title in result.sections
        ), f"Expected title {expected_section_title} in sections"

    if test_case.evaluation.correctness:
        expected_correctness = test_case.evaluation.correctness
        if isinstance(expected_correctness, Evaluation):
            expected_correctness = expected_correctness.expected_score
        assert scores.get("correctness", 0) >= expected_correctness

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
