# type: ignore
import os
from typing import Optional
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from rich.console import Console
from holmes.core.models import ChatRequest
from holmes.core.tracing import TracingFactory
from holmes.config import Config
from holmes.core.conversations import build_chat_messages
from holmes.core.llm import DefaultLLM
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools_utils.tool_executor import ToolExecutor
from tests.llm.utils.classifiers import evaluate_correctness
from tests.llm.utils.commands import set_test_env_vars
from tests.llm.utils.mock_toolset import (
    MockToolsetManager,
    MockMode,
    MockGenerationConfig,
)
from tests.llm.utils.test_case_utils import (
    AskHolmesTestCase,
    Evaluation,
    MockHelper,
    check_and_skip_test,
)

from holmes.core.prompt import build_initial_ask_messages

from tests.llm.utils.property_manager import (
    set_initial_properties,
    update_test_results,
    update_mock_error,
)
from os import path
from tests.llm.utils.tags import add_tags_to_eval
from holmes.core.tracing import SpanType
from tests.llm.utils.test_helpers import (
    print_expected_output,
    print_correctness_evaluation,
    print_tool_calls_summary,
    print_tool_calls_detailed,
)

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_ask_holmes"))
)


# TODO: reuse code with test_investigate.py and test_workload_health.py
def get_test_cases():
    mh = MockHelper(TEST_CASES_FOLDER)
    test_cases = mh.load_ask_holmes_test_cases()
    iterations = int(os.environ.get("ITERATIONS", "1"))
    return [add_tags_to_eval(test_case) for test_case in test_cases] * iterations


def idfn(val):
    if isinstance(val, AskHolmesTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.parametrize("test_case", get_test_cases(), ids=idfn)
def test_ask_holmes(
    test_case: AskHolmesTestCase,
    caplog,
    request,
    mock_generation_config: MockGenerationConfig,
    shared_test_infrastructure,  # type: ignore
):
    # Set initial properties early so they're available even if test fails
    set_initial_properties(request, test_case)

    # Check if test should be skipped
    check_and_skip_test(test_case)

    # Check for setup failures
    setup_failures = shared_test_infrastructure.get("setup_failures", {})
    if test_case.id in setup_failures:
        request.node.user_properties.append(("is_setup_failure", True))
        pytest.fail(f"Test setup failed: {setup_failures[test_case.id]}")

    print(f"\n🧪 TEST: {test_case.id}")
    print("   CONFIGURATION:")
    print(
        f"   • Mode: {'⚪️ MOCKED' if mock_generation_config.mode == MockMode.MOCK else '🔥 LIVE'}, Generate Mocks: {mock_generation_config.generate_mocks}"
    )
    print(f"   • User Prompt: {test_case.user_prompt}")
    print(f"   • Expected Output: {test_case.expected_output}")
    if test_case.before_test:
        if "\n" in test_case.before_test:
            print("   • Before Test:")
            for line in test_case.before_test.strip().split("\n"):
                print(f"       {line}")
        else:
            print(f"   • Before Test: {test_case.before_test}")

    if test_case.after_test:
        if "\n" in test_case.after_test:
            print("   • After Test:")
            for line in test_case.after_test.strip().split("\n"):
                print(f"       {line}")
        else:
            print(f"   • After Test: {test_case.after_test}")

    tracer = TracingFactory.create_tracer("braintrust")
    tracer.start_experiment()

    result: Optional[LLMResult] = None

    try:
        with tracer.start_trace(
            name=test_case.id, span_type=SpanType.EVAL
        ) as eval_span:
            # Store span info in user properties for conftest to access
            if hasattr(eval_span, "id"):
                request.node.user_properties.append(
                    ("braintrust_span_id", str(eval_span.id))
                )
            if hasattr(eval_span, "root_span_id"):
                request.node.user_properties.append(
                    ("braintrust_root_span_id", str(eval_span.root_span_id))
                )

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
                    # metadata={"tags": test_case.tags},
                )
        except Exception:
            pass  # Don't fail the test due to logging issues

        # Check if this is a MockDataError
        is_mock_error = "MockDataError" in type(e).__name__ or any(
            "MockData" in base.__name__ for base in type(e).__mro__
        )

        if is_mock_error:
            # Update properties for mock error
            update_mock_error(request, e)

        # Cleanup is handled by session-scoped fixture now
        raise

    finally:
        # Cleanup is handled by session-scoped fixture now
        pass

    input = test_case.user_prompt
    output = result.result
    expected = test_case.expected_output

    scores = {}

    if not isinstance(expected, list):
        expected = [expected]

    print_expected_output(expected)

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
    print("\n💬 ACTUAL OUTPUT:")
    print(f"   {output}")

    print_correctness_evaluation(correctness_eval)

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
            # metadata={"tags": test_case.tags},
        )

    # Print tool calls summary
    print_tool_calls_summary(result.tool_calls)

    if result.tool_calls:
        tools_called = [tc.description for tc in result.tool_calls]
    else:
        tools_called = "None"

    # Print detailed tool output
    print_tool_calls_detailed(result.tool_calls)

    # Update test results
    update_test_results(request, output, tools_called, scores)

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
        # Get expected from test_case since debug_expected is no longer in local scope
        expected_output = test_case.expected_output
        if isinstance(expected_output, list):
            expected_output = "\n-  ".join(expected_output)
        pytest.fail(
            f"Test {test_case.id} failed due to mock data error\nActual: {output}\nExpected: {expected_output}"
        )

    # Get expected for assertion message
    expected_output = test_case.expected_output
    if isinstance(expected_output, list):
        expected_output = "\n-  ".join(expected_output)

    assert (
        int(scores.get("correctness", 0)) == 1
    ), f"Test {test_case.id} failed (score: {scores.get('correctness', 0)})\nActual: {output}\nExpected: {expected_output}"


# TODO: can this call real ask_holmes so more of the logic is captured
def ask_holmes(
    test_case: AskHolmesTestCase, tracer, mock_generation_config, request=None
) -> LLMResult:
    toolset_manager = MockToolsetManager(
        test_case_folder=test_case.folder,
        mock_generation_config=mock_generation_config,
        request=request,
        mock_policy=test_case.mock_policy,
    )

    tool_executor = ToolExecutor(toolset_manager.toolsets)
    enabled_toolsets = [t.name for t in tool_executor.enabled_toolsets]
    print(
        f"\n🛠️  ENABLED TOOLSETS ({len(enabled_toolsets)}):", ", ".join(enabled_toolsets)
    )

    ai = ToolCallingLLM(
        tool_executor=tool_executor,
        max_steps=10,
        llm=DefaultLLM(os.environ.get("MODEL", "gpt-4o"), tracer=tracer),
    )

    test_type = os.environ.get("ASK_HOLMES_TEST_TYPE", "cli").lower()
    if test_type == "cli":
        if test_case.conversation_history:
            pytest.skip("CLI mode does not support conversation history tests")
        else:
            console = Console()
            # Use custom runbooks from test case if provided, otherwise use default system runbooks
            if test_case.runbooks is not None:
                runbooks = test_case.runbooks
            else:
                # Load default system runbooks
                from holmes.plugins.runbooks import load_runbook_catalog

                runbook_catalog = load_runbook_catalog()
                runbooks = runbook_catalog.model_dump() if runbook_catalog else {}
            messages = build_initial_ask_messages(
                console,
                test_case.user_prompt,
                None,
                ai.tool_executor,
                runbooks,
            )
    else:
        chat_request = ChatRequest(ask=test_case.user_prompt)
        config = Config()
        if test_case.cluster_name:
            config.cluster_name = test_case.cluster_name

        messages = build_chat_messages(
            ask=chat_request.ask,
            conversation_history=test_case.conversation_history,
            ai=ai,
            config=config,
        )

    # Create LLM completion trace within current context
    with tracer.start_trace("run holmes", span_type=SpanType.LLM) as llm_span:
        return ai.messages_call(messages=messages, trace_span=llm_span)
