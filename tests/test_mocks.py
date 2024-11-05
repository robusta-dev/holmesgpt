


from holmes.core.tools import ToolExecutor
from tests.mock_toolset import MockToolsets
import pytest

@pytest.mark.parametrize("params", [
    ({"field1": "1", "field2": "2"}),
    ({"field1": "1", "field2": "2", "field3": "3"})
])
def test_mock_tools_match(params):
    mock = MockToolsets(require_mock=True)
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_describe",
        match_params={"field1": "1", "field2": "2"},
        return_value="this tool is mocked"
    )
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
    mock = MockToolsets(require_mock=False)
    mock.mock_tool(
        toolset_name="kubernetes/core",
        tool_name="kubectl_describe",
        match_params={"field1": "1", "field2": "2"},
        return_value="this tool is mocked"
    )
    tool_executor = ToolExecutor(mock.mocked_toolsets)
    result = tool_executor.invoke("kubectl_describe", params)

    assert result != "this tool is mocked"

def test_mock_tools_does_not_throws_if_no_match():
    mock = MockToolsets(require_mock=False)
    tool_executor = ToolExecutor(mock.mocked_toolsets)
    tool_executor.invoke("kubectl_describe", {"foo":"bar"})

def test_mock_tools_throws_if_no_match():
    mock = MockToolsets(require_mock=True)
    tool_executor = ToolExecutor(mock.mocked_toolsets)
    with pytest.raises(Exception) as exception:
        tool_executor.invoke("kubectl_describe", {"foo":"bar"})

    assert str(exception.value) == "Tool was invoked but a mock is required. Update the test with a mock for that tool. toolset_name=kubernetes/core, tool_name=kubectl_describe, params={'foo': 'bar'}"
