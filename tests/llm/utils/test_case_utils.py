# type: ignore
import json
from typing_extensions import Dict
import yaml
import logging
import os
from pathlib import Path
from typing import Any, List, Literal, Optional, TypeVar, Union, cast

import pytest
from pydantic import BaseModel, TypeAdapter
from holmes.core.models import InvestigateRequest, WorkloadHealthRequest
from holmes.core.prompt import append_file_to_user_prompt

from holmes.core.tool_calling_llm import ResourceInstructions
from tests.llm.utils.constants import ALLOWED_EVAL_TAGS


def read_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read().strip()


TEST_CASE_ID_PATTERN = r"^[\d+]_(?:[a-z]+_)*[a-z]+$"
CONFIG_FILE_NAME = "test_case.yaml"


# TODO: do we ever use this? or do we always just use float below
class Evaluation(BaseModel):
    expected_score: float = 1
    type: Union[Literal["loose"], Literal["strict"]]


class LLMEvaluations(BaseModel):
    correctness: Union[float, Evaluation] = 1


class Message(BaseModel):
    message: str


T = TypeVar("T")


class HolmesTestCase(BaseModel):
    id: str
    folder: str
    mocked_date: Optional[str] = None
    tags: Optional[list[ALLOWED_EVAL_TAGS]] = None
    skip: Optional[bool] = None
    skip_reason: Optional[str] = None
    expected_output: Union[str, List[str]]  # Whether an output is expected
    evaluation: LLMEvaluations = LLMEvaluations()
    before_test: Optional[str] = None
    after_test: Optional[str] = None
    conversation_history: Optional[list[dict]] = None
    test_env_vars: Optional[Dict[str, str]] = (
        None  # Environment variables to set during test execution
    )
    mock_policy: Optional[str] = (
        "inherit"  # Mock policy: always_mock, never_mock, or inherit
    )


class AskHolmesTestCase(HolmesTestCase, BaseModel):
    user_prompt: str  # The user's question to ask holmes
    cluster_name: Optional[str] = None
    include_files: Optional[List[str]] = None  # matches include_files option of the CLI
    runbooks: Optional[Dict[str, Any]] = None  # Optional runbook catalog override


class InvestigateTestCase(HolmesTestCase, BaseModel):
    investigate_request: InvestigateRequest
    issue_data: Optional[Dict]
    resource_instructions: Optional[ResourceInstructions]
    expected_sections: Optional[Dict[str, Union[List[str], bool]]] = None


class HealthCheckTestCase(HolmesTestCase, BaseModel):
    workload_health_request: WorkloadHealthRequest
    issue_data: Optional[Dict]
    resource_instructions: Optional[ResourceInstructions]
    expected_sections: Optional[Dict[str, Union[List[str], bool]]] = None


def check_and_skip_test(test_case: HolmesTestCase) -> None:
    """Check if test should be skipped and raise pytest.skip if needed.

    Args:
        test_case: A HolmesTestCase or any of its subclasses
    """
    if test_case.skip:
        pytest.skip(test_case.skip_reason or "Test skipped")


class MockHelper:
    def __init__(self, test_cases_folder: Path) -> None:
        super().__init__()
        self._test_cases_folder = test_cases_folder

    def load_workload_health_test_cases(self) -> List[HealthCheckTestCase]:
        return cast(List[HealthCheckTestCase], self.load_test_cases())

    def load_investigate_test_cases(self) -> List[InvestigateTestCase]:
        return cast(List[InvestigateTestCase], self.load_test_cases())

    def load_ask_holmes_test_cases(self) -> List[AskHolmesTestCase]:
        return cast(List[AskHolmesTestCase], self.load_test_cases())

    def load_test_cases(self) -> List[HolmesTestCase]:
        test_cases: List[HolmesTestCase] = []
        test_cases_ids: List[str] = [
            f
            for f in os.listdir(self._test_cases_folder)
            if not f.startswith(".")
            and os.path.isdir(self._test_cases_folder.joinpath(f))
        ]  # ignoring hidden files like Mac's .DS_Store and non-directory files
        for test_case_id in test_cases_ids:
            test_case_folder = self._test_cases_folder.joinpath(test_case_id)
            logging.debug(f"Evaluating potential test case folder: {test_case_folder}")
            try:
                config_dict = yaml.safe_load(
                    read_file(test_case_folder.joinpath(CONFIG_FILE_NAME))
                )
                config_dict["id"] = test_case_id
                config_dict["folder"] = str(test_case_folder)

                if config_dict.get("user_prompt"):
                    config_dict["conversation_history"] = load_conversation_history(
                        test_case_folder
                    )
                    extra_prompt = load_include_files(
                        test_case_folder, config_dict.get("include_files", None)
                    )
                    config_dict["user_prompt"] = (
                        config_dict["user_prompt"] + extra_prompt
                    )
                    test_case = TypeAdapter(AskHolmesTestCase).validate_python(
                        config_dict
                    )
                elif self._test_cases_folder.name == "test_investigate":
                    config_dict["investigate_request"] = load_investigate_request(
                        test_case_folder
                    )
                    config_dict["issue_data"] = load_issue_data(test_case_folder)
                    config_dict["resource_instructions"] = load_resource_instructions(
                        test_case_folder
                    )
                    config_dict["request"] = TypeAdapter(InvestigateRequest)
                    test_case = TypeAdapter(InvestigateTestCase).validate_python(
                        config_dict
                    )
                elif self._test_cases_folder.name == "test_workload_health":
                    config_dict["workload_health_request"] = (
                        load_workload_health_request(test_case_folder)
                    )
                    config_dict["issue_data"] = load_issue_data(test_case_folder)
                    config_dict["resource_instructions"] = load_resource_instructions(
                        test_case_folder
                    )
                    config_dict["request"] = TypeAdapter(WorkloadHealthRequest)
                    test_case = TypeAdapter(HealthCheckTestCase).validate_python(
                        config_dict
                    )

                logging.debug(f"Successfully loaded test case {test_case_id}")
            except FileNotFoundError:
                logging.debug(
                    f"Folder {self._test_cases_folder}/{test_case_id} ignored because it is missing a {CONFIG_FILE_NAME} file."
                )
                continue

            test_cases.append(test_case)
        logging.debug(f"Found {len(test_cases)} in {self._test_cases_folder}")

        return test_cases


def load_issue_data(test_case_folder: Path) -> Optional[Dict]:
    issue_data_mock_path = test_case_folder.joinpath(Path("issue_data.json"))
    if issue_data_mock_path.exists():
        return json.loads(read_file(issue_data_mock_path))
    return None


def load_resource_instructions(
    test_case_folder: Path,
) -> Optional[ResourceInstructions]:
    resource_instructions_mock_path = test_case_folder.joinpath(
        Path("resource_instructions.json")
    )
    if resource_instructions_mock_path.exists():
        return TypeAdapter(ResourceInstructions).validate_json(
            read_file(Path(resource_instructions_mock_path))
        )
    return None


def load_investigate_request(test_case_folder: Path) -> InvestigateRequest:
    investigate_request_path = test_case_folder.joinpath(
        Path("investigate_request.json")
    )
    if investigate_request_path.exists():
        return TypeAdapter(InvestigateRequest).validate_json(
            read_file(Path(investigate_request_path))
        )
    raise Exception(
        f"Investigate test case declared in folder {str(test_case_folder)} should have an investigate_request.json file but none is present"
    )


def load_workload_health_request(test_case_folder: Path) -> WorkloadHealthRequest:
    workload_health_request_path = test_case_folder.joinpath(
        Path("workload_health_request.json")
    )
    if workload_health_request_path.exists():
        return TypeAdapter(WorkloadHealthRequest).validate_json(
            read_file(Path(workload_health_request_path))
        )
    raise Exception(
        f"Workload health test case declared in folder {str(test_case_folder)} should have an workload_health_request.json file but none is present"
    )


def load_conversation_history(test_case_folder: Path) -> Optional[list[dict[str, str]]]:
    """
    Loads conversation history from .md files in a specified folder structure.

    The folder structure is expected to be:
    test_case_folder/
        conversation_history/
            <index>_<role>.md
            ...
    """
    conversation_history_dir = test_case_folder / "conversation_history"

    if not conversation_history_dir.is_dir():
        return None

    md_files = sorted(list(conversation_history_dir.glob("*.md")))

    # If no .md files are found in the directory, return None.
    if not md_files:
        return None

    conversation_history: list[dict[str, str]] = []
    for md_file_path in md_files:
        # Get the filename without the .md extension (the "stem")
        # e.g., "01_system.md" -> "01_system"
        stem = md_file_path.stem

        # The filename pattern is "<index>_<role>.md".
        # The role is the part of the stem after the first underscore.
        # Example: "01_system" -> role is "system"
        # str.split("_", 1) splits the string at the first underscore.
        # It will return a list of two strings if an underscore is present.
        # e.g., "01_system".split("_", 1) -> ["01", "system"]
        try:
            _index_part, role = stem.split("_", 1)
        except ValueError:
            raise ValueError(
                f"Filename '{md_file_path.name}' in '{conversation_history_dir}' "
                f"does not conform to the expected '<index>_<role>.md' pattern."
            )

        content = md_file_path.read_text(encoding="utf-8")

        conversation_history.append({"role": role, "content": content})

    return conversation_history


def load_include_files(
    test_case_folder: Path, include_files: Optional[list[str]]
) -> str:
    extra_prompt: str = ""
    if include_files:
        for file_path_str in include_files:
            file_path = Path(test_case_folder.joinpath(file_path_str))
            extra_prompt = append_file_to_user_prompt(extra_prompt, file_path)

    return extra_prompt
