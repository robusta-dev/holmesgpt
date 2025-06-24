# type: ignore
import json
from typing_extensions import Dict
import yaml
import logging
import os
import re
from pathlib import Path
from typing import List, Literal, Optional, TypeVar, Union, cast

from pydantic import BaseModel, TypeAdapter
from holmes.core.models import InvestigateRequest
from holmes.core.prompt import append_file_to_user_prompt
from holmes.core.tool_calling_llm import ResourceInstructions
from tests.llm.utils.constants import ALLOWED_EVAL_TAGS, AUTO_GENERATED_FILE_SUFFIX
from tests.llm.utils.mock_toolset import MockMetadata, ToolMock
from holmes.core.tools import StructuredToolResult, ToolResultStatus


def read_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read().strip()


TEST_CASE_ID_PATTERN = r"^[\d+]_(?:[a-z]+_)*[a-z]+$"
CONFIG_FILE_NAME = "test_case.yaml"


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
    generate_mocks: bool = False  # If True, generate mocks
    add_params_to_mock_file: bool = True
    expected_output: Union[str, List[str]]  # Whether an output is expected
    evaluation: LLMEvaluations = LLMEvaluations()
    tool_mocks: List[ToolMock] = []
    before_test: Optional[str] = None
    after_test: Optional[str] = None
    conversation_history: Optional[list[dict]] = None


class AskHolmesTestCase(HolmesTestCase, BaseModel):
    user_prompt: str  # The user's question to ask holmes
    include_files: Optional[List[str]] = None  # matches include_files option of the CLI


class InvestigateTestCase(HolmesTestCase, BaseModel):
    investigate_request: InvestigateRequest
    issue_data: Optional[Dict]
    resource_instructions: Optional[ResourceInstructions]
    expected_sections: Optional[Dict[str, Union[List[str], bool]]] = None


pydantic_tool_mock = TypeAdapter(MockMetadata)


def parse_mock_metadata(text) -> Optional[MockMetadata]:
    """
    Expects the mock metadata to be the first line of the text and be a JSON string.
    """
    try:
        match = re.match(r"^(.*)$", text, re.MULTILINE)
        if match:
            first_line = match.group(0)
            metadata = json.loads(first_line)
            return pydantic_tool_mock.validate_python(metadata)
        return None
    except Exception as e:
        logging.error(e)
        return None


def parse_structured_json(
    text: str, metadata: Optional[MockMetadata]
) -> StructuredToolResult:
    """
    Expects the mock metadata to be the first line of the text and be a JSON string.
    """
    try:
        match = re.match(r"^(.*)$", text, re.MULTILINE)
        first_line = match.group(0)
        parsed_json = json.loads(first_line)
        result = StructuredToolResult(**parsed_json)
        data = text[text.find("\n") + 1 :]  # remove first line
        result.data = data
        return result
    except Exception as e:
        logging.info(
            f"Failed to parse mock value as StructuredToolResult: {e}. Using mock value as string"
        )
        params = {}
        if metadata and metadata.match_params:
            params = metadata.match_params
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=text,
            params=params,
        )


class MockHelper:
    def __init__(self, test_cases_folder: Path) -> None:
        super().__init__()
        self._test_cases_folder = test_cases_folder

    def load_investigate_test_cases(self) -> List[InvestigateTestCase]:
        return cast(List[InvestigateTestCase], self.load_test_cases())

    def load_ask_holmes_test_cases(self) -> List[AskHolmesTestCase]:
        return cast(List[AskHolmesTestCase], self.load_test_cases())

    def load_test_cases(self) -> List[HolmesTestCase]:
        test_cases: List[HolmesTestCase] = []
        test_cases_ids: List[str] = [
            f for f in os.listdir(self._test_cases_folder) if not f.startswith(".")
        ]  # ignoring hidden files like Mac's .DS_Store
        for test_case_id in test_cases_ids:
            test_case_folder = self._test_cases_folder.joinpath(test_case_id)
            logging.info("Evaluating potential test case folder: {test_case_folder}")
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
                else:
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

                logging.info(f"Successfully loaded test case {test_case_id}")
            except FileNotFoundError:
                logging.info(
                    f"Folder {self._test_cases_folder}/{test_case_id} ignored because it is missing a {CONFIG_FILE_NAME} file."
                )
                continue

            mock_file_names: List[str] = os.listdir(test_case_folder)

            for mock_file_name in mock_file_names:
                if mock_file_name == CONFIG_FILE_NAME:
                    continue
                if mock_file_name.endswith(AUTO_GENERATED_FILE_SUFFIX):
                    continue
                if not mock_file_name.endswith(".txt"):
                    continue
                mock_file_path = test_case_folder.joinpath(mock_file_name)
                mock_text = read_file(mock_file_path)

                metadata = parse_mock_metadata(mock_text)
                mock_value = mock_text[mock_text.find("\n") + 1 :]  # remove first line

                tool_structured_result = parse_structured_json(mock_value, metadata)
                if not metadata:
                    logging.warning(
                        f"Failed to parse metadata from test case file at {str(mock_file_path)}. It will be skipped"
                    )
                    continue
                tool_mock = ToolMock(
                    source_file=mock_file_name,
                    toolset_name=metadata.toolset_name,
                    tool_name=metadata.tool_name,
                    match_params=metadata.match_params,
                    return_value=tool_structured_result,
                )
                logging.info(f"Successfully loaded tool mock {tool_mock}")
                test_case.tool_mocks.append(tool_mock)
            test_cases.append(test_case)
        logging.info(f"Found {len(test_cases)} in {self._test_cases_folder}")

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
