from pathlib import Path
from langfuse import Langfuse
from pydantic import TypeAdapter
import os
import pytest

from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
from tests.llm.utils.braintrust import upload_dataset
from tests.llm.utils.classifiers import get_context_classifier, get_logs_explanation_classifier
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.langfuse import resolve_dataset_item, upload_test_cases
from tests.llm.utils.system import readable_timestamp
from tests.llm.utils.mock_toolset import MockToolsets
from braintrust import Experiment, ReadonlyExperiment

from autoevals.llm import Factuality
import braintrust
from tests.llm.utils.mock_utils import AskHolmesTestCase, MockHelper
from tests.llm.utils.system import get_machine_state_tags
from os import path

TEST_CASES_FOLDER = Path(path.abspath(path.join(
    path.dirname(__file__),
    "fixtures", "test_ask_holmes"
)))

DATASET_NAME = "ask_holmes"

langfuse = Langfuse()

def get_test_cases():
    experiment_name = f"{readable_timestamp()}:gpt-4o-mini"

    mh = MockHelper(TEST_CASES_FOLDER)
    upload_test_cases(mh.load_test_cases(), DATASET_NAME)

    test_cases = mh.load_ask_holmes_test_cases()
    return [(experiment_name, test_case) for test_case in test_cases]

def idfn(val):
    if isinstance(val, AskHolmesTestCase):
        return val.id
    else:
        return str(val)

@pytest.mark.llm
@pytest.mark.skipif(not os.environ.get('BRAINTRUST_API_KEY'), reason="BRAINTRUST_API_KEY must be set to run LLM evaluations")
def test_ask_holmes_with_braintrust():

    mh = MockHelper(TEST_CASES_FOLDER)
    # upload_dataset(
    #     test_cases=mh.load_investigate_test_cases(),
    #     project_name=PROJECT,
    #     dataset_name=DATASET_NAME
    # )

    dataset = braintrust.init_dataset(project=PROJECT, name=DATASET_NAME)
    experiment:Experiment|ReadonlyExperiment = braintrust.init(
        project=PROJECT,
        experiment=f"ask_holmes_{readable_timestamp()}",
        dataset=dataset,
        open=False,
        update=False,
        metadata=get_machine_state_tags())

    if isinstance(experiment, ReadonlyExperiment):
        raise Exception("Experiment must be writable. The above options open=False and update=False ensure this is the case so this exception should never be raised")

    eval_factuality = Factuality()
    test_cases = mh.load_ask_holmes_test_cases()
    # for test_case in test_cases:
    for dataset_row in dataset:
        test_case = TypeAdapter(AskHolmesTestCase).validate_python(dataset_row["metadata"])
        with experiment.start_span(name=test_case.id) as span:

            result = ask_holmes(test_case)

            input = test_case.user_prompt
            output = result.result
            expected = test_case.expected_output

            scores = {
                "faithfulness": eval_factuality(output, expected, input=input).score,
            }

            if len(test_case.retrieval_context) > 0:
                evaluate_context_usage = get_context_classifier(test_case.retrieval_context)
                scores["context"] = evaluate_context_usage(output, expected, input=input).score

            span.log(
                input=input,
                output=output,
                expected=expected,
                dataset_record_id=dataset_row["id"],
                scores=scores
            )

    experiment.flush()


def ask_holmes(test_case:AskHolmesTestCase) -> LLMResult:

    mock = MockToolsets(tools_passthrough=test_case.mocks_passthrough, test_case_folder=test_case.folder)

    expected_tools = []
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
