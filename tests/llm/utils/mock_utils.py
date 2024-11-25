
import json
import braintrust
from typing_extensions import Dict
import yaml
import logging
import os
import re
from pathlib import Path
from typing import Generic, List, Optional, TypeVar, Union, cast

from pydantic import BaseModel, TypeAdapter
from holmes.core.models import InvestigateRequest
from holmes.core.tool_calling_llm import ResourceInstructions
from tests.llm.utils.constants import AUTO_GENERATED_FILE_SUFFIX
from tests.llm.utils.mock_toolset import MockMetadata, ToolMock

def read_file(file_path:Path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read().strip()


TEST_CASE_ID_PATTERN = r'^[\d+]_(?:[a-z]+_)*[a-z]+$'
CONFIG_FILE_NAME = "test_case.yaml"

class LLMEvaluation(BaseModel):
    answer_relevancy: float = 0.5
    faithfulness: float = 0.5
    contextual_precision: float = 0.5
    contextual_recall: float = 0
    contextual_relevancy: float = 0

class Message(BaseModel):
    message: str

T = TypeVar('T')

class HolmesTestCase(BaseModel):
    id: str
    folder: str
    mocks_passthrough: bool = False # If True, unmocked tools and dal can be invoked by the LLM without error
    expected_output: str # Whether an output is expected
    evaluation: LLMEvaluation = LLMEvaluation()
    retrieval_context: List[str] = [] # Elements helping to evaluate the correctness of the LLM response
    tool_mocks: List[ToolMock] = []

class AskHolmesTestCase(HolmesTestCase, BaseModel):
    user_prompt: str # The user's question to ask holmes

class InvestigateTestCase(HolmesTestCase, BaseModel):
    investigate_request: InvestigateRequest
    issue_data: Optional[Dict]
    resource_instructions: Optional[ResourceInstructions]

pydantic_tool_mock = TypeAdapter(MockMetadata)

def parse_mock_metadata(text) -> Optional[MockMetadata]:
    """
    Expects the mock metadata to be the first line of the text and be a JSON string.
    """
    try:
        match = re.match(r'^(.*)$', text, re.MULTILINE)
        if match:
            first_line = match.group(0)
            metadata = json.loads(first_line)
            return pydantic_tool_mock.validate_python(metadata)
        return None
    except Exception as e:
        logging.error(e)
        return None


class MockHelper():

    def __init__(self, test_cases_folder:Path) -> None:
        super().__init__()
        self._test_cases_folder = test_cases_folder


    def load_investigate_test_cases(self) -> List[InvestigateTestCase]:
        return cast(List[InvestigateTestCase], self._load_test_cases())

    def load_ask_holmes_test_cases(self) -> List[AskHolmesTestCase]:
        return cast(List[AskHolmesTestCase], self._load_test_cases())

    def _load_test_cases(self) -> List[HolmesTestCase]:

        test_cases:List[HolmesTestCase] = []
        test_cases_ids:List[str] = os.listdir(self._test_cases_folder)
        for test_case_id in test_cases_ids:
            test_case_folder = self._test_cases_folder.joinpath(test_case_id)
            logging.info("Evaluating potential test case folder: {test_case_folder}")
            try:
                config_dict = yaml.safe_load(read_file(test_case_folder.joinpath(CONFIG_FILE_NAME)))
                config_dict["id"] = test_case_id
                config_dict["folder"] = str(test_case_folder)

                if config_dict.get("user_prompt"):
                    test_case = TypeAdapter(AskHolmesTestCase).validate_python(config_dict)
                else:
                    config_dict["investigate_request"] = load_investigate_request(test_case_folder)
                    config_dict["issue_data"] = load_issue_data(test_case_folder)
                    config_dict["resource_instructions"] = load_resource_instructions(test_case_folder)
                    config_dict["request"] = TypeAdapter(InvestigateRequest)
                    test_case = TypeAdapter(InvestigateTestCase).validate_python(config_dict)

                logging.info(f"Successfully loaded test case {test_case_id}")
            except FileNotFoundError:
                logging.info(f"Folder {self._test_cases_folder}/{test_case_id} ignored because it is missing a {CONFIG_FILE_NAME} file.")
                continue

            mock_file_names:List[str] = os.listdir(test_case_folder)

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
                mock_value = mock_text[mock_text.find('\n') + 1:] # remove first line
                if not metadata:
                    logging.warning(f"Failed to parse metadata from test case file at {str(mock_file_path)}. It will be skipped")
                    continue
                tool_mock = ToolMock(
                    source_file=mock_file_name,
                    toolset_name= metadata.toolset_name,
                    tool_name= metadata.tool_name,
                    match_params= metadata.match_params,
                    return_value=mock_value
                )
                logging.info(f"Successfully loaded tool mock {tool_mock}")
                test_case.tool_mocks.append(tool_mock)
            test_cases.append(test_case)
        logging.info(f"Found {len(test_cases)} in {self._test_cases_folder}")

        return test_cases

def find_dataset_row_by_test_case(dataset:braintrust.Dataset, test_case:HolmesTestCase):
    for row in dataset:
        if row.get("metadata", {}).get("id") == test_case.id:
            return row
    return None


def upload_dataset(
    test_cases:Union[List[AskHolmesTestCase], List[InvestigateTestCase]],
    project_name:str,
    dataset_name:str):

    dataset = braintrust.init_dataset(project=project_name, name=dataset_name)
    for test_case in test_cases:

        input = ""
        if isinstance(test_case, AskHolmesTestCase):
            input = test_case.user_prompt
        elif isinstance(test_case, InvestigateTestCase):
            input = test_case.investigate_request
        else:
            raise Exception("Unsupported test case class")

        row = find_dataset_row_by_test_case(dataset, test_case)

        if row:
            dataset.update(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata=test_case.model_dump(),
                tags=[],
            )
        else:
            dataset.insert(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata=test_case.model_dump(),
                tags=[],
            )
        logging.info("Inserted dataset record with id", id)

    logging.info(dataset.summarize())

def load_investigate_request(test_case_folder:Path) -> InvestigateRequest:
    investigate_request_path = test_case_folder.joinpath(Path("investigate_request.json"))
    if investigate_request_path.exists():
        return TypeAdapter(InvestigateRequest).validate_json(read_file(Path(investigate_request_path)))
    raise Exception(f"Investigate test case declared in folder {str(test_case_folder)} should have an investigate_request.json file but none is present")

def load_issue_data(test_case_folder:Path) -> Optional[Dict]:

    issue_data_mock_path = test_case_folder.joinpath(Path("issue_data.json"))
    if issue_data_mock_path.exists():
        return json.loads(read_file(issue_data_mock_path))
    return None


def load_resource_instructions(test_case_folder:Path) -> Optional[ResourceInstructions]:
    resource_instructions_mock_path = test_case_folder.joinpath(Path("resource_instructions.json"))
    if resource_instructions_mock_path.exists():
        return TypeAdapter(ResourceInstructions).validate_json(read_file(Path(resource_instructions_mock_path)))
    return None
