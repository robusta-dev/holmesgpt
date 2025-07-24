# type: ignore
import os
from pathlib import Path
from typing import Optional
import json
import pytest
from server import workload_health_check

from holmes.core.tracing import SpanType
from holmes.core.tools_utils.tool_executor import ToolExecutor
import tests.llm.utils.braintrust as braintrust_util
from holmes.config import Config

from holmes.core.supabase_dal import SupabaseDal
from tests.llm.utils.classifiers import (
    evaluate_correctness,
)
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.system import get_machine_state_tags
from tests.llm.utils.mock_dal import MockSupabaseDal
from tests.llm.utils.mock_toolset import MockToolsetManager
from tests.llm.utils.test_case_utils import (
    Evaluation,
    HealthCheckTestCase,
    MockHelper,
)
from tests.llm.utils.property_manager import set_initial_properties, update_test_results
from os import path
from braintrust import Span
from unittest.mock import patch

from tests.llm.utils.tags import add_tags_to_eval

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_workload_health"))
)


class MockConfig(Config):
    def __init__(
        self, test_case: HealthCheckTestCase, parent_span: Span, mock_generation_config
    ):
        super().__init__()
        self._test_case = test_case
        self._parent_span = parent_span
        self._mock_generation_config = mock_generation_config

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        mock = MockToolsetManager(
            test_case_folder=self._test_case.folder,
            mock_generation_config=self._mock_generation_config,
        )

        # With the new file-based mock system, mocks are loaded from disk automatically
        # No need to call mock_tool() anymore
        return ToolExecutor(mock.enabled_toolsets)


def get_test_cases():
    experiment_name = braintrust_util.get_experiment_name("health_check")
    dataset_name = braintrust_util.get_dataset_name("health_check")

    mh = MockHelper(TEST_CASES_FOLDER)

    if os.environ.get("UPLOAD_DATASET") and os.environ.get("BRAINTRUST_API_KEY"):
        bt_helper = braintrust_util.BraintrustEvalHelper(
            project_name=PROJECT, dataset_name=dataset_name
        )
        bt_helper.upload_test_cases(mh.load_test_cases())

    test_cases = mh.load_workload_health_test_cases()

    iterations = int(os.environ.get("ITERATIONS", "0"))
    if iterations:
        test_cases_tuples = []
        for i in range(0, iterations):
            test_cases_tuples.extend(
                [
                    add_tags_to_eval(experiment_name, test_case)
                    for test_case in test_cases
                ]
            )
        return test_cases_tuples
    else:
        return [
            add_tags_to_eval(experiment_name, test_case) for test_case in test_cases
        ]


def idfn(val):
    if isinstance(val, HealthCheckTestCase):
        return val.id
    else:
        return str(val)


@pytest.mark.llm
@pytest.mark.parametrize("experiment_name, test_case", get_test_cases(), ids=idfn)
def test_health_check(
    experiment_name: str,
    test_case: HealthCheckTestCase,
    caplog,
    request,
    mock_generation_config,
):
    # Set initial properties early so they're available even if test fails
    set_initial_properties(request, test_case)

    dataset_name = braintrust_util.get_dataset_name("health_check")
    bt_helper = braintrust_util.BraintrustEvalHelper(
        project_name=PROJECT, dataset_name=dataset_name
    )
    eval_span = bt_helper.start_evaluation(experiment_name, name=test_case.id)

    # Store span info in user properties for conftest to access
    if hasattr(eval_span, "id"):
        request.node.user_properties.append(("braintrust_span_id", str(eval_span.id)))
    if hasattr(eval_span, "root_span_id"):
        request.node.user_properties.append(
            ("braintrust_root_span_id", str(eval_span.root_span_id))
        )

    config = MockConfig(test_case, eval_span, mock_generation_config)
    config.model = os.environ.get("MODEL", "gpt-4o")

    mock_dal = MockSupabaseDal(
        test_case_folder=Path(test_case.folder),
        generate_mocks=mock_generation_config.generate_mocks,
        issue_data=test_case.issue_data,
        resource_instructions=test_case.resource_instructions,
    )

    input = test_case.workload_health_request
    expected = test_case.expected_output

    metadata = get_machine_state_tags()
    metadata["model"] = config.model or "Unknown"
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

    if bt_helper and eval_span:
        bt_helper.end_evaluation(
            input=input,
            output=output or "",
            expected=str(expected),
            id=test_case.id,
            scores=scores,
            prompt=None,
            tags=test_case.tags,
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
