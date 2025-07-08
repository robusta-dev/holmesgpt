import os
import braintrust
from braintrust import Dataset, Experiment, ReadonlyExperiment, Span
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from tests.llm.utils.mock_utils import HolmesTestCase  # type: ignore
from tests.llm.utils.system import get_machine_state_tags, readable_timestamp

BRAINTRUST_API_KEY = os.environ.get("BRAINTRUST_API_KEY")

braintrust_enabled = False

if BRAINTRUST_API_KEY:
    braintrust_enabled = True


def find_dataset_row_by_test_case(dataset: Dataset, test_case: HolmesTestCase):
    for row in dataset:
        if row.get("id") == test_case.id:
            return row
    return None


def pop_test_case(
    test_cases: List[HolmesTestCase], id: str
) -> Optional[HolmesTestCase]:
    for test_case in test_cases:
        if test_case.id == id:
            test_cases.remove(test_case)
            return test_case

    return None


def pop_matching_test_case_if_exists(
    test_cases: List[HolmesTestCase], item: Any
) -> Optional[HolmesTestCase]:
    """
    This function is expected to mutate the test_cases list then
    remove the matching test case from the list and return it
    """

    test_case_id = item.get("id")
    return pop_test_case(test_cases, test_case_id)


class BraintrustEvalHelper:
    def __init__(self, project_name: str, dataset_name: str) -> None:
        self.project_name = project_name
        self.dataset_name = dataset_name
        self.dataset = None
        if braintrust_enabled:
            self.dataset = braintrust.init_dataset(
                project=project_name, name=dataset_name
            )
        self.experiment = None

    def upload_test_cases(self, test_cases: List[HolmesTestCase]):
        if not self.dataset:
            # braintrust is disabled
            return

        logging.info(f"Uploading f{len(test_cases)} test cases to braintrust")

        logging.info(f"Found dataset: {self.dataset.summarize()}")

        for item in self.dataset:
            test_case = pop_matching_test_case_if_exists(test_cases, item)
            if not test_case:
                self.dataset.delete(item.get("id"))  # type: ignore
                continue

            logging.info(f"Updating dataset item f{test_case.id}")
            # update the existing dataset item
            self.dataset.update(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata={"test_case": test_case.model_dump()},
                tags=[],
            )

        for test_case in test_cases:
            logging.info(f"Creating dataset item f{test_case.id}")
            self.dataset.insert(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata={"test_case": test_case.model_dump()},
                tags=[],
            )

        logging.info(self.dataset.summarize())

    def resolve_dataset_item(self, test_case: HolmesTestCase) -> Optional[Any]:
        if not self.dataset:
            # braintrust is disabled
            return None
        return find_dataset_row_by_test_case(self.dataset, test_case)

    def start_evaluation(self, experiment_name: str, name: str) -> Optional[Span]:
        if not self.dataset:
            # braintrust is disabled
            return None
        if not self.experiment:
            experiment: Experiment | ReadonlyExperiment = braintrust.init(
                project=self.project_name,
                experiment=experiment_name,
                dataset=self.dataset,
                open=False,
                update=True,
                metadata=get_machine_state_tags(),
            )

            if isinstance(
                experiment, ReadonlyExperiment
            ):  # Ensures type checker knows this is a writable experiment
                raise Exception(
                    "Experiment must be writable. The above options open=False and update=True ensure this is the case so this exception should never be raised"
                )
            self.experiment = experiment  # type: ignore
        self._root_span = self.experiment.start_span(name=name)  # type: ignore
        return self._root_span

    def end_evaluation(
        self,
        input: str,
        output: str,
        expected: str,
        id: str,
        scores: dict[str, Any],
        prompt: Optional[str],
        tags: Optional[list[str]] = None,
    ):
        if not self.dataset:
            # braintrust is disabled
            return
        if not self.experiment:
            raise Exception("start_evaluation() must be called before end_evaluation()")

        self._root_span.log(
            input=input,
            output=output,
            expected=expected,
            dataset_record_id=id,
            scores=scores,
            metadata={"system_prompt": prompt},
            tags=tags,
        )
        self._root_span.end()
        self.experiment.flush()


def get_experiment_name(test_suite: str):
    unique_test_id = os.environ.get("PYTEST_XDIST_TESTRUNUID", readable_timestamp())
    experiment_name = f"{test_suite}:{unique_test_id}"
    if os.environ.get("EXPERIMENT_ID"):
        experiment_name = f'{test_suite}:{os.environ.get("EXPERIMENT_ID")}'
    return experiment_name


def get_dataset_name(test_suite: str):
    system_metadata = get_machine_state_tags()
    return f"{test_suite}:{system_metadata.get('branch', 'unknown_branch')}"


class ExperimentData(BaseModel):
    experiment_name: str
    records: List[Dict[str, Any]]
    test_cases: List[Dict[str, Any]]


def get_experiment_results(project_name: str, test_suite: str) -> ExperimentData:
    experiment_name = get_experiment_name(test_suite)
    experiment = braintrust.init(
        project=project_name, experiment=experiment_name, open=True
    )
    dataset = braintrust.init_dataset(
        project=project_name, name=get_dataset_name(test_suite)
    )
    records = list(experiment.fetch())
    test_cases = list(dataset.fetch())
    return ExperimentData(
        experiment_name=experiment_name,
        records=records,  # type: ignore
        test_cases=test_cases,  # type: ignore
    )
