import json
from typing_extensions import Dict
import yaml
import logging
import os
from pathlib import Path
from typing import Any, List, Literal, Optional, TypeVar, Union, cast

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError, ConfigDict
from holmes.core.models import InvestigateRequest, WorkloadHealthRequest
from holmes.core.prompt import append_file_to_user_prompt

from holmes.core.tool_calling_llm import ResourceInstructions
from tests.llm.utils.constants import ALLOWED_EVAL_TAGS, get_allowed_tags_list


class SetupFailureError(Exception):
    """Custom exception for setup failures with additional context."""

    def __init__(
        self,
        message: str,
        test_id: str,
        command: Optional[str] = None,
        output: Optional[str] = None,
    ):
        super().__init__(message)
        self.test_id = test_id
        self.command = command
        self.output = output


def get_models():
    """Get list of models to test from MODEL env var (supports comma-separated list)."""
    models_str = os.environ.get("MODEL", "gpt-4o")
    return models_str.split(",")


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
    model_config = ConfigDict(extra="forbid")

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
    description: Optional[str] = None
    generate_mocks: Optional[bool] = None
    toolsets: Optional[Dict[str, Any]] = None
    port_forwards: Optional[List[Dict[str, Any]]] = (
        None  # Port forwarding configurations
    )


class AskHolmesTestCase(HolmesTestCase, BaseModel):
    user_prompt: Union[
        str, List[str]
    ]  # The user's question(s) to ask holmes - can be single string or array
    cluster_name: Optional[str] = None
    include_files: Optional[List[str]] = None  # matches include_files option of the CLI
    runbooks: Optional[Dict[str, Any]] = None  # Optional runbook catalog override

    # Internal fields for variant handling
    variant_index: Optional[int] = None  # Which variant this instance represents
    original_user_prompt: Optional[Union[str, List[str]]] = (
        None  # Store original prompt(s)
    )
    test_type: Optional[str] = None  # The type of test to run


class InvestigateTestCase(HolmesTestCase, BaseModel):
    investigate_request: InvestigateRequest
    issue_data: Optional[Dict]
    resource_instructions: Optional[ResourceInstructions]
    expected_sections: Optional[Dict[str, Union[List[str], bool]]] = None
    request: Any = None


class HealthCheckTestCase(HolmesTestCase, BaseModel):
    workload_health_request: WorkloadHealthRequest
    issue_data: Optional[Dict]
    resource_instructions: Optional[ResourceInstructions]
    expected_sections: Optional[Dict[str, Union[List[str], bool]]] = None
    request: Any = None


def check_and_skip_test(
    test_case: HolmesTestCase, request=None, shared_test_infrastructure=None
) -> None:
    """Check if test should be skipped or has setup failures, and raise appropriate pytest exceptions.

    Args:
        test_case: A HolmesTestCase or any of its subclasses
        request: The pytest request object (optional, needed for setup failure tracking)
        shared_test_infrastructure: Shared test infrastructure dict (optional, needed for setup failure checking)
    """
    # Check if test should be skipped
    if test_case.skip:
        pytest.skip(test_case.skip_reason or "Test skipped")

    # Check if --only-setup is set
    if request and request.config.getoption("--only-setup", False):
        print("   ⚙️  --only-setup mode: Skipping test execution, only ran setup")
        pytest.skip("Skipping test execution due to --only-setup flag")

    # Check for setup failures - early return if no infrastructure or request
    if shared_test_infrastructure is None or request is None:
        return

    setup_failures = shared_test_infrastructure.get("setup_failures", {})
    if test_case.id in setup_failures:
        setup_error_detail = setup_failures[test_case.id]
        request.node.user_properties.append(("is_setup_failure", True))
        request.node.user_properties.append(
            ("setup_failure_detail", setup_error_detail)
        )

        # Just pass the full error detail through - no parsing needed
        raise SetupFailureError(
            message=setup_error_detail,
            test_id=test_case.id,
            command="Setup script",
            output=setup_error_detail,  # Full details including stdout/stderr
        )


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

    def _add_port_forward_tag(self, test_case: HolmesTestCase) -> None:
        """Automatically add port-forward tag if test has port forwards."""
        if test_case and test_case.port_forwards:
            if test_case.tags is None:
                test_case.tags = []
            if "port-forward" not in test_case.tags:
                test_case.tags.append("port-forward")

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
                test_case: Optional[HolmesTestCase] = None

                if config_dict.get("user_prompt"):
                    config_dict["conversation_history"] = load_conversation_history(
                        test_case_folder
                    )
                    extra_prompt = load_include_files(
                        test_case_folder, config_dict.get("include_files", None)
                    )

                    original_user_prompt = config_dict["user_prompt"]

                    # Handle array of user prompts - create multiple test case instances
                    if isinstance(original_user_prompt, list):
                        for i, prompt in enumerate(original_user_prompt):
                            variant_config = config_dict.copy()
                            variant_config["user_prompt"] = prompt + extra_prompt
                            variant_config["variant_index"] = i
                            variant_config["original_user_prompt"] = (
                                original_user_prompt
                            )
                            variant_config["id"] = f"{test_case_id}[{i}]"
                            test_case = TypeAdapter(AskHolmesTestCase).validate_python(
                                variant_config
                            )
                            self._add_port_forward_tag(test_case)
                            test_cases.append(test_case)
                        continue  # Skip the normal append at the end
                    else:
                        # Single prompt case
                        config_dict["user_prompt"] = (
                            config_dict["user_prompt"] + extra_prompt
                        )
                        config_dict["original_user_prompt"] = original_user_prompt
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
                else:
                    # Skip test cases that don't match any known type
                    logging.debug(
                        f"Skipping test case {test_case_id} - unknown test type"
                    )
                    continue

                self._add_port_forward_tag(test_case)

                logging.debug(f"Successfully loaded test case {test_case_id}")
                test_cases.append(test_case)
            except ValidationError as e:
                problematic_tags = []
                for error in e.errors():
                    if error["type"] == "literal_error" and "tags" in str(error["loc"]):
                        problematic_tags.append(error["input"])

                if problematic_tags:
                    error_msg = (
                        f"VALIDATION ERROR in test case: {test_case_folder.name}\n"
                    )
                    error_msg += f"Problematic tags: {', '.join(problematic_tags)}\n"
                    error_msg += f"Allowed tags; {get_allowed_tags_list()}"
                    print(error_msg)
                raise e
            except FileNotFoundError:
                logging.debug(
                    f"Folder {self._test_cases_folder}/{test_case_id} ignored because it is missing a {CONFIG_FILE_NAME} file."
                )
                continue
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


def _parse_conversation_history_md_files(
    conversation_history_dir,
) -> None | List[Dict[str, str]]:
    # If no .md files are found in the directory, return None.
    md_files = sorted(list(conversation_history_dir.glob("*.md")))

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
    if conversation_history_dir.is_dir():
        conversation_history = _parse_conversation_history_md_files(
            conversation_history_dir
        )
    elif test_case_folder.joinpath("conversation_history.json").exists():
        conversation_history = json.loads(
            read_file(test_case_folder.joinpath("conversation_history.json"))
        )
    else:
        conversation_history = None

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
