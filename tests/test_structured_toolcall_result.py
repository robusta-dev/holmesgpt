import json
import pytest
from pydantic import BaseModel

from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.core.models import ToolCallResult, format_tool_result_data


class DummyResult(BaseModel):
    x: int
    y: str


class Unserializable:
    def __str__(self):
        return "unserializable_str"


@pytest.mark.parametrize(
    "data,expected",
    [
        (None, ""),
        ("simple string", "simple string"),
    ],
)
def test_get_stringified_data_none_and_str(data, expected):
    result = StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data=data)
    assert result.get_stringified_data() == expected


def test_get_stringified_data_base_model():
    dummy = DummyResult(x=10, y="hello")
    result = StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data=dummy)
    expected = dummy.model_dump_json(indent=2)
    assert result.get_stringified_data() == expected


@pytest.mark.parametrize(
    "data",
    [
        {"key": "value", "num": 5},
        [1, 2, 3],
    ],
)
def test_get_stringified_data_json_serializable(data):
    result = StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data=data)
    expected = json.dumps(data, indent=2)
    assert result.get_stringified_data() == expected


def test_get_stringified_data_unserializable_object():
    obj = Unserializable()
    result = StructuredToolResult(status=StructuredToolResultStatus.ERROR, data=obj)
    assert result.get_stringified_data() == "unserializable_str"


@pytest.mark.parametrize(
    "status,error,return_code,url,invocation,params",
    [
        (StructuredToolResultStatus.SUCCESS, None, None, None, None, None),
        (
            StructuredToolResultStatus.ERROR,
            "oops",
            1,
            "http://example.com",
            "invoke",
            {"a": 1},
        ),
    ],
)
def test_default_and_custom_fields(status, error, return_code, url, invocation, params):
    result = StructuredToolResult(
        status=status,
        error=error,
        return_code=return_code,
        data=None,
        url=url,
        invocation=invocation,
        params=params,
    )
    assert result.schema_version == "robusta:v1.0.0"
    assert result.status == status
    assert result.error == error
    assert result.return_code == return_code
    assert result.data is None
    assert result.url == url
    assert result.invocation == invocation
    assert result.params == params


@pytest.mark.parametrize(
    "status,error,data,expected",
    [
        (StructuredToolResultStatus.SUCCESS, None, "test", "test"),
        (
            StructuredToolResultStatus.NO_DATA,
            None,
            DummyResult(x=2, y="test"),
            DummyResult(x=2, y="test").model_dump_json(indent=2),
        ),
        (
            StructuredToolResultStatus.SUCCESS,
            None,
            {"k": 1},
            json.dumps({"k": 1}, indent=2),
        ),
        (
            StructuredToolResultStatus.SUCCESS,
            None,
            Unserializable(),
            str(Unserializable()),
        ),
    ],
)
def test_format_tool_result_data_non_error(status, error, data, expected):
    tool_result = StructuredToolResult(status=status, error=error, data=data)
    assert format_tool_result_data(tool_result) == expected


def test_format_tool_result_data_str_non_error():
    result = StructuredToolResult(
        status=StructuredToolResultStatus.SUCCESS, data="hello"
    )
    assert format_tool_result_data(result) == "hello"


def test_format_tool_result_data_base_model_non_error():
    dummy = DummyResult(x=2, y="b")
    result = StructuredToolResult(status=StructuredToolResultStatus.NO_DATA, data=dummy)
    assert format_tool_result_data(result) == dummy.model_dump_json(indent=2)


def test_format_tool_result_data_json_serializable_non_error():
    data = {"k": 3}
    result = StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data=data)
    assert format_tool_result_data(result) == json.dumps(data, indent=2)


def test_format_tool_result_data_unserializable_non_error():
    obj = Unserializable()
    result = StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data=obj)
    assert format_tool_result_data(result) == str(obj)


def test_format_tool_result_data_error_with_message_and_data():
    result = StructuredToolResult(
        status=StructuredToolResultStatus.ERROR, error="fail", data="oops"
    )
    assert format_tool_result_data(result) == "fail:\n\noops"


def test_format_tool_result_data_error_without_message_or_data():
    result = StructuredToolResult(
        status=StructuredToolResultStatus.ERROR, error=None, data=None
    )
    assert format_tool_result_data(result) == "Tool execution failed:"


def test_format_tool_result_data_error_without_message_with_unserializable():
    obj = Unserializable()
    result = StructuredToolResult(
        status=StructuredToolResultStatus.ERROR, error=None, data=obj
    )
    expected = f"Tool execution failed:\n\n{str(obj)}"
    assert format_tool_result_data(result) == expected


def test_as_tool_call_message_without_params():
    structured = StructuredToolResult(
        status=StructuredToolResultStatus.SUCCESS, data="hello"
    )
    tcr = ToolCallResult(
        tool_call_id="call1",
        tool_name="toolX",
        description="desc",
        result=structured,
    )
    message = tcr.as_tool_call_message()
    assert message == {
        "tool_call_id": "call1",
        "role": "tool",
        "name": "toolX",
        "content": "hello",
    }


def test_as_tool_call_message_with_params():
    structured = StructuredToolResult(
        status=StructuredToolResultStatus.SUCCESS,
        data="hello",
        params={"pod_name": "my-pod", "namespace": "my-namespace"},
    )
    tcr = ToolCallResult(
        tool_call_id="call1",
        tool_name="toolX",
        description="desc",
        result=structured,
    )
    message = tcr.as_tool_call_message()
    assert message == {
        "tool_call_id": "call1",
        "role": "tool",
        "name": "toolX",
        "content": (
            'Params used for the tool call: {"pod_name": "my-pod", "namespace": "my-namespace"}. The tool call output follows on the next line.\n'
            "hello"
        ),
    }


def test_as_tool_result_response():
    structured = StructuredToolResult(
        status=StructuredToolResultStatus.SUCCESS, data="hello"
    )
    tcr = ToolCallResult(
        tool_call_id="call1",
        tool_name="toolX",
        description="desc",
        result=structured,
    )
    response = tcr.as_tool_result_response()
    assert response["tool_call_id"] == "call1"
    assert response["tool_name"] == "toolX"
    assert response["description"] == "desc"
    assert response["role"] == "tool"

    expected_dump = structured.model_dump()
    expected_dump["data"] = structured.get_stringified_data()
    assert response["result"] == expected_dump


def test_as_streaming_tool_result_response():
    structured = StructuredToolResult(
        status=StructuredToolResultStatus.SUCCESS, data="hello"
    )
    tcr = ToolCallResult(
        tool_call_id="call2",
        tool_name="toolY",
        description="desc2",
        result=structured,
    )
    streaming = tcr.as_streaming_tool_result_response()
    assert streaming["tool_call_id"] == "call2"
    assert streaming["role"] == "tool"
    assert streaming["description"] == "desc2"
    assert streaming["name"] == "toolY"

    expected_dump = structured.model_dump()
    expected_dump["data"] = structured.get_stringified_data()
    assert streaming["result"] == expected_dump
