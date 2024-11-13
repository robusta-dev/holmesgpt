from pathlib import Path
from typing import Any, List, Optional
from pydantic import TypeAdapter
import pytest
from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolExecutor
from tests.mock_toolset import MockToolsets
import json
from langsmith import Client
from langsmith.evaluation import LangChainStringEvaluator, evaluate

from tests.utils import AskHolmesTestCase, load_ask_holmes_test_cases

TEST_CASES_FOLDER = Path("tests/fixtures/test_chat")

test_cases = load_ask_holmes_test_cases(TEST_CASES_FOLDER, expected_number_of_test_cases=6)

pydantic_test_case = TypeAdapter(AskHolmesTestCase)

def prep_data(run, example) -> dict[str,str]:
    return {
        "prediction": run.outputs["result"],
        "reference": example.outputs["expected_output"],
        "input": example.inputs["user_prompt"],
    }

qa_evaluator = LangChainStringEvaluator(
    "qa",
    prepare_data=prep_data
)


def find_test_case(id:Optional[str], test_cases: List[AskHolmesTestCase]) -> Optional[AskHolmesTestCase]:
    if not id:
        return None
    for test_case in test_cases:
        if test_case.id == id:
            return test_case
            break
    return None


def test_upload_dataset():
    client = Client()
    dataset_name = "Basic holmes dataset"

    dataset = client.read_dataset(dataset_name=dataset_name)
    new_dataset:bool = False
    if not dataset:
        dataset = client.create_dataset(dataset_name, description="Fundamental testing of Holmes' effectiveness")
        new_dataset = True

    examples = client.list_examples(dataset_id=dataset.id)
    for example in examples:
        example.id
    for test_case in test_cases:
        if new_dataset:
            client.create_example(
                inputs={"test_case_id": test_case.id, "user_prompt": test_case.user_prompt},
                outputs={"test_case_id": test_case.id, "expected_output": test_case.expected_output},
                metadata=test_case.model_dump(),
                dataset_id=dataset.id
            )
        else:
            client.update_example(
                inputs={"test_case_id": test_case.id, "user_prompt": test_case.user_prompt},
                outputs={"test_case_id": test_case.id, "expected_output": test_case.expected_output},
                metadata=test_case.model_dump(),
                dataset_id=dataset.id,
                example_id=test_case.id
            )

    def execute(data:dict[str, Any]) -> dict[str, Any]:
        print("** EXECUTE", data)
        test_case_id = data.get("test_case_id")
        test_case = find_test_case(test_case_id, test_cases)
        if not test_case:
            raise Exception(f"Could not find test case with id={test_case_id}")
        # test_case = pydantic_test_case.validate_python(data)
        # test_case = AskHolmesTestCase(**data)
        #
        result = ask_holmes(test_case=test_case)
        # print("***** EXECUTE", test_case)
        return {
            "result": result.result,
            "tool_calls": [tool_call.tool_name for tool_call in (result.tool_calls or [])]
        }

        # return ask_holmes(test_case).model_dump()

    res = evaluate(
        execute, # Your AI system goes here
        data=dataset_name, # The data to predict and grade over
        evaluators=[qa_evaluator], # The evaluators to score the results
        experiment_prefix="MAIN-2356", # The name of the experiment
        metadata={
            "version": "1.0.0",
            "revision_id": "beta"
        },
    )
    print(res)
    assert False


# @pytest. mark. skip(reason="Tests failing on GH runners")
# @pytest.mark.parametrize("test_case", test_cases, ids=[test_case.id for test_case in test_cases])
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


    # deepeval_test_case = LLMTestCase(
    #     name=f"ask_holmes:{test_case.id}",
    #     input=test_case.user_prompt,
    #     actual_output=llm_call.result or "",
    #     expected_output=test_case.expected_output,
    #     retrieval_context=test_case.retrieval_context,
    #     tools_called=[tool_call.tool_name for tool_call in (llm_call.tool_calls or [])],
    #     expected_tools=expected_tools
    # )
    # assert_test(deepeval_test_case, [
    #     AnswerRelevancyMetric(test_case.evaluation.answer_relevancy),
    #     FaithfulnessMetric(test_case.evaluation.faithfulness),
    #     ContextualPrecisionMetric(
    #         threshold=test_case.evaluation.contextual_precision,
    #         model="gpt-4o-mini",
    #         include_reason=True
    #     ),
    #     ContextualRecallMetric(
    #         threshold=test_case.evaluation.contextual_recall,
    #         model="gpt-4o-mini",
    #         include_reason=True
    #     ),
    #     ContextualRelevancyMetric(
    #         threshold=test_case.evaluation.contextual_relevancy,
    #         model="gpt-4o-mini",
    #         include_reason=True
    #     )
    # ])
