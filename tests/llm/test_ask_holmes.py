# type: ignore
import os
from typing import Optional
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from holmes.core.tracing import TracingFactory
from holmes.common.env_vars import load_bool
from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.models import ChatRequest
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools_utils.tool_executor import ToolExecutor
import tests.llm.utils.braintrust as braintrust_util
from tests.llm.utils.classifiers import evaluate_correctness
from tests.llm.utils.commands import after_test, before_test, set_test_env_vars
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.mock_toolset import MockToolsetManager
from braintrust import SpanTypeAttribute
from tests.llm.utils.test_case_utils import AskHolmesTestCase, Evaluation, MockHelper
from os import path
from tests.llm.utils.tags import add_tags_to_eval
from holmes.core.tracing import SpanType

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
        return [
            add_tags_to_eval(experiment_name, test_case) for test_case in test_cases
        ] * iterations
    else:
        return [
            add_tags_to_eval(experiment_name, test_case) for test_case in test_cases
        ]


def idfn(val):
    if isinstance(val, AskHolmesTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_ask_holmes(
    experiment_name: str,
    test_case: AskHolmesTestCase,
    caplog,
    request,
    mock_generation_config,
):
    tracer = TracingFactory.create_tracer("braintrust", project=PROJECT)

    # Create experiment using unified API
    tracer.start_experiment(
        experiment_name=experiment_name,
        metadata=braintrust_util.get_machine_state_tags(),
    )

    # Create evaluation span and use as context manager
    result: Optional[LLMResult] = None
    try:
        with tracer.start_trace(
            name=test_case.id, span_type=SpanType.TASK
        ) as eval_span:
            with eval_span.start_span("Before Test Setup", type=SpanTypeAttribute.TASK):
                before_test(test_case)

            # Mock datetime if mocked_date is provided
            if test_case.mocked_date:
                mocked_datetime = datetime.fromisoformat(
                    test_case.mocked_date.replace("Z", "+00:00")
                )
                with patch("holmes.plugins.prompts.datetime") as mock_datetime:
                    mock_datetime.now.return_value = mocked_datetime

                    mock_datetime.side_effect = None
                    mock_datetime.configure_mock(
                        **{"now.return_value": mocked_datetime, "side_effect": None}
                    )
                    with set_test_env_vars(test_case):
                        result = ask_holmes(
                            test_case=test_case,
                            tracer=tracer,
                            mock_generation_config=mock_generation_config,
                            request=request,
                        )
            else:
                with set_test_env_vars(test_case):
                    result = ask_holmes(
                        test_case=test_case,
                        tracer=tracer,
                        mock_generation_config=mock_generation_config,
                        request=request,
                    )

    except Exception as e:
        # Log error to span if available
        try:
            if "eval_span" in locals():
                eval_span.log(
                    input=test_case.user_prompt,
                    output=result.result if result else str(e),
                    expected=test_case.expected_output,
                    dataset_record_id=test_case.id,
                    scores={},
                )
        except Exception:
            pass  # Don't fail the test due to logging issues

        # Check if this is a MockDataError
        is_mock_error = "MockDataError" in type(e).__name__ or any(
            "MockData" in base.__name__ for base in type(e).__mro__
        )

        if is_mock_error:
            # Store minimal data for summary before failing
            expected = test_case.expected_output
            if not isinstance(expected, list):
                expected = [expected]
            debug_expected = "\n-  ".join(expected)

            expected_correctness_score = (
                test_case.evaluation.correctness.expected_score
                if isinstance(test_case.evaluation.correctness, Evaluation)
                else test_case.evaluation.correctness
            )

            # Record the mock failure in user_properties
            request.node.user_properties.append(("expected", debug_expected))
            request.node.user_properties.append(
                ("actual", f"Mock data error: {str(e)}")
            )
            request.node.user_properties.append(("tools_called", []))
            request.node.user_properties.append(
                ("expected_correctness_score", expected_correctness_score)
            )
            request.node.user_properties.append(("actual_correctness_score", 0))
            request.node.user_properties.append(("mock_data_failure", True))

        after_test(test_case)
        raise

    finally:
        with eval_span.start_span("After Test Teardown", type=SpanTypeAttribute.TASK):
            after_test(test_case)

    input = test_case.user_prompt
    output = result.result
    expected = test_case.expected_output

    scores = {}

    if not isinstance(expected, list):
        expected = [expected]

    debug_expected = "\n-  ".join(expected)
    print(f"** EXPECTED **\n-  {debug_expected}")

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
        caplog=caplog,
    )
    print(
        f"\nCORRECTNESS:\nscore = {correctness_eval.score}\nRATIONALE:\n{correctness_eval.metadata.get('rationale', '')}"
    )

    scores["correctness"] = correctness_eval.score

    # Log evaluation results directly to the span
    if eval_span:
        eval_span.log(
            input=input,
            output=output or "",
            expected=str(expected),
            dataset_record_id=test_case.id,
            scores=scores,
            metadata={"system_prompt": prompt},
        )

    if result.tool_calls:
        tools_called = [tc.description for tc in result.tool_calls]
    else:
        tools_called = "None"
    print(f"\n** TOOLS CALLED **\n{tools_called}")
    print(f"\n** OUTPUT **\n{output}")
    print(f"\n** SCORES **\n{scores}")

    # Store data for summary plugin
    expected_correctness_score = (
        test_case.evaluation.correctness.expected_score
        if isinstance(test_case.evaluation.correctness, Evaluation)
        else test_case.evaluation.correctness
    )
    request.node.user_properties.append(("expected", debug_expected))
    request.node.user_properties.append(("actual", output or ""))
    request.node.user_properties.append(
        (
            "tools_called",
            tools_called if isinstance(tools_called, list) else [str(tools_called)],
        )
    )
    request.node.user_properties.append(
        ("expected_correctness_score", expected_correctness_score)
    )
    request.node.user_properties.append(
        ("actual_correctness_score", scores.get("correctness", 0))
    )

    # Check if the output contains MockDataError (indicating a mock failure)
    if output and any(
        error_type in output
        for error_type in [
            "MockDataError",
            "MockDataNotFoundError",
            "MockDataCorruptedError",
        ]
    ):
        # Record mock failure in user_properties
        request.node.user_properties.append(("mock_data_failure", True))
        # Fail the test
        pytest.fail(
            f"Test {test_case.id} failed due to mock data error\nActual: {output}\nExpected: {debug_expected}"
        )

    assert (
        int(scores.get("correctness", 0)) == 1
    ), f"Test {test_case.id} failed (score: {scores.get('correctness', 0)})\nActual: {output}\nExpected: {debug_expected}"


def ask_holmes(
    test_case: AskHolmesTestCase, tracer, mock_generation_config, request=None
) -> LLMResult:
    run_live = load_bool("RUN_LIVE", default=False)
    mock = MockToolsetManager(
        generate_mocks=mock_generation_config.generate_mocks,
        test_case_folder=test_case.folder,
        run_live=run_live,
        mock_generation_tracker=mock_generation_config,
        request=request,
    )

    # With the new simplified mock system, mocks are loaded from disk on each tool invocation
    # No need to populate mocks in memory anymore

    tool_executor = ToolExecutor(mock.enabled_toolsets)
    enabled_toolsets = [t.name for t in tool_executor.enabled_toolsets]

    print(f"** ENABLED TOOLSETS **\n{', '.join(enabled_toolsets)}")

    ai = ToolCallingLLM(
        tool_executor=tool_executor,
        max_steps=10,
        llm=DefaultLLM(os.environ.get("MODEL", "gpt-4o"), tracer=tracer),
    )

    chat_request = ChatRequest(ask=test_case.user_prompt)
    messages = build_chat_messages(
        ask=chat_request.ask, conversation_history=test_case.conversation_history, ai=ai
    )

    # Create LLM completion trace within current context
    with tracer.start_trace("run holmes", span_type=SpanType.LLM) as llm_span:
        return ai.messages_call(messages=messages, trace_span=llm_span)
