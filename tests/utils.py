
import json
import yaml
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, TypeAdapter
from tests.mock_toolset import AUTO_GENERATED_FILE_SUFFIX, MockMetadata, ToolMock

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

class AskHolmesTestCase(BaseModel):
    id: str
    folder: str
    tools_passthrough: bool = False # If True, unmocked tools can be invoked by the LLM without error
    user_prompt: str # The user's question to ask holmes
    expected_output: str # Whether an output is expected
    evaluation: LLMEvaluation = LLMEvaluation()
    retrieval_context: List[str] = [] # Elements helping to evaluate the correctness of the LLM response
    tool_mocks: List[ToolMock] = []

pydantic_test_case = TypeAdapter(AskHolmesTestCase)
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

def load_ask_holmes_test_cases(test_cases_folder:Path, expected_number_of_test_cases=-1) -> List[AskHolmesTestCase]:

    test_cases = []
    test_cases_ids:List[str] = os.listdir(test_cases_folder)
    for test_case_id in test_cases_ids:
        test_case_folder = test_cases_folder.joinpath(test_case_id)
        logging.info("Evaluating potential test case folder: {test_case_folder}")
        try:
            config_dict = yaml.safe_load(read_file(test_case_folder.joinpath(CONFIG_FILE_NAME)))
            config_dict["id"] = test_case_id
            config_dict["folder"] = str(test_case_folder)
            test_case:AskHolmesTestCase = pydantic_test_case.validate_python(config_dict)
            logging.info(f"Successfully loaded test case {test_case_id}")
        except FileNotFoundError:
            logging.info(f"Folder {test_cases_folder}/{test_case_id} ignored because it is missing a {CONFIG_FILE_NAME} file.")
            continue

        mock_file_names:List[str] = os.listdir(test_case_folder)

        for mock_file_name in mock_file_names:
            if mock_file_name == CONFIG_FILE_NAME:
                continue
            if mock_file_name.endswith(AUTO_GENERATED_FILE_SUFFIX):
                continue
            mock_file_path = test_case_folder.joinpath(mock_file_name)
            mock_text = read_file(mock_file_path)

            metadata = parse_mock_metadata(mock_text)
            mock_value = mock_text[mock_text.find('\n') + 1:] # remove first line
            if not metadata:
                logging.warning(f"Failed to parse metadata from test case file at {str(mock_file_path)}. It will be skipped")
                continue
            tool_mock = ToolMock(
                source_file=str(mock_file_path),
                toolset_name= metadata.toolset_name,
                tool_name= metadata.tool_name,
                match_params= metadata.match_params,
                return_value=mock_value
            )
            logging.info(f"Successfully loaded tool mock {tool_mock}")
            test_case.tool_mocks.append(tool_mock)
        test_cases.append(test_case)
    logging.info(f"Found {len(test_cases)} in {test_cases_folder}")

    if expected_number_of_test_cases > 0:
        assert len(test_cases) == expected_number_of_test_cases
    return test_cases
