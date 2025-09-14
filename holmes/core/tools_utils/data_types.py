import json
from typing import Optional
from pydantic import BaseModel

from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus


class TruncationMetadata(BaseModel):
    tool_call_id: str
    start_index: int
    end_index: int
    tool_name: str
    original_token_count: int


class TruncationResult(BaseModel):
    truncated_messages: list[dict]
    truncations: list[TruncationMetadata]


def format_tool_result_data(tool_result: StructuredToolResult) -> str:
    tool_response = tool_result.data
    if isinstance(tool_result.data, str):
        tool_response = tool_result.data
    else:
        try:
            if isinstance(tool_result.data, BaseModel):
                tool_response = tool_result.data.model_dump_json(indent=2)
            else:
                tool_response = json.dumps(tool_result.data, indent=2)
        except Exception:
            tool_response = str(tool_result.data)
    if tool_result.status == StructuredToolResultStatus.ERROR:
        tool_response = f"{tool_result.error or 'Tool execution failed'}:\n\n{tool_result.data or ''}".strip()
    return tool_response


class ToolCallResult(BaseModel):
    tool_call_id: str
    tool_name: str
    description: str
    result: StructuredToolResult
    size: Optional[int] = None

    def as_tool_call_message(self):
        content = format_tool_result_data(self.result)
        if self.result.params:
            content = (
                f"Params used for the tool call: {json.dumps(self.result.params)}. The tool call output follows on the next line.\n"
                + content
            )
        return {
            "tool_call_id": self.tool_call_id,
            "role": "tool",
            "name": self.tool_name,
            "content": content,
        }

    def as_tool_result_response(self):
        result_dump = self.result.model_dump()
        result_dump["data"] = self.result.get_stringified_data()

        return {
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "description": self.description,
            "role": "tool",
            "result": result_dump,
        }

    def as_streaming_tool_result_response(self):
        result_dump = self.result.model_dump()
        result_dump["data"] = self.result.get_stringified_data()

        return {
            "tool_call_id": self.tool_call_id,
            "role": "tool",
            "description": self.description,
            "name": self.tool_name,
            "result": result_dump,
        }
