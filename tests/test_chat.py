from pathlib import Path
from typing import Any, Dict, List
from litellm.types.utils import Tuple
from pydantic import TypeAdapter
import random
import string

from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
from tests.mock_toolset import MockToolsets
from braintrust import Eval, EvalCase, Experiment, ReadonlyExperiment

from autoevals.llm import Factuality, Battle
import braintrust
from datetime import datetime
from tests.mock_utils import AskHolmesTestCase, load_ask_holmes_test_cases
from tests.utils import get_machine_state_tags

TEST_CASES_FOLDER = Path("tests/fixtures/test_chat")

test_cases = load_ask_holmes_test_cases(TEST_CASES_FOLDER)

pydantic_test_case = TypeAdapter(AskHolmesTestCase)

from autoevals import LLMClassifier
eval_factuality = Factuality()


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

PROJECT="HolmesGPT"
DATASET_NAME = "ask_holmes"

def _test_upload_dataset():
    dataset = braintrust.init_dataset(project=PROJECT, name=DATASET_NAME)

    for test_case in test_cases:
        id = dataset.insert(
            id=f"ask_holmes_{test_case.id}",
            input=test_case.user_prompt,
            expected=test_case.expected_output,
            metadata=test_case.model_dump(),
            tags=["common","holmesgpt","ask_holmes","basic"],
        )
        print("Inserted record with id", id)

    print(dataset.summarize())

pydantic_test_case = TypeAdapter(AskHolmesTestCase)


def test_ask_holmes():

    dataset = braintrust.init_dataset(project=PROJECT, name=DATASET_NAME)
    experiment:Experiment|ReadonlyExperiment = braintrust.init(
        project=PROJECT,
        experiment="ask_holmes",
        dataset=dataset,
        open=False,
        update=False,
        metadata=get_machine_state_tags())

    if isinstance(experiment, ReadonlyExperiment):
        raise Exception("Experiment must be writable. The above options open=False and update=False ensure this is the case so this exception should never be raised")

    for dataset_row in dataset:
        test_case = pydantic_test_case.validate_python(dataset_row["metadata"])

        span = experiment.start_span(name=f"test_ask_holmes:{test_case.id}")
        result = ask_holmes(test_case)
        span.end()

        input = test_case.user_prompt
        output = result.result
        expected = test_case.expected_output

        span.log(
            input=input,
            output=output,
            expected=expected,
            dataset_record_id=dataset_row["id"],
            scores={
                "faithfulness": eval_factuality(output, expected, input=input).score
            }
        )

    experiment.flush()


def ask_holmes(test_case:AskHolmesTestCase) -> LLMResult:

    mock = MockToolsets(tools_passthrough=test_case.tools_passthrough, test_case_folder=test_case.folder)

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
