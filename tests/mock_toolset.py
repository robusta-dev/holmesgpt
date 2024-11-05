

from os import name
from typing import Dict, List, Optional
from holmes.core.tools import Tool, Toolset
from holmes.plugins.toolsets import load_builtin_toolsets
from pydantic import BaseModel


class MockMetadata(BaseModel):
    toolset_name:str
    tool_name: str
    match_params: Optional[Dict] = None # None will match all params

class ToolMock(MockMetadata):
    return_value: str

class RaiseExceptionTool(Tool):
    """
    Tool that raises an exception if invoked.
    It is used to fail tests if not all invoked tool calls are mocked. This ensures stable test conditions
    """
    toolset_name: str
    unmocked_tool: Tool
    def __init__(self, unmocked_tool:Tool, toolset_name:str = "Unknown"):
        super().__init__(
            name = unmocked_tool.name,
            description = unmocked_tool.description,
            parameters = unmocked_tool.parameters,
            user_description = unmocked_tool.user_description,
            toolset_name = toolset_name,
            unmocked_tool = unmocked_tool
        )

    def invoke(self, params) -> str:
        raise Exception(f"Tool was invoked but a mock is required. Update the test with a mock for that tool. toolset_name={self.toolset_name}, tool_name={self.name}, params={str(params)}")

    def get_parameterized_one_liner(self, params) -> str:
        return self.unmocked_tool.get_parameterized_one_liner(params)


class MockTool(Tool):
    unmocked_tool:Tool
    mocks: List[ToolMock] = []
    def __init__(self, unmocked_tool:Tool):
        super().__init__(
            name=unmocked_tool.name,
            description=unmocked_tool.description,
            parameters=unmocked_tool.parameters,
            user_description=unmocked_tool.user_description,
            unmocked_tool=unmocked_tool
        )

    def find_matching_mock(self, params:Dict) -> Optional[ToolMock]:
        for mock in self.mocks:
            if not mock.match_params: # wildcard
                return mock

            match = all(key in params and params[key] == val for key, val in mock.match_params.items())
            if match:
                return mock


    def invoke(self, params) -> str:
        mock = self.find_matching_mock(params)
        if mock:
            return mock.return_value
        else:
            return self.unmocked_tool.invoke(params)

    def get_parameterized_one_liner(self, params) -> str:
        return self.unmocked_tool.get_parameterized_one_liner(params)

class MockToolsets:
    unmocked_toolsets: List[Toolset]
    mocked_toolsets: List[Toolset] = []
    mocks: List[ToolMock] = []
    require_mock: bool = False

    def __init__(self, require_mock: bool = False) -> None:
        self.unmocked_toolsets = load_builtin_toolsets()
        self.require_mock = require_mock
        self._update()

    def mock_tool(self, tool_mock:ToolMock):
        self.mocks.append(tool_mock)
        self._update()

    def _find_mocks_for_tool(self, toolset_name:str, tool_name:str) -> List[ToolMock]:
        found_mocks = []
        for tool_mock in self.mocks:
            if tool_mock.toolset_name == toolset_name and tool_mock.tool_name == tool_name:
                found_mocks.append(tool_mock)
        return found_mocks

    def _wrap_tool_with_exception_if_required(self, tool:Tool, toolset_name:str) -> Tool:
        if self.require_mock:
            return RaiseExceptionTool(unmocked_tool=tool, toolset_name=toolset_name)
        else:
            return tool

    def _update(self):
        mocked_toolsets = []
        for toolset in self.unmocked_toolsets:
            mocked_tools = []
            for i in range(len(toolset.tools)):
                tool = toolset.tools[i]
                mocks = self._find_mocks_for_tool(toolset_name=toolset.name, tool_name=tool.name)
                wrapped_tool = self._wrap_tool_with_exception_if_required(tool=tool, toolset_name=toolset.name)

                if len(mocks) > 0:
                    mock_tool = MockTool(unmocked_tool=wrapped_tool)
                    mock_tool.mocks = mocks
                    mocked_tools.append(mock_tool)
                else:
                    mocked_tools.append(wrapped_tool)

            mocked_toolset = Toolset(
                name = toolset.name,
                prerequisites = toolset.prerequisites,
                tools = toolset.tools
            )
            mocked_toolset.tools = mocked_tools
            mocked_toolsets.append(mocked_toolset)

        self.mocked_toolsets = mocked_toolsets
