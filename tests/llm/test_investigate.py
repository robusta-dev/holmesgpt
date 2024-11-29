
import os
from pathlib import Path
from typing import Optional

import pytest
from rich.console import Console

import tests.llm.utils.braintrust as braintrust_util
from holmes.config import Config
from holmes.core.investigation import investigate_issues
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import ToolExecutor, ToolsetPattern
from tests.llm.utils.classifiers import evaluate_context_usage, evaluate_correctness, evaluate_factuality, evaluate_previous_logs_mention
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.system import get_machine_state_tags, readable_timestamp
from tests.llm.utils.mock_dal import MockSupabaseDal
from tests.llm.utils.mock_toolset import MockToolsets
from tests.llm.utils.mock_utils import InvestigateTestCase, MockHelper
from os import path

system_metadata = get_machine_state_tags()
TEST_CASES_FOLDER = Path(path.abspath(path.join(
    path.dirname(__file__),
    "fixtures", "test_investigate"
)))

DATASET_NAME = f"investigate:{system_metadata.get('branch', 'unknown_branch')}"

class MockConfig(Config):
    def __init__(self, test_case:InvestigateTestCase):
        super().__init__()
        self._test_case = test_case

    def create_tool_executor(
        self, console: Console, allowed_toolsets: ToolsetPattern, dal:Optional[SupabaseDal]
    ) -> ToolExecutor:

        mock = MockToolsets(generate_mocks=self._test_case.generate_mocks, test_case_folder=self._test_case.folder)

        expected_tools = []
        for tool_mock in self._test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

        return ToolExecutor(mock.mocked_toolsets)

def get_test_cases():

    unique_test_id = os.environ.get("PYTEST_XDIST_TESTRUNUID", readable_timestamp())
    experiment_name = f'investigate:{unique_test_id}'
    if os.environ.get("EXPERIMENT_ID"):
        experiment_name = f'investigate:{os.environ.get("EXPERIMENT_ID")}'

    mh = MockHelper(TEST_CASES_FOLDER)

    if os.environ.get('UPLOAD_DATASET'):
        if os.environ.get('BRAINTRUST_API_KEY'):
            bt_helper = braintrust_util.BraintrustEvalHelper(project_name=PROJECT, dataset_name=DATASET_NAME)
            bt_helper.upload_test_cases(mh.load_test_cases())

    test_cases = mh.load_investigate_test_cases()
    return [(experiment_name, test_case) for test_case in test_cases]

def idfn(val):
    if isinstance(val, InvestigateTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.skipif(not os.environ.get('BRAINTRUST_API_KEY'), reason="BRAINTRUST_API_KEY must be set to run LLM evaluations")
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_investigate(experiment_name, test_case):

    config = MockConfig(test_case)
    mock_dal = MockSupabaseDal(
        test_case_folder=Path(test_case.folder),
        generate_mocks=test_case.generate_mocks,
        issue_data=test_case.issue_data,
        resource_instructions=test_case.resource_instructions
    )

    input = test_case.investigate_request
    expected = test_case.expected_output
    result = None

    metadata = get_machine_state_tags()
    metadata["model"] = config.model or "Unknown"

    bt_helper = braintrust_util.BraintrustEvalHelper(project_name=PROJECT, dataset_name=DATASET_NAME)

    eval = bt_helper.start_evaluation(experiment_name, name=test_case.id)

    result = investigate_issues(
        investigate_request=test_case.investigate_request,
        config=config,
        dal=mock_dal,
        console=Console()
    )
    assert result

    output = result.analysis

    scores = {}

    if isinstance(expected, list):
        scores["correctness"] = evaluate_correctness(output=output, expected_elements=expected).score
    else:
        scores["faithfulness"] = evaluate_factuality(output=output, expected=expected, input=input).score
    scores["previous_logs"] = evaluate_previous_logs_mention(output=output).score

    if len(test_case.retrieval_context) > 0:
            scores["context"] = evaluate_context_usage(input=input, output=output, context_items=test_case.retrieval_context).score

    bt_helper.end_evaluation(
        eval=eval,
        input=input,
        output=output or "",
        expected=str(expected),
        id=test_case.id,
        scores=scores
    )
    print(f"** OUTPUT **\n{output}")
    print(f"** SCORES **\n{scores}")

    if scores.get("faithfulness"):
        assert scores.get("faithfulness") >= test_case.evaluation.faithfulness

    if scores.get("correctness"):
        assert scores.get("correctness") >= test_case.evaluation.correctness
    assert scores.get("context", 0) >= test_case.evaluation.context
