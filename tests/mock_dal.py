import json
from pathlib import Path
from os import path
from typing import Dict, Optional

from pydantic import TypeAdapter

from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tool_calling_llm import ResourceInstructions
from tests.mock_utils import read_file


basepath = path.dirname(__file__)
filepath = path.abspath(path.join(basepath, "fixtures", "test_investigate", "01_crashloop_backoff", "investigation_request.json"))
class MockSupabaseDal(SupabaseDal):

    def __init__(self, issue_data:Optional[Dict], resource_instructions:Optional[ResourceInstructions]):
        super().__init__()
        self._issue_data = issue_data
        self._resource_instructions = resource_instructions

    def get_issue_data(self, issue_id: Optional[str]) -> Optional[Dict]:
        if self._issue_data:
            return self._issue_data
        else:
            # TODO: create draft mockl file
            return None

    def get_resource_instructions(self, type: str, name: Optional[str]) -> Optional[ResourceInstructions]:
        if self._resource_instructions:
            return self._resource_instructions
        else:
            # TODO: create draft mockl file
            return None


pydantic_resource_instructions = TypeAdapter(ResourceInstructions)

def load_mock_dal(test_case_folder:Path):
    issue_data_mock_path = test_case_folder.joinpath(Path("issue_data.json"))
    issue_data = None
    if issue_data_mock_path.exists():
        issue_data = json.loads(read_file(issue_data_mock_path))


    resource_instructions_mock_path = test_case_folder.joinpath(Path("resource_instructions.json"))
    resource_instructions = None
    if resource_instructions_mock_path.exists():
        resource_instructions = pydantic_resource_instructions.validate_json(read_file(Path(resource_instructions_mock_path)))

    return MockSupabaseDal(issue_data=issue_data, resource_instructions=resource_instructions)
