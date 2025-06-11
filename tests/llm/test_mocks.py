# type: ignore
from holmes.core.tools import StructuredToolResult, ToolResultStatus
from holmes.core.tools_utils.tool_executor import ToolExecutor
from tests.llm.utils.mock_toolset import MockToolsets, ToolMock
import pytest
import tempfile
from unittest import mock as mocker


@pytest.mark.parametrize(
    "params",
    [({"field1": "1", "field2": "2"}), ({"field1": "1", "field2": "2", "field3": "3"})],
)
def test_mock_tools_match(params):
    with mocker.patch(
        "holmes.plugins.toolsets.service_discovery.find_service_url",
        return_value="http://mock-prometheus:9090",
    ):
        mock = MockToolsets(
            test_case_folder=tempfile.gettempdir(), generate_mocks=False
        )
        mock.mock_tool(
            ToolMock(
                source_file="test",
                toolset_name="kubernetes/core",
                tool_name="kubectl_describe",
                match_params={"field1": "1", "field2": "2"},
                return_value=StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="this tool is mocked",
                    params=params,
                ),
            )
        )
        tool_executor = ToolExecutor(mock.enabled_toolsets)
        result = tool_executor.invoke("kubectl_describe", params)

        assert result.data == "this tool is mocked"


@pytest.mark.parametrize(
    "params",
    [
        ({}),
        ({"field1": "1"}),
        ({"field2": "2"}),
        ({"field1": "1", "field2": "XXX"}),
        ({"field1": "XXX", "field2": "2"}),
        ({"field3": "3"}),
    ],
)
def test_mock_tools_do_not_match(params):
    with mocker.patch(
        "holmes.plugins.toolsets.service_discovery.find_service_url",
        return_value="http://mock-prometheus:9090",
    ):
        mock = MockToolsets(test_case_folder=tempfile.gettempdir(), generate_mocks=True)
        mock.mock_tool(
            ToolMock(
                source_file="test",
                toolset_name="kubernetes/core",
                tool_name="kubectl_describe",
                match_params={"field1": "1", "field2": "2"},
                return_value=StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="this tool is mocked",
                    params=params,
                ),
            )
        )
        tool_executor = ToolExecutor(mock.enabled_toolsets)
        result = tool_executor.invoke("kubectl_describe", params)

        assert result != "this tool is mocked"


def test_mock_tools_does_not_throws_if_no_match():
    with mocker.patch(
        "holmes.plugins.toolsets.service_discovery.find_service_url",
        return_value="http://mock-prometheus:9090",
    ):
        mock = MockToolsets(test_case_folder=tempfile.gettempdir(), generate_mocks=True)
        tool_executor = ToolExecutor(mock.enabled_toolsets)
        tool_executor.invoke("kubectl_describe", {"foo": "bar"})
