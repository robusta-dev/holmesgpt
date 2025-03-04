from typing import Dict, List, Optional
from holmes.core.tools import Tool, Toolset, ToolsetStatusEnum
from holmes.plugins.toolsets import load_builtin_toolsets
from pydantic import BaseModel
import logging
import re

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
    return_value: str


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
        output = strip_ansi(output)
        with open(mock_file_path, "w") as f:
            f.write(mock_metadata_json + "\n")
            f.write(output)

        return output

    def _invoke(self, params) -> str:
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

    def _invoke(self, params) -> str:
        mock = self.find_matching_mock(params)
        if mock:
            return mock.return_value
        else:
            return self.unmocked_tool.invoke(params)

    def get_parameterized_one_liner(self, params) -> str:
        return self.unmocked_tool.get_parameterized_one_liner(params)


class MockToolsets:
    unmocked_toolsets: List[Toolset]
    mocked_toolsets: List[Toolset]
    _mocks: List[ToolMock]
    generate_mocks: bool
    test_case_folder: str

    def __init__(self, test_case_folder: str, generate_mocks: bool = True) -> None:
        self.unmocked_toolsets = load_builtin_toolsets()

        for toolset in self.unmocked_toolsets:
            toolset.enabled = True
            toolset.check_prerequisites()

        self.generate_mocks = generate_mocks
        self.test_case_folder = test_case_folder
        self._mocks = []
        self.mocked_toolsets = []
        self._update()

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

            if has_mocks or toolset.get_status() == ToolsetStatusEnum.ENABLED:
                mocked_toolset = Toolset(
                    name=toolset.name,
                    prerequisites=toolset.prerequisites,
                    tools=toolset.tools,
                    description=toolset.description,
                )
                mocked_toolset.tools = mocked_tools
                mocked_toolset._status = ToolsetStatusEnum.ENABLED
                mocked_toolsets.append(mocked_toolset)
        self.mocked_toolsets = mocked_toolsets
