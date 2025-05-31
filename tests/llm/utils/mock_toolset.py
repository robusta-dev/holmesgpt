import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from holmes.core.tools import StructuredToolResult, Tool, Toolset, ToolsetStatusEnum
from holmes.plugins.toolsets import load_builtin_toolsets, load_toolsets_from_file
from tests.llm.utils.constants import AUTO_GENERATED_FILE_SUFFIX

ansi_escape = re.compile(r"\x1B\[([0-9]{1,3}(;[0-9]{1,2};?)?)?[mGK]")


def strip_ansi(text):
    return ansi_escape.sub("", text)


class MockMetadata(BaseModel):
    toolset_name: str
    tool_name: str
    match_params: Optional[Dict] = None  # None will match all params


class ToolMock(MockMetadata):
    source_file: str
    return_value: StructuredToolResult


class SaveMockTool(Tool):
    """
    Tool that raises an exception if invoked.
    It is used to fail tests if not all invoked tool calls are mocked. This ensures stable test conditions
    """

    toolset_name: str
    unmocked_tool: Tool
    test_case_folder: str

    def __init__(
        self, unmocked_tool: Tool, test_case_folder: str, toolset_name: str = "Unknown"
    ):
        super().__init__(
            name=unmocked_tool.name,
            description=unmocked_tool.description,
            parameters=unmocked_tool.parameters,
            user_description=unmocked_tool.user_description,
            toolset_name=toolset_name,
            unmocked_tool=unmocked_tool,
            test_case_folder=test_case_folder,
        )

    def _get_mock_file_path(self):
        return f"{self.test_case_folder}/{self.name}.txt{AUTO_GENERATED_FILE_SUFFIX}"

    def _auto_generate_mock_file(self, params: Dict):
        mock_file_path = self._get_mock_file_path()
        logging.warning(f"Writing mock file for your convenience at {mock_file_path}")

        mock_metadata_json = MockMetadata(
            toolset_name=self.toolset_name, tool_name=self.name, match_params=params
        ).model_dump_json()

        logging.info(f"Invoking tool {self.unmocked_tool}")
        output = self.unmocked_tool.invoke(params)
        content = output.data
        structured_output_without_data = output.model_dump()
        structured_output_without_data["data"] = None
        with open(mock_file_path, "w") as f:
            f.write(mock_metadata_json + "\n")
            f.write(json.dumps(structured_output_without_data) + "\n")
            if content:
                f.write(content)

        return output

    def _invoke(self, params) -> StructuredToolResult:
        return self._auto_generate_mock_file(params)

    def get_parameterized_one_liner(self, params) -> str:
        return self.unmocked_tool.get_parameterized_one_liner(params)


class MockToolWrapper(Tool):
    unmocked_tool: Tool
    mocks: List[ToolMock] = []

    def __init__(self, unmocked_tool: Tool):
        super().__init__(
            name=unmocked_tool.name,
            description=unmocked_tool.description,
            parameters=unmocked_tool.parameters,
            user_description=unmocked_tool.user_description,
            unmocked_tool=unmocked_tool,
        )

    def find_matching_mock(self, params: Dict) -> Optional[ToolMock]:
        for mock in self.mocks:
            if not mock.match_params:  # wildcard
                return mock

            match = all(
                key in params and params[key] == mock_val or mock_val == "*"
                for key, mock_val in mock.match_params.items()
            )
            if match:
                return mock

    def _invoke(self, params) -> StructuredToolResult:
        mock = self.find_matching_mock(params)
        if mock:
            return mock.return_value
        else:
            return self.unmocked_tool.invoke(params)

    def get_parameterized_one_liner(self, params) -> str:
        return self.unmocked_tool.get_parameterized_one_liner(params)


class MockToolset(Toolset):
    def get_example_config(self) -> Dict[str, Any]:
        return {}


class MockToolsets:
    unmocked_toolsets: List[Toolset]
    enabled_toolsets: List[Toolset]
    configured_toolsets: List[Toolset]
    _mocks: List[ToolMock]
    generate_mocks: bool
    test_case_folder: str

    def __init__(
        self, test_case_folder: str, generate_mocks: bool = True, run_live: bool = False
    ) -> None:
        self.generate_mocks = generate_mocks
        self.test_case_folder = test_case_folder
        self._mocks = []
        self.enabled_toolsets = []
        self.configured_toolsets = []
        self._enable_builtin_toolsets(run_live)
        self._update()

    def _load_toolsets_definitions(self, run_live) -> List[Toolset]:
        config_path = os.path.join(self.test_case_folder, "toolsets.yaml")
        toolsets_definitions = None
        if os.path.isfile(config_path):
            toolsets_definitions = load_toolsets_from_file(
                toolsets_path=config_path, strict_check=False
            )

        return toolsets_definitions or []

    def _enable_builtin_toolsets(self, run_live: bool):
        self.unmocked_toolsets = load_builtin_toolsets()

        toolset_definitions = self._load_toolsets_definitions(run_live)

        for toolset in self.unmocked_toolsets:
            toolset.enabled = True
            definition = next(
                (d for d in toolset_definitions if d.name == toolset.name), None
            )
            if definition:
                toolset.config = definition.config
                toolset.enabled = definition.enabled
                self.configured_toolsets.append(toolset)

            if toolset.enabled:
                try:
                    toolset.check_prerequisites()
                except Exception:
                    logging.error(
                        f"check_prerequisites failed for toolset {toolset.name}.",
                        exc_info=True,
                    )

    def mock_tool(self, tool_mock: ToolMock):
        self._mocks.append(tool_mock)
        self._update()

    def _find_mocks_for_tool(self, toolset_name: str, tool_name: str) -> List[ToolMock]:
        found_mocks = []
        for tool_mock in self._mocks:
            if (
                tool_mock.toolset_name == toolset_name
                and tool_mock.tool_name == tool_name
            ):
                found_mocks.append(tool_mock)
        return found_mocks

    def _wrap_tool_with_exception_if_required(
        self, tool: Tool, toolset_name: str
    ) -> Tool:
        if self.generate_mocks:
            return SaveMockTool(
                unmocked_tool=tool,
                toolset_name=toolset_name,
                test_case_folder=self.test_case_folder,
            )
        else:
            return tool

    def _update(self):
        mocked_toolsets = []
        for toolset in self.unmocked_toolsets:
            mocked_tools = []
            has_mocks = False
            for i in range(len(toolset.tools)):
                tool = toolset.tools[i]
                mocks = self._find_mocks_for_tool(
                    toolset_name=toolset.name, tool_name=tool.name
                )
                wrapped_tool = self._wrap_tool_with_exception_if_required(
                    tool=tool, toolset_name=toolset.name
                )

                if len(mocks) > 0:
                    has_mocks = True
                    mock_tool = MockToolWrapper(unmocked_tool=wrapped_tool)
                    mock_tool.mocks = mocks
                    mocked_tools.append(mock_tool)
                else:
                    mocked_tools.append(wrapped_tool)

            if has_mocks or toolset.status == ToolsetStatusEnum.ENABLED:
                mocked_toolset = MockToolset(
                    name=toolset.name,
                    prerequisites=toolset.prerequisites,
                    tools=toolset.tools,
                    description=toolset.description,
                    llm_instructions=toolset.llm_instructions,
                )
                mocked_toolset.tools = mocked_tools
                mocked_toolset.status = ToolsetStatusEnum.ENABLED
                mocked_toolsets.append(mocked_toolset)

        enabled_toolsets = mocked_toolsets
        for toolset in self.configured_toolsets:
            mocked = None
            try:
                mocked = next(
                    toolset
                    for mocked_toolset in enabled_toolsets
                    if mocked_toolset.name == toolset.name
                )
            except StopIteration:
                pass
            if not mocked:
                enabled_toolsets.append(toolset)
        self.enabled_toolsets = enabled_toolsets
