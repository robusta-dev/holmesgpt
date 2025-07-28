# type: ignore
import os
from pathlib import Path
from typing import Optional
import json
import pytest
from server import workload_health_check

from holmes.core.tracing import SpanType, TracingFactory
from holmes.core.tools_utils.tool_executor import ToolExecutor
from holmes.config import Config

from holmes.core.supabase_dal import SupabaseDal
from tests.llm.utils.classifiers import (
    evaluate_correctness,
)
from tests.llm.utils.mock_dal import MockSupabaseDal
from tests.llm.utils.mock_toolset import MockToolsetManager
from tests.llm.utils.test_case_utils import (
    Evaluation,
    HealthCheckTestCase,
    MockHelper,
    check_and_skip_test,
)
from tests.llm.utils.property_manager import set_initial_properties, update_test_results
from os import path
from unittest.mock import patch

from tests.llm.utils.tags import add_tags_to_eval

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_workload_health"))
)


class MockConfig(Config):
    def __init__(
        self,
        test_case: HealthCheckTestCase,
        tracer,
        mock_generation_config,
        request=None,
    ):
        super().__init__()
        self._test_case = test_case
        self._tracer = tracer
        self._mock_generation_config = mock_generation_config
        self._request = request

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        mock = MockToolsetManager(
            test_case_folder=self._test_case.folder,
            mock_generation_config=self._mock_generation_config,
            request=self._request,
        )

        # With the new file-based mock system, mocks are loaded from disk automatically
        # No need to call mock_tool() anymore
        return ToolExecutor(mock.toolsets)


def get_test_cases():
    mh = MockHelper(TEST_CASES_FOLDER)
    # dataset_name = braintrust_util.get_dataset_name("health_check")
    # if os.environ.get("UPLOAD_DATASET") and os.environ.get("BRAINTRUST_API_KEY"):
    #     bt_helper = braintrust_util.BraintrustEvalHelper(
    #         project_name=BRAINTRUST_PROJECT, dataset_name=dataset_name
    #     )
    #     bt_helper.upload_test_cases(mh.load_test_cases())

    test_cases = mh.load_workload_health_test_cases()
    iterations = int(os.environ.get("ITERATIONS", "1"))
    return [add_tags_to_eval(test_case) for test_case in test_cases] * iterations


def idfn(val):
    if isinstance(val, HealthCheckTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.parametrize("test_case", get_test_cases(), ids=idfn)
def test_health_check(
    test_case: HealthCheckTestCase,
    caplog,
    request,
    mock_generation_config,
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

    tracer = TracingFactory.create_tracer("braintrust")
    tracer.start_experiment()

    config = MockConfig(test_case, tracer, mock_generation_config, request)
    config.model = os.environ.get("MODEL", "gpt-4o")

    mock_dal = MockSupabaseDal(
        test_case_folder=Path(test_case.folder),
        generate_mocks=mock_generation_config.generate_mocks,
        issue_data=test_case.issue_data,
        resource_instructions=test_case.resource_instructions,
    )

    input = test_case.workload_health_request
    expected = test_case.expected_output

    with tracer.start_trace(name=test_case.id, span_type=SpanType.EVAL) as eval_span:
        # Store span info in user properties for conftest to access
        if hasattr(eval_span, "id"):
            request.node.user_properties.append(
                ("braintrust_span_id", str(eval_span.id))
            )
        if hasattr(eval_span, "root_span_id"):
            request.node.user_properties.append(
                ("braintrust_root_span_id", str(eval_span.root_span_id))
            )

        with patch.multiple("server", dal=mock_dal, config=config):
            with eval_span.start_span("Holmes Run", type=SpanType.LLM):
                result = workload_health_check(request=input)

        assert result, "No result returned by workload_health_check()"
        # check that analysis is json parsable otherwise failed.
        print(f"** ANALYSIS **\n-  {result.analysis}")
        json.loads(result.analysis)
        output = result.analysis

        debug_expected = "\n-  ".join(expected)

        print(f"** EXPECTED **\n-  {debug_expected}")
        correctness_eval = evaluate_correctness(
            output=output,
            expected_elements=expected,
            parent_span=eval_span,
            caplog=caplog,
            evaluation_type="strict",
        )
        print(
            f"\n** CORRECTNESS **\nscore = {correctness_eval.score}\nrationale = {correctness_eval.metadata.get('rationale', '')}"
        )
        scores = {}
        scores["correctness"] = correctness_eval.score

        # Log evaluation results directly to the span
        if eval_span:
            eval_span.log(
                input=input,
                output=output or "",
                expected=str(expected),
                dataset_record_id=test_case.id,
                scores=scores,
                metadata={"tags": test_case.tags},
            )

        tools_called = [t.tool_name for t in result.tool_calls]
        print(f"\n** TOOLS CALLED **\n{tools_called}")
        print(f"\n** OUTPUT **\n{output}")
        print(f"\n** SCORES **\n{scores}")

    # Update test results
    update_test_results(request, output, tools_called, scores)

    if test_case.evaluation.correctness:
        expected_correctness = test_case.evaluation.correctness
        if isinstance(expected_correctness, Evaluation):
            expected_correctness = expected_correctness.expected_score
        assert scores.get("correctness", 0) >= expected_correctness
