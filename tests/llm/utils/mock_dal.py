# type: ignore
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import TypeAdapter

from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tool_calling_llm import ResourceInstructions
from holmes.plugins.runbooks import RobustaRunbookInstruction
from holmes.utils.global_instructions import Instructions
from tests.llm.utils.test_case_utils import read_file


class MockSupabaseDal(SupabaseDal):
    def __init__(
        self,
        test_case_folder: Path,
        issue_data: Optional[Dict],
        resource_instructions: Optional[ResourceInstructions],
        generate_mocks: bool,
        initialize_base: bool = True,
    ):
        if initialize_base:
            super().__init__(cluster="test")
        else:
            # For only using mock data without initializing the base class
            # Don't call super().__init__ to avoid initializing Supabase connection
            # Set necessary attributes that would normally be set by SupabaseDal.__init__
            self.enabled = True
            self.cluster = "test"

        self._issue_data = issue_data
        self._resource_instructions = resource_instructions
        self._test_case_folder = test_case_folder
        self._generate_mocks = generate_mocks

    def get_issue_data(self, issue_id: Optional[str]) -> Optional[Dict]:
        if self._issue_data is not None:
            return self._issue_data
        else:
            data = super().get_issue_data(issue_id)
            if self._generate_mocks:
                file_path = self._get_mock_file_path("issue_data")

                with open(file_path, "w") as f:
                    f.write(json.dumps(data or {}, indent=2))
                    f.close()

                logging.warning(
                    f"A mock file was generated for you at {file_path} with the contentof dal.get_issue_data({issue_id})"
                )

            return data

    def get_resource_instructions(
        self, type: str, name: Optional[str]
    ) -> Optional[ResourceInstructions]:
        if self._resource_instructions is not None:
            return self._resource_instructions
        else:
            data = super().get_resource_instructions(type, name)
            if self._generate_mocks:
                file_path = self._get_mock_file_path("resource_instructions")

                with open(file_path, "w") as f:
                    f.write(json.dumps(data or {}, indent=2))
                    f.close()

                logging.warning(
                    f"A mock file was generated for you at {file_path} with the contentof dal.get_resource_instructions({type}, {name})"
                )

                return data

    def get_runbook_catalog(self) -> Optional[List[RobustaRunbookInstruction]]:
        # Try to read from mock file first
        mock_file_path = self._get_mock_file_path("runbook_catalog")
        if mock_file_path.exists():
            try:
                with open(mock_file_path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [RobustaRunbookInstruction(**item) for item in data]
                    return None
            except Exception as e:
                logging.warning(f"Failed to read runbook catalog mock file: {e}")
        return None

    def get_runbook_content(
        self, runbook_id: str
    ) -> Optional[RobustaRunbookInstruction]:
        # Try to read from mock file first
        mock_file_path = self._get_mock_file_path(f"runbook_content_{runbook_id}")
        if mock_file_path.exists():
            try:
                with open(mock_file_path, "r") as f:
                    data = json.load(f)
                    return RobustaRunbookInstruction(**data)
            except Exception as e:
                logging.warning(f"Failed to read runbook content mock file: {e}")
        return None

    def _get_mock_file_path(self, entity_type: str) -> Path:
        return self._test_case_folder / f"{entity_type}.json"

    def get_global_instructions_for_account(self) -> Optional[Instructions]:
        # Try to read from mock file first
        mock_file_path = self._get_mock_file_path("global_instructions")
        if mock_file_path.exists():
            try:
                with open(mock_file_path, "r") as f:
                    data = json.load(f)
                    return Instructions(**data)
            except Exception as e:
                logging.warning(f"Failed to read global instructions mock file: {e}")

        return None

    def get_workload_issues(self, *args) -> list:
        return []


pydantic_resource_instructions = TypeAdapter(ResourceInstructions)
pydantic_instructions = TypeAdapter(Instructions)


def load_mock_dal(
    test_case_folder: Path, generate_mocks: bool, initialize_base: bool = True
):
    issue_data_mock_path = test_case_folder.joinpath(Path("issue_data.json"))
    issue_data = None
    if issue_data_mock_path.exists():
        issue_data = json.loads(read_file(issue_data_mock_path))

    resource_instructions_mock_path = test_case_folder.joinpath(
        Path("resource_instructions.json")
    )
    resource_instructions = None
    if resource_instructions_mock_path.exists():
        resource_instructions = pydantic_resource_instructions.validate_json(
            read_file(Path(resource_instructions_mock_path))
        )

    return MockSupabaseDal(
        test_case_folder=test_case_folder,
        issue_data=issue_data,
        resource_instructions=resource_instructions,
        generate_mocks=generate_mocks,
        initialize_base=initialize_base,
    )
