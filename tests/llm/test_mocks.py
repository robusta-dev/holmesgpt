from holmes.core.tools import ToolExecutor
from tests.llm.utils.mock_toolset import MockToolsets, ToolMock
import pytest
import tempfile

@pytest.mark.parametrize("params", [
    ({"field1": "1", "field2": "2"}),
    ({"field1": "1", "field2": "2", "field3": "3"})
])
def test_mock_tools_match(params):
    mock = MockToolsets(test_case_folder=tempfile.gettempdir(), generate_mocks=False)
    mock.mock_tool(ToolMock(
        source_file="test",
        toolset_name="kubernetes/core",
        tool_name="kubectl_describe",
        match_params={"field1": "1", "field2": "2"},
        return_value="this tool is mocked"
    ))
    tool_executor = ToolExecutor(mock.mocked_toolsets)
    result = tool_executor.invoke("kubectl_describe", params)

    assert result == "this tool is mocked"

@pytest.mark.parametrize("params", [
    ({}),
    ({"field1": "1"}),
    ({"field2": "2"}),
    ({"field1": "1", "field2": "XXX"}),
    ({"field1": "XXX", "field2": "2"}),
    ({"field3": "3"})
])
def test_mock_tools_do_not_match(params):
    mock = MockToolsets(test_case_folder=tempfile.gettempdir(), generate_mocks=True)
    mock.mock_tool(ToolMock(
        source_file="test",
        toolset_name="kubernetes/core",
        tool_name="kubectl_describe",
        match_params={"field1": "1", "field2": "2"},
        return_value="this tool is mocked"
    ))
    tool_executor = ToolExecutor(mock.mocked_toolsets)
    result = tool_executor.invoke("kubectl_describe", params)

    assert result != "this tool is mocked"

def test_mock_tools_does_not_throws_if_no_match():
    mock = MockToolsets(test_case_folder=tempfile.gettempdir(), generate_mocks=True)
    tool_executor = ToolExecutor(mock.mocked_toolsets)
    tool_executor.invoke("kubectl_describe", {"foo":"bar"})
