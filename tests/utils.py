
import json
import yaml
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, TypeAdapter
from tests.mock_toolset import MockMetadata, ToolMock

def read_file(file_path:Path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read().strip()


TEST_CASE_ID_PATTERN = r'^[1-5]_(?:[a-z]+_)*[a-z]+$'
CONFIG_FILE_NAME = "test_case.yaml"

class Message(BaseModel):
    message: str

class AskHolmesFixture(BaseModel):
    mocks_required: bool = True # If True, an exception will be thrown if the LLM calls a tool that has not been mocked. You usually wants it to true because self contained tests are more stable.
    user_prompt: str # The user's question to ask holmes
    expected_output: str # Whether an output is expected
    retrieval_context: List[str] = [] # Elements helping to evaluate the correctness of the LLM response
    tool_mocks: List[ToolMock] = []

pydantic_fixture = TypeAdapter(AskHolmesFixture)
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

def load_ask_holmes_fixtures(fixtures_folder) -> List[AskHolmesFixture]:
    fixtures = []
    test_cases_ids:List[str] = os.listdir(fixtures_folder)
    for test_case_id in test_cases_ids:
        if not bool(re.match(TEST_CASE_ID_PATTERN, test_case_id)):
            continue
        test_case_folder = fixtures_folder.joinpath(test_case_id)
        try:
            config_dict = yaml.safe_load(read_file(test_case_folder.joinpath(CONFIG_FILE_NAME)))
            fixture:AskHolmesFixture = pydantic_fixture.validate_python(config_dict)
        except FileNotFoundError as e:
            logging.error(e)
            logging.warning(f"Test case {fixtures_folder}/{test_case_id} is missing a {CONFIG_FILE_NAME} file. This test case will be skipped.")
            continue

        mock_file_names = os.listdir(test_case_folder)
        mocks:List[ToolMock] = []
        for mock_file_name in mock_file_names:
            if mock_file_name == CONFIG_FILE_NAME:
                continue
            mock_file_path = test_case_folder.joinpath(mock_file_name)
            mock_text = read_file(mock_file_path)

            metadata = parse_mock_metadata(mock_text)
            mock_value = mock_text[mock_text.find('\n') + 1:] # remove first line
            if not metadata:
                logging.warning(f"Failed to parse metadata from fixture file at {str(mock_file_path)}. It will be skipped")
                continue;
            fixture.tool_mocks.append(
                ToolMock(
                    toolset_name= metadata.toolset_name,
                    tool_name= metadata.tool_name,
                    match_params= metadata.match_params,
                    return_value=mock_value
                )
            )
        fixtures.append(fixture)

    return fixtures
