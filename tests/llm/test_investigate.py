
import os
from pathlib import Path
from typing import Optional

from autoevals import Factuality
import braintrust
from pydantic import TypeAdapter
import pytest
from rich.console import Console

from holmes.config import Config
from holmes.core.investigation import investigate_issues
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import ToolExecutor, ToolsetPattern
from tests.llm.common import PROJECT, get_context_classifier, readable_timestamp
from tests.llm.utils import get_machine_state_tags
from tests.mock_dal import MockSupabaseDal
from tests.mock_toolset import MockToolsets
from tests.mock_utils import InvestigateTestCase, MockHelper, upload_dataset
from os import path


TEST_CASES_FOLDER = Path(path.abspath(path.join(
    path.dirname(__file__),
    "fixtures", "test_investigate"
)))

DATASET_NAME = "investigate"

class MockConfig(Config):
    def __init__(self, test_case:InvestigateTestCase):
        super().__init__()
        self._test_case = test_case

    def create_tool_executor(
        self, console: Console, allowed_toolsets: ToolsetPattern, dal:Optional[SupabaseDal]
    ) -> ToolExecutor:

        mock = MockToolsets(tools_passthrough=self._test_case.tools_passthrough, test_case_folder=self._test_case.folder)

        expected_tools = []
        for tool_mock in self._test_case.tool_mocks:
            mock.mock_tool(tool_mock)
            expected_tools.append(tool_mock.tool_name)

        return ToolExecutor(mock.mocked_toolsets)

@pytest.mark.skipif(not os.environ.get('BRAINTRUST_API_KEY'), reason="BRAINTRUST_API_KEY must be set to run LLM evaluations")
def test_investigate():

    mh = MockHelper(TEST_CASES_FOLDER)
    upload_dataset(
        test_cases=mh.load_investigate_test_cases(),
        project_name=PROJECT,
        dataset_name=DATASET_NAME
    )
    dataset = braintrust.init_dataset(project=PROJECT, name=DATASET_NAME)
    experiment:braintrust.Experiment|braintrust.ReadonlyExperiment = braintrust.init(
        project=PROJECT,
        experiment=f"investigate_{readable_timestamp()}",
        dataset=dataset,
        open=False,
        update=False,
        metadata=get_machine_state_tags())

    if isinstance(experiment, braintrust.ReadonlyExperiment):
        raise Exception("Experiment must be writable. The above options open=False and update=False ensure this is the case so this exception should never be raised")


    eval_factuality = Factuality()
    for dataset_row in dataset:

        test_case = TypeAdapter(InvestigateTestCase).validate_python(dataset_row["metadata"])

        config = MockConfig(test_case)
        mock_dal = MockSupabaseDal(
            issue_data=test_case.issue_data,
            resource_instructions=test_case.resource_instructions
        )
        span = experiment.start_span(name=f"investigate:{test_case.id}", span_attributes={"test_case_id": test_case.id})

        result = investigate_issues(
            investigate_request=test_case.investigate_request,
            config=config,
            dal=mock_dal,
            console=Console()
        )
        span.end()

        input = test_case.investigate_request
        output = result.analysis
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
