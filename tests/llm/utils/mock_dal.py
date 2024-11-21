import json
import logging
from pathlib import Path
from typing import Dict, Optional

from pydantic import TypeAdapter

from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tool_calling_llm import ResourceInstructions
from tests.llm.utils.constants import AUTO_GENERATED_FILE_SUFFIX
from tests.llm.utils.mock_utils import load_issue_data, load_resource_instructions, read_file

class MockSupabaseDal(SupabaseDal):

    def __init__(self, test_case_folder:Path, issue_data:Optional[Dict], resource_instructions:Optional[ResourceInstructions], dal_passthrough:bool):
        super().__init__()
        self._issue_data = issue_data
        self._resource_instructions = resource_instructions
        self._test_case_folder = test_case_folder
        self._dal_passthrough = dal_passthrough

    def get_issue_data(self, issue_id: Optional[str]) -> Optional[Dict]:
        if self._issue_data is not None:
            return self._issue_data
        else:
            file_path = self._get_mock_file_path("issue_data")
            data = super().get_issue_data(issue_id)
            file_path = self._get_mock_file_path("issue_data")

            with open(file_path, 'w') as f:
                f.write(json.dumps(data or {}, indent=2))
                f.close()

            logging.warning(f"A mock file was generated for you at {file_path} with the contentof dal.get_issue_data({issue_id})")
            if self._dal_passthrough:
                return data
            else:
                raise Exception(f"dal.get_issue_data({issue_id}) was invoked and is not mocked. A mock file was generated for you at {file_path}. Remove the '{AUTO_GENERATED_FILE_SUFFIX}' suffix to enable that file")

    def get_resource_instructions(self, type: str, name: Optional[str]) -> Optional[ResourceInstructions]:
        if self._resource_instructions is not None:
            return self._resource_instructions
        else:
            data = super().get_resource_instructions(type, name)
            file_path = self._get_mock_file_path("resource_instructions")

            with open(file_path, 'w') as f:
                f.write(json.dumps(data or {}, indent=2))
                f.close()

            logging.warning(f"A mock file was generated for you at {file_path} with the contentof dal.get_resource_instructions({type}, {name})")
            if self._dal_passthrough:
                return data
            else:
                raise Exception(f"dal.get_resource_instructions({type}, {name}) was invoked and is not mocked. A mock file was generated for you at {file_path}. Remove the '{AUTO_GENERATED_FILE_SUFFIX}' suffix to enable that file")

    def _get_mock_file_path(self, entity_type:str):
        return f"{self._test_case_folder}/{entity_type}.json{AUTO_GENERATED_FILE_SUFFIX}"

pydantic_resource_instructions = TypeAdapter(ResourceInstructions)

def load_mock_dal(test_case_folder:Path, dal_passthrough:bool = False):
    issue_data = load_issue_data(test_case_folder)
    resource_instructions = load_resource_instructions(test_case_folder)

    return MockSupabaseDal(
        test_case_folder=test_case_folder,
        issue_data=issue_data,
        resource_instructions=resource_instructions,
        dal_passthrough=dal_passthrough
    )
