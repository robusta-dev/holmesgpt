from pathlib import Path
import pytest
from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import ToolCallingLLM
from holmes.core.tools import ToolExecutor
from tests.mock_toolset import MockToolsets

from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, ContextualPrecisionMetric, ContextualRecallMetric, ContextualRelevancyMetric

from tests.utils import AskHolmesTestCase, load_ask_holmes_test_cases

TEST_CASES_FOLDER = Path("tests/fixtures/test_chat")

test_cases = load_ask_holmes_test_cases(TEST_CASES_FOLDER)

@pytest.mark.parametrize("test_case", test_cases, ids=[test_case.id for test_case in test_cases])
def test_ask_holmes_with_tags(test_case:AskHolmesTestCase):

    mock = MockToolsets(tools_passthrough=test_case.tools_passthrough, test_case_folder=test_case.folder)
    print("**", str(test_case))
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
    llm_call = ai.messages_call(messages=messages)

    deepeval_test_case = LLMTestCase(
        name=f"ask_holmes:{test_case.id}",
        input=test_case.user_prompt,
        actual_output=llm_call.result or "",
        expected_output=test_case.expected_output,
        retrieval_context=test_case.retrieval_context,
        tools_called=[tool_call.tool_name for tool_call in (llm_call.tool_calls or [])],
        expected_tools=expected_tools
    )
    assert_test(deepeval_test_case, [
        AnswerRelevancyMetric(
            threshold=test_case.evaluation.answer_relevancy,
            model="gpt-4o",
            include_reason=True
        ),
        FaithfulnessMetric(
            threshold=test_case.evaluation.faithfulness,
            model="gpt-4o",
            include_reason=True
        ),
        ContextualPrecisionMetric(
            threshold=test_case.evaluation.contextual_precision,
            model="gpt-4o",
            include_reason=True
        ),
        ContextualRecallMetric(
            threshold=test_case.evaluation.contextual_recall,
            model="gpt-4o",
            include_reason=True
        ),
        ContextualRelevancyMetric(
            threshold=test_case.evaluation.contextual_relevancy,
            model="gpt-4o",
            include_reason=True
        )
    ])
