import os
from pathlib import Path
from typing import Optional

import pytest

from holmes.core.investigation_structured_output import DEFAULT_SECTIONS
import tests.llm.utils.braintrust as braintrust_util
from holmes.config import Config
from holmes.core.investigation import investigate_issues
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import ToolExecutor
from tests.llm.utils.classifiers import (
    evaluate_context_usage,
    evaluate_correctness,
    evaluate_previous_logs_mention,
)
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.system import get_machine_state_tags
from tests.llm.utils.mock_dal import MockSupabaseDal
from tests.llm.utils.mock_toolset import MockToolsets
from tests.llm.utils.mock_utils import InvestigateTestCase, MockHelper
from os import path

system_metadata = get_machine_state_tags()
TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_investigate"))
)

DATASET_NAME = f"investigate:{system_metadata.get('branch', 'unknown_branch')}"


class MockConfig(Config):
    def __init__(self, test_case: InvestigateTestCase):
        super().__init__()
        self._test_case = test_case

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        mock = MockToolsets(
            generate_mocks=self._test_case.generate_mocks,
            test_case_folder=self._test_case.folder,
        )

        expected_tools = []
        for tool_mock in self._test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

        return ToolExecutor(mock.mocked_toolsets)


def get_test_cases():
    experiment_name = braintrust_util.get_experiment_name("investigate")

    mh = MockHelper(TEST_CASES_FOLDER)

    if os.environ.get("UPLOAD_DATASET") and os.environ.get("BRAINTRUST_API_KEY"):
        bt_helper = braintrust_util.BraintrustEvalHelper(
            project_name=PROJECT, dataset_name=DATASET_NAME
        )
        bt_helper.upload_test_cases(mh.load_test_cases())

    test_cases = mh.load_investigate_test_cases()
    return [(experiment_name, test_case) for test_case in test_cases]


def idfn(val):
    if isinstance(val, InvestigateTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.skipif(
    not os.environ.get("BRAINTRUST_API_KEY"),
    reason="BRAINTRUST_API_KEY must be set to run LLM evaluations",
)
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_investigate(experiment_name, test_case):
    config = MockConfig(test_case)
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

    bt_helper = None
    eval = None
    if braintrust_util.PUSH_EVALS_TO_BRAINTRUST:
        bt_helper = braintrust_util.BraintrustEvalHelper(
            project_name=PROJECT, dataset_name=DATASET_NAME
        )
        eval = bt_helper.start_evaluation(experiment_name, name=test_case.id)

    investigate_request = test_case.investigate_request
    investigate_request.sections = DEFAULT_SECTIONS
    result = investigate_issues(
        investigate_request=investigate_request, config=config, dal=mock_dal
    )
    assert result, "No result returned by investigate_issues()"

    output = result.analysis

    scores = {}

    debug_expected = "\n-  ".join(expected)

    print(f"** EXPECTED **\n-  {debug_expected}")

    correctness_eval = evaluate_correctness(output=output, expected_elements=expected)
    print(
        f"\n** CORRECTNESS **\nscore = {correctness_eval.score}\nrationale = {correctness_eval.metadata.get('rationale', '')}"
    )
    scores["correctness"] = correctness_eval.score

    scores["previous_logs"] = evaluate_previous_logs_mention(output=output).score

    if len(test_case.retrieval_context) > 0:
        scores["context"] = evaluate_context_usage(
            input=input, output=output, context_items=test_case.retrieval_context
        ).score

    if bt_helper and eval:
        bt_helper.end_evaluation(
            eval=eval,
            input=input,
            output=output or "",
            expected=str(expected),
            id=test_case.id,
            scores=scores,
        )
    tools_called = [t.tool_name for t in result.tool_calls]
    print(f"\n** TOOLS CALLED **\n{tools_called}")
    print(f"\n** OUTPUT **\n{output}")
    print(f"\n** SCORES **\n{scores}")

    assert result.sections, "Missing sections"
    assert (
        len(result.sections) >= len(DEFAULT_SECTIONS)
    ), f"Received {len(result.sections)} sections but expected {len(DEFAULT_SECTIONS)}. Received: {result.sections.keys()}"
    for expected_section_title in DEFAULT_SECTIONS:
        assert (
            expected_section_title in result.sections
        ), f"Expected title {expected_section_title} in sections"

    if test_case.expected_sections:
        for (
            expected_section_title,
            expected_section_array_content,
        ) in test_case.expected_sections.items():
            assert (
                expected_section_title in result.sections
            ), f"Expected to see section [{expected_section_title}] in result but that section is missing"
            for expected_content in expected_section_array_content:
                assert (
                    expected_content in result.sections.get(expected_section_title, "")
                ), f"Expected to see content [{expected_content}] in section [{expected_section_title}] but could not find such content"

    if test_case.evaluation.correctness:
        assert scores.get("correctness", 0) >= test_case.evaluation.correctness
