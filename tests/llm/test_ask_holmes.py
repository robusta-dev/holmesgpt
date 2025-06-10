# type: ignore
from pathlib import Path
import os
import pytest

from holmes.common.env_vars import load_bool
from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
import tests.llm.utils.braintrust as braintrust_util
from tests.llm.utils.classifiers import evaluate_correctness
from tests.llm.utils.commands import after_test, before_test
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.mock_toolset import MockToolsets
from braintrust.span_types import SpanTypeAttribute
from braintrust import Span
from tests.llm.utils.mock_utils import AskHolmesTestCase, Evaluation, MockHelper
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

    iterations = int(os.environ.get("ITERATIONS", "0"))
    if iterations:
        return [(experiment_name, test_case) for test_case in test_cases] * iterations
    else:
        return [(experiment_name, test_case) for test_case in test_cases]


def idfn(val):
    if isinstance(val, AskHolmesTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_ask_holmes(experiment_name: str, test_case: AskHolmesTestCase):
    dataset_name = braintrust_util.get_dataset_name("ask_holmes")
    bt_helper = braintrust_util.BraintrustEvalHelper(
        project_name=PROJECT, dataset_name=dataset_name
    )

    eval_span = bt_helper.start_evaluation(experiment_name, name=test_case.id)

    try:
        before_test(test_case)
    except Exception as e:
        after_test(test_case)
        raise e

    try:
        result = ask_holmes(test_case, parent_span=eval_span)

        if result.tool_calls:
            for tool_call in result.tool_calls:
                # TODO: mock this instead so span start time & end time will be accurate.
                # Also to include calls to llm spans
                with eval_span.start_span(
                    name=tool_call.tool_name, type=SpanTypeAttribute.TOOL
                ) as tool_span:
                    if isinstance(tool_call.result, dict):
                        tool_span.log(
                            input=tool_call.description,
                            output=tool_call.result.model_dump_json(indent=2),
                            error=tool_call.result.error,
                        )
                    else:
                        tool_span.log(
                            input=tool_call.description,
                            output=tool_call.result,
                            error=tool_call.result.error,
                        )
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

    if bt_helper and eval_span:
        prompt = (
            result.messages[0]["content"]
            if result.messages and len(result.messages) > 0
            else result.prompt
        )
        evaluation_type: str = (
            test_case.evaluation.correctness.type
            if isinstance(test_case.evaluation.correctness, Evaluation)
            else "strict"
        )
        correctness_eval = evaluate_correctness(
            output=output,
            expected_elements=expected,
            parent_span=eval_span,
            evaluation_type=evaluation_type,
        )

        scores["correctness"] = correctness_eval.score

        bt_helper.end_evaluation(
            input=input,
            output=output or "",
            expected=str(expected),
            id=test_case.id,
            scores=scores,
            prompt=prompt,
        )
    if result.tool_calls:
        tools_called = [tc.description for tc in result.tool_calls]
    else:
        tools_called = "None"
    print(f"\n** TOOLS CALLED **\n{tools_called}")
    print(f"\n** OUTPUT **\n{output}")
    print(f"\n** SCORES **\n{scores}")

    if test_case.evaluation.correctness:
        expected_correctness = test_case.evaluation.correctness
        if isinstance(expected_correctness, Evaluation):
            expected_correctness = expected_correctness.expected_score
        assert scores.get("correctness", 0) >= expected_correctness


def ask_holmes(test_case: AskHolmesTestCase, parent_span: Span) -> LLMResult:
    run_live = load_bool("RUN_LIVE", default=False)
    mock = MockToolsets(
        generate_mocks=test_case.generate_mocks,
        test_case_folder=test_case.folder,
        run_live=run_live,
        parent_span=parent_span,
    )

    expected_tools = []
    if not run_live:
        for tool_mock in test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

    tool_executor = ToolExecutor(mock.enabled_toolsets)
    enabled_toolsets = [t.name for t in tool_executor.enabled_toolsets]

    print(f"** ENABLED TOOLSETS **\n{', '.join(enabled_toolsets)}")
    ai = ToolCallingLLM(
        tool_executor=tool_executor,
        max_steps=10,
        llm=DefaultLLM(os.environ.get("MODEL", "gpt-4o")),
    )

    chat_request = ChatRequest(ask=test_case.user_prompt)
    messages = build_chat_messages(
        ask=chat_request.ask, conversation_history=test_case.conversation_history, ai=ai
    )
    return ai.messages_call(messages=messages)
