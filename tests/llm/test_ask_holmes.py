from pathlib import Path
import os
import pytest

from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
import tests.llm.utils.braintrust as braintrust_util
from tests.llm.utils.classifiers import get_context_classifier
from tests.llm.utils.commands import after_test, before_test
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.system import readable_timestamp
from tests.llm.utils.mock_toolset import MockToolsets

from autoevals.llm import Factuality
from tests.llm.utils.mock_utils import AskHolmesTestCase, MockHelper
from tests.llm.utils.system import get_machine_state_tags
from os import path

TEST_CASES_FOLDER = Path(path.abspath(path.join(
    path.dirname(__file__),
    "fixtures", "test_ask_holmes"
)))

system_metadata = get_machine_state_tags()
DATASET_NAME = f"ask_holmes:{system_metadata.get('branch', 'unknown_branch')}"

def get_test_cases():

    experiment_name = f'ask_holmes:{os.environ.get("PYTEST_XDIST_TESTRUNUID", readable_timestamp())}'

    mh = MockHelper(TEST_CASES_FOLDER)

    if os.environ.get('UPLOAD_DATASET'):
        if os.environ.get('BRAINTRUST_API_KEY'):
            bt_helper = braintrust_util.BraintrustEvalHelper(project_name=PROJECT, dataset_name=DATASET_NAME)
            bt_helper.upload_test_cases(mh.load_test_cases())

    test_cases = mh.load_ask_holmes_test_cases()
    return [(experiment_name, test_case) for test_case in test_cases]

def idfn(val):
    if isinstance(val, AskHolmesTestCase):
        return val.id
    else:
        return str(val)

@pytest.mark.llm
@pytest.mark.skipif(not os.environ.get('BRAINTRUST_API_KEY'), reason="BRAINTRUST_API_KEY must be set to run LLM evaluations")
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_ask_holmes_with_braintrust(experiment_name, test_case):

    bt_helper = braintrust_util.BraintrustEvalHelper(project_name=PROJECT, dataset_name=DATASET_NAME)

    eval = bt_helper.start_evaluation(experiment_name, name=test_case.id)

    eval_factuality = Factuality()

    try:
        before_test(test_case)
    except Exception as e:
        after_test(test_case)
        raise e

    try:
        result = ask_holmes(test_case)
    finally:
        after_test(test_case)

    input = test_case.user_prompt
    output = result.result
    expected = test_case.expected_output

    scores = {
        "faithfulness": eval_factuality(output, expected, input=input).score
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


def ask_holmes(test_case:AskHolmesTestCase) -> LLMResult:

    mock = MockToolsets(tools_passthrough=test_case.mocks_passthrough, test_case_folder=test_case.folder)

    expected_tools = []
    if not os.environ.get("RUN_LIVE"):
        for tool_mock in test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

    tool_executor = ToolExecutor(mock.mocked_toolsets)
    ai = ToolCallingLLM(
        tool_executor=tool_executor,
        max_steps=10,
        llm=DefaultLLM("gpt-4o")
    )

    chat_request = ChatRequest(ask=test_case.user_prompt)

    messages = build_chat_messages(
        chat_request.ask, [], ai=ai
    )
    return ai.messages_call(messages=messages)
