from pathlib import Path
import os
import pytest

from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
import tests.llm.utils.braintrust as braintrust_util
from tests.llm.utils.classifiers import evaluate_context_usage, evaluate_correctness
from tests.llm.utils.commands import after_test, before_test
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.mock_toolset import MockToolsets
from braintrust.span_types import SpanTypeAttribute
from tests.llm.utils.mock_utils import AskHolmesTestCase, MockHelper
from os import path

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_ask_holmes"))
)


def get_test_cases():
    experiment_name = braintrust_util.get_experiment_name("ask_holmes")
    dataset_name = braintrust_util.get_dataset_name("ask_holmes")

    mh = MockHelper(TEST_CASES_FOLDER)

    if os.environ.get("UPLOAD_DATASET") and os.environ.get("BRAINTRUST_API_KEY"):
        bt_helper = braintrust_util.BraintrustEvalHelper(
            project_name=PROJECT, dataset_name=dataset_name
        )
        bt_helper.upload_test_cases(mh.load_test_cases())
    test_cases = mh.load_ask_holmes_test_cases()
    return [(experiment_name, test_case) for test_case in test_cases]


def idfn(val):
    if isinstance(val, AskHolmesTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.skipif(
    not os.environ.get("BRAINTRUST_API_KEY"),
    reason="BRAINTRUST_API_KEY must be set to run LLM evaluations",
)
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_ask_holmes(experiment_name, test_case):
    bt_helper = None
    eval = None
    dataset_name = braintrust_util.get_dataset_name("ask_holmes")
    if braintrust_util.PUSH_EVALS_TO_BRAINTRUST:
        bt_helper = braintrust_util.BraintrustEvalHelper(
            project_name=PROJECT, dataset_name=dataset_name
        )

        eval = bt_helper.start_evaluation(experiment_name, name=test_case.id)

    try:
        before_test(test_case)
    except Exception as e:
        after_test(test_case)
        raise e

    try:
        result: LLMResult = ask_holmes(test_case)
        for tool_call in result.tool_calls:
            with eval.start_span(
                name=tool_call.tool_name, type=SpanTypeAttribute.TOOL
            ) as tool_span:
                tool_span.log(input=tool_call.description, output=tool_call.result)
    finally:
        after_test(test_case)

    input = test_case.user_prompt
    output = result.result
    expected = test_case.expected_output

    scores = {}

    if not isinstance(expected, list):
        expected = [expected]

    debug_expected = "\n-  ".join(expected)
    print(f"** EXPECTED **\n-  {debug_expected}")
    with eval.start_span(
        name="Correctness", type=SpanTypeAttribute.SCORE
    ) as correctness_span:
        correctness_eval = evaluate_correctness(
            output=output, expected_elements=expected
        )
        print(
            f"\n** CORRECTNESS **\nscore = {correctness_eval.score}\nrationale = {correctness_eval.metadata.get('rationale', '')}"
        )
        scores["correctness"] = correctness_eval.score
        correctness_span.log(
            scores={
                "correctness": correctness_eval.score,
            },
            # This will merge the metadata from the factuality score with the
            # metadata from the tree.
            metadata={"correctness": correctness_eval.metadata},
        )
    if len(test_case.retrieval_context) > 0:
        with eval.start_span(
            name="Context", type=SpanTypeAttribute.SCORE
        ) as context_span:
            context_eval = evaluate_context_usage(
                output=output, context_items=test_case.retrieval_context, input=input
            )
            scores["context"] = context_eval.score
            context_span.log(
                scores={
                    "context": context_eval.score,
                },
                metadata={"context": context_eval.metadata},
            )

    if bt_helper and eval:
        bt_helper.end_evaluation(
            eval=eval,
            input=input,
            output=output or "",
            expected=str(expected),
            id=test_case.id,
            scores=scores,
        )
    if result.tool_calls:
        tools_called = [t.tool_name for t in result.tool_calls]
    else:
        tools_called = "None"
    print(f"\n** TOOLS CALLED **\n{tools_called}")
    print(f"\n** OUTPUT **\n{output}")
    print(f"\n** SCORES **\n{scores}")

    if test_case.evaluation.correctness:
        assert scores.get("correctness", 0) >= test_case.evaluation.correctness


def ask_holmes(test_case: AskHolmesTestCase) -> LLMResult:
    mock = MockToolsets(
        generate_mocks=test_case.generate_mocks, test_case_folder=test_case.folder
    )

    expected_tools = []
    if not os.environ.get("RUN_LIVE"):
        for tool_mock in test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

    tool_executor = ToolExecutor(mock.mocked_toolsets)

    ai = ToolCallingLLM(
        tool_executor=tool_executor,
        max_steps=10,
        llm=DefaultLLM(os.environ.get("MODEL", "gpt-4o")),
    )

    chat_request = ChatRequest(ask=test_case.user_prompt)

    messages = build_chat_messages(chat_request.ask, [], ai=ai)
    return ai.messages_call(messages=messages)
