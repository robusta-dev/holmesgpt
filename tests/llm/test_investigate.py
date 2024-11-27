
import os
from pathlib import Path
from typing import Optional

from autoevals import Factuality
import pytest
from rich.console import Console

import tests.llm.utils.braintrust as braintrust_util
from holmes.config import Config
from holmes.core.investigation import investigate_issues
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import ToolExecutor, ToolsetPattern
from tests.llm.utils.classifiers import get_context_classifier, get_logs_explanation_classifier
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

        mock = MockToolsets(tools_passthrough=self._test_case.mocks_passthrough, test_case_folder=self._test_case.folder)

        expected_tools = []
        for tool_mock in self._test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

        return ToolExecutor(mock.mocked_toolsets)



def get_test_cases():
    experiment_name = f'investigate:{os.environ.get("PYTEST_XDIST_TESTRUNUID", readable_timestamp())}'

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

    eval_factuality = Factuality()

    config = MockConfig(test_case)
    mock_dal = MockSupabaseDal(
        test_case_folder=Path(test_case.folder),
        dal_passthrough=test_case.mocks_passthrough,
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

    evaluate_logs_explanation = get_logs_explanation_classifier()
    factuality = eval_factuality(output, expected, input=input)
    previous_logs = evaluate_logs_explanation(output, expected, input=input)
    scores = {
        "faithfulness": factuality.score,
        "previous_logs": previous_logs.score
    }

    if len(test_case.retrieval_context) > 0:
            evaluate_context_usage = get_context_classifier(test_case.retrieval_context)
            scores["context"] = evaluate_context_usage(output, expected, input=input).score

    bt_helper.end_evaluation(
        eval=eval,
        input=input,
        output=output or "",
        expected=expected,
        id=test_case.id,
        scores=scores
    )
    print(f"** OUTPUT **\n{output}")
    print(f"** SCORES **\n{scores}")

    assert scores.get("faithfulness") >= test_case.evaluation.faithfulness
    assert scores.get("context", 0) >= test_case.evaluation.context
