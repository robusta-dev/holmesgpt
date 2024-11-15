from pathlib import Path
from typing import List
from pydantic import TypeAdapter
import os
import pytest

from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
from tests.mock_toolset import MockToolsets
from braintrust import Experiment, ReadonlyExperiment

from autoevals.llm import Factuality
import braintrust
from datetime import datetime
from tests.mock_utils import AskHolmesTestCase, load_ask_holmes_test_cases
from tests.utils import get_machine_state_tags
from autoevals import LLMClassifier

TEST_CASES_FOLDER = Path("tests/fixtures/test_chat")

test_cases = load_ask_holmes_test_cases(TEST_CASES_FOLDER)

pydantic_test_case = TypeAdapter(AskHolmesTestCase)

def get_context_classifier(context_items:List[str]):
    context = "\n- ".join(context_items)
    prompt_prefix = f"""
CONTEXT
-------
{context}


QUESTION
--------
{{{{input}}}}


ANSWER
------
{{{{output}}}}


Evaluate whether the ANSWER to the QUESTION refers to all items mentioned in the CONTEXT.
Then evaluate which of the following statement is match the closest and return the corresponding letter:

A. No item mentioned in the CONTEXT is mentioned in the ANSWER
B. Less than half of items present in the CONTEXT are mentioned in the ANSWER
C. More than half of items present in the CONTEXT are mentioned in the ANSWER
D. All items present in the CONTEXT are mentioned in the ANSWER
    """

    return LLMClassifier(
        name="ContextPrecision",
        prompt_template=prompt_prefix,
        choice_scores={"A": 0, "B": 0.33, "C": 0.67, "D": 1},
        use_cot=True,
    )


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

@pytest.mark.skipif(not os.environ.get('BRAINTRUST_API_KEY'), reason="BRAINTRUST_API_KEY must be set to run LLM evaluations")
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


    eval_factuality = Factuality()
    for dataset_row in dataset:
        test_case = pydantic_test_case.validate_python(dataset_row["metadata"])

        span = experiment.start_span(name=f"test_ask_holmes:{test_case.id}")
        result = ask_holmes(test_case)
        span.end()

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
