
import braintrust
from braintrust import Dataset, Experiment, ReadonlyExperiment
import logging
from typing import Any, List, Optional

from tests.llm.utils.mock_utils import HolmesTestCase
from tests.llm.utils.system import get_machine_state_tags

def find_dataset_row_by_test_case(dataset:Dataset, test_case:HolmesTestCase):
    for row in dataset:
        if row.get("id") == test_case.id:
            return row
    return None

def pop_test_case(test_cases:List[HolmesTestCase], id:str) -> Optional[HolmesTestCase]:
    for test_case in test_cases:
        if test_case.id == id:
            test_cases.remove(test_case)
            return test_case

def pop_matching_test_case_if_exists(test_cases:List[HolmesTestCase], item:Any) -> Optional[HolmesTestCase]:
    """
    This function is expected to mutate the test_cases list then
    remove the matching test case from the list and return it
    """

    test_case_id = item.get("id")
    return pop_test_case(test_cases, test_case_id)


class BraintrustEvalHelper():
    def __init__(self, project_name:str, dataset_name:str) -> None:
        self.project_name = project_name
        self.dataset_name = dataset_name
        self.dataset = braintrust.init_dataset(project=project_name, name=dataset_name)
        self.experiment = None


    def upload_test_cases(self, test_cases:List[HolmesTestCase]):
        logging.info(f"Uploading f{len(test_cases)} test cases to braintrust")

        logging.info(f"Found dataset: {self.dataset.summarize()}")

        for item in self.dataset:
            test_case = pop_matching_test_case_if_exists(test_cases, item)
            if not test_case:
                self.dataset.delete(item.get("id"))
                continue

            logging.info(f"Updating dataset item f{test_case.id}")
            # update the existing dataset item
            self.dataset.update(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata={
                    "test_case": test_case.model_dump()
                },
                tags=[],
            )

        for test_case in test_cases:
            logging.info(f"Creating dataset item f{test_case.id}")
            self.dataset.insert(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata={
                    "test_case": test_case.model_dump()
                },
                tags=[],
            )

        logging.info(self.dataset.summarize())


    def resolve_dataset_item(self, test_case:HolmesTestCase) -> Optional[Any]:
        return find_dataset_row_by_test_case(self.dataset, test_case)

    def start_evaluation(self, experiment_name:str, name:str):
        if not self.experiment:
            experiment:Experiment|ReadonlyExperiment = braintrust.init(
                project=self.project_name,
                experiment=experiment_name,
                dataset=self.dataset,
                open=False,
                update=True,
                metadata=get_machine_state_tags())

            if isinstance(experiment, ReadonlyExperiment): # Ensures type checker knows this is a writable experiment
                raise Exception("Experiment must be writable. The above options open=False and update=True ensure this is the case so this exception should never be raised")
            self.experiment = experiment
        return self.experiment.start_span(name=name)

    def end_evaluation(self, eval:Any, input:str, output:str, expected:str, id:str, scores:dict[str, Any]):
        if not self.experiment:
            raise Exception("start_evaluation() must be called before end_evaluation()")

        eval.log(
            input=input,
            output=output,
            expected=expected,
            dataset_record_id=id,
            scores=scores
        )
        self.experiment.flush()
