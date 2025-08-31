# type: ignore
import time
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
    check_and_skip_test,
    get_models,
)
from tests.llm.utils.property_manager import (
    set_initial_properties,
    set_trace_properties,
    update_test_results,
    handle_test_error,
)
from os import path
from unittest.mock import patch

from tests.llm.utils.iteration_utils import get_test_cases

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


def get_workload_health_test_cases():
    return get_test_cases(TEST_CASES_FOLDER)


@pytest.mark.llm
@pytest.mark.parametrize("model", get_models())
@pytest.mark.parametrize("test_case", get_workload_health_test_cases())
def test_health_check(
    model: str,
    test_case: HealthCheckTestCase,
    caplog,
    request,
    mock_generation_config,
    shared_test_infrastructure,  # type: ignore
):
    # Set initial properties early so they're available even if test fails
    set_initial_properties(request, test_case, model)

    tracer = TracingFactory.create_tracer("braintrust")
    metadata = {"model": model}
    tracer.start_experiment(additional_metadata=metadata)

    config = MockConfig(test_case, tracer, mock_generation_config, request)
    config.model = model

    mock_dal = MockSupabaseDal(
        test_case_folder=Path(test_case.folder),
        generate_mocks=mock_generation_config.generate_mocks,
        issue_data=test_case.issue_data,
        resource_instructions=test_case.resource_instructions,
    )

    input = test_case.workload_health_request
    expected = test_case.expected_output

    result = None
    with tracer.start_trace(
        name=f"{test_case.id}[{model}]", span_type=SpanType.EVAL
    ) as eval_span:
        set_trace_properties(request, eval_span)
        check_and_skip_test(test_case, request, shared_test_infrastructure)

        try:
            with patch.multiple("server", dal=mock_dal, config=config):
                # Note: Currently workload_health_check does not trace llm calls and the run includes the startup time of the tools
                with eval_span.start_span("Holmes Run", type=SpanType.TASK.value):
                    start_time = time.time()
                    result = workload_health_check(request=input)
                    holmes_duration = time.time() - start_time
                    eval_span.log(metadata={"Holmes Duration": holmes_duration})

            assert result, "No result returned by workload_health_check()"

            # check that analysis is json parsable otherwise failed.
            print(f"\n🧪 TEST: {test_case.id}")
            print(f"   • Model: {model}")
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
                # Prepare tags with model
                tags = (test_case.tags or []).copy()
                tags.append(f"model:{model}")

                eval_span.log(
                    input=input,
                    output=output or "",
                    expected=str(expected),
                    dataset_record_id=test_case.id,
                    scores=scores,
                    metadata={"model": model},
                    tags=tags,
                )

            tools_called = (
                [t.tool_name for t in result.tool_calls] if result.tool_calls else []
            )
            print(f"\n** TOOLS CALLED **\n{tools_called}")
            print(f"\n** OUTPUT **\n{output}")
            print(f"\n** SCORES **\n{scores}")

            # Update test results
            update_test_results(request, output, tools_called, scores, result)

        except Exception as e:
            handle_test_error(
                request=request,
                error=e,
                eval_span=eval_span,
                test_case=test_case,
                model=model,
                result=result,
                mock_generation_config=mock_generation_config,
            )
            raise

    if test_case.evaluation.correctness:
        expected_correctness = test_case.evaluation.correctness
        if isinstance(expected_correctness, Evaluation):
            expected_correctness = expected_correctness.expected_score
        assert scores.get("correctness", 0) >= expected_correctness
