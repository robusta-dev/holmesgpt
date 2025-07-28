# TODO: we can remove most of this now and just use tracing.py
import braintrust
from braintrust import Dataset, Experiment, ReadonlyExperiment, Span
import logging
from typing import Any, List, Optional, Union

from tests.llm.utils.test_case_utils import HolmesTestCase  # type: ignore
from holmes.core.tracing import (
    DummySpan,
    BRAINTRUST_API_KEY,
    BRAINTRUST_PROJECT,
    BRAINTRUST_ORG,
    get_machine_state_tags,
    get_experiment_name,
)


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

    # TODO: remove and use BraintrustTracer instead
    def start_evaluation(
        self, experiment_name: str, name: str
    ) -> Union[Span, DummySpan]:
        if not self.dataset:
            # braintrust is disabled
            return DummySpan()
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

        # Create the span directly from experiment (tests manage their own spans)
        if self.experiment:
            self._root_span = self.experiment.start_span(name=name)
            return self._root_span
        else:
            return DummySpan()

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


def get_dataset_name(test_suite: str):
    system_metadata = get_machine_state_tags()
    return f"{test_suite}:{system_metadata.get('branch', 'unknown_branch')}"


def get_braintrust_url(
    span_id: Optional[str] = None,
    root_span_id: Optional[str] = None,
) -> Optional[str]:
    """Generate Braintrust URL for a test.

    Args:
        test_suite: Either "ask_holmes" or "investigate"
        test_id: Test ID like "01"
        test_name: Test name like "how_many_pods"
        span_id: Optional span ID for direct linking
        root_span_id: Optional root span ID for direct linking

    Returns:
        Braintrust URL string, or None if Braintrust is not configured
    """
    if not BRAINTRUST_API_KEY:
        return None

    experiment_name = get_experiment_name()

    # Build URL with available parameters
    url = f"https://www.braintrust.dev/app/{BRAINTRUST_ORG}/p/{BRAINTRUST_PROJECT}/experiments/{experiment_name}?c="

    # Add span IDs if available
    if span_id and root_span_id:
        # Use span_id as r parameter and root_span_id as s parameter
        url += f"&r={span_id}&s={root_span_id}"

    return url
