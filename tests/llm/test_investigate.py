
import json
import logging
import os
from pathlib import Path
from typing import Optional

from autoevals import Factuality
import braintrust
import pytest
from rich.console import Console

from holmes.config import Config
from holmes.core.investigation import investigate_issues
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import ToolExecutor, ToolsetPattern
from tests.llm.utils.classifiers import get_context_classifier, get_logs_explanation_classifier
from tests.llm.utils.constants import PROJECT
from tests.llm.utils.system import get_machine_state_tags, readable_timestamp
from tests.llm.utils.mock_dal import MockSupabaseDal
from tests.llm.utils.mock_toolset import MockToolsets
from tests.llm.utils.mock_utils import InvestigateTestCase, MockHelper, upload_dataset
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

        mock = MockToolsets(tools_passthrough=self._test_case.mocks_passthrough, test_case_folder=self._test_case.folder)

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
    failed_runs = []
    runs = []

    mh = MockHelper(TEST_CASES_FOLDER)
    test_cases = mh.load_investigate_test_cases()
    for test_case in test_cases:
    # for dataset_row in dataset:

    #     test_case = TypeAdapter(InvestigateTestCase).validate_python(dataset_row["metadata"])

        config = MockConfig(test_case)
        mock_dal = MockSupabaseDal(
            test_case_folder=Path(test_case.folder),
            dal_passthrough=test_case.mocks_passthrough,
            issue_data=test_case.issue_data,
            resource_instructions=test_case.resource_instructions
        )
        # span = experiment.start_span(name=f"investigate:{test_case.id}", span_attributes={"test_case_id": test_case.id})

        input = test_case.investigate_request
        expected = test_case.expected_output
        result = None
        try:
            result = investigate_issues(
                investigate_request=test_case.investigate_request,
                config=config,
                dal=mock_dal,
                console=Console()
            )
        except Exception:
            logging.exception(f"Failed to run test case {test_case.id}")
        finally:
            # span.end()
            pass

        if result is None:
            # span.log(
            #     input=input,
            #     output="",
            #     expected=expected,
            #     dataset_record_id=dataset_row["id"],
            #     scores={"runs_successfully": 0}
            # )
            failed_runs.append(test_case.id)
            continue

        output = result.analysis

        evaluate_logs_explanation = get_logs_explanation_classifier()
        scores = {
            "runs_successfully": 1,
            "faithfulness": eval_factuality(output, expected, input=input).score,
            "previous_logs": evaluate_logs_explanation(output, expected, input=input).score
        }

        if len(test_case.retrieval_context) > 0:
            evaluate_context_usage = get_context_classifier(test_case.retrieval_context)
            scores["context"] = evaluate_context_usage(output, expected, input=input).score

        # span.log(
        #     input=input,
        #     output=output,
        #     expected=expected,
        #     dataset_record_id=dataset_row["id"],
        #     scores=scores
        # )
        print(output)
        runs.append({
            "id": test_case.id,
            "scores":scores
        })

    # experiment.flush()

    print(json.dumps(runs, indent=2))
    assert failed_runs == [], f"The following llm runs failed: {str(failed_runs)}"



# @pytest.mark.skipif(not os.environ.get('BRAINTRUST_API_KEY'), reason="BRAINTRUST_API_KEY must be set to run LLM evaluations")
# def _test_investigate_langfuse():

#     mh = MockHelper(TEST_CASES_FOLDER)
#     upload_dataset(
#         test_cases=mh.load_investigate_test_cases(),
#         project_name=PROJECT,
#         dataset_name=DATASET_NAME
#     )
#     experiment_name = f"investigate_{readable_timestamp()}"
#     dataset = braintrust.init_dataset(project=PROJECT, name=DATASET_NAME)
#     experiment:braintrust.Experiment|braintrust.ReadonlyExperiment = braintrust.init(
#         project=PROJECT,
#         experiment=experiment_name,
#         dataset=dataset,
#         open=False,
#         update=False,
#         metadata=get_machine_state_tags())

#     lf_dataset = None
#     try:
#         lf_dataset = langfuse.get_dataset(DATASET_NAME)
#     except Exception:
#         pass
#     if not lf_dataset:
#         lf_dataset = langfuse.create_dataset(
#             name=DATASET_NAME,
#             # optional description
#             description=DATASET_NAME
#         )
#         for dataset_row in dataset:
#             test_case = TypeAdapter(InvestigateTestCase).validate_python(dataset_row["metadata"])
#             langfuse.create_dataset_item(
#                 dataset_name=DATASET_NAME,
#                 input={
#                     "text": test_case.id
#                 },
#                 expected_output={
#                     "text": test_case.expected_output
#                 },
#                 metadata=test_case.model_dump()
#             )
#         assert False, "Dataset created"


#     if isinstance(experiment, braintrust.ReadonlyExperiment):
#         raise Exception("Experiment must be writable. The above options open=False and update=False ensure this is the case so this exception should never be raised")


#     eval_factuality = Factuality()
#     failed_runs = []




#     for item in lf_dataset.items:
#         # Make sure your application function is decorated with @observe decorator to automatically link the trace
#         test_case = TypeAdapter(InvestigateTestCase).validate_python(item.metadata)


#         config = MockConfig(test_case)
#         mock_dal = MockSupabaseDal(
#             test_case_folder=Path(test_case.folder),
#             dal_passthrough=test_case.mocks_passthrough,
#             issue_data=test_case.issue_data,
#             resource_instructions=test_case.resource_instructions
#         )
#         # span = experiment.start_span(name=f"investigate:{test_case.id}", span_attributes={"test_case_id": test_case.id})

#         input = test_case.investigate_request
#         expected = test_case.expected_output

#         trace = langfuse.trace(
#             name = test_case.id,
#             input={"text": test_case.id}
#         )


#         result = investigate_issues(
#             investigate_request=test_case.investigate_request,
#             config=config,
#             dal=mock_dal,
#             console=Console()
#         )
#         # update span and sets end_time
#         trace.update(
#             output=result.analysis,
#         )
#         item.link(
#             trace,
#             experiment_name,
#             run_description=experiment_name, # optional
#             run_metadata={ "model": "gpt-4o" } # optional
#         )
#             # optionally, evaluate the output to compare different runs more easily
#             # langfuse.score(
#             #     trace_id=trace_id,
#             #     name="<example_eval>",
#             #     # any float value
#             #     value=my_eval_fn(item.input, output, item.expected_output),
#             #     comment="This is a comment",  # optional, useful to add reasoning
#             # )

#     # Flush the langfuse client to ensure all data is sent to the server at the end of the experiment run
#     langfuse.flush()
