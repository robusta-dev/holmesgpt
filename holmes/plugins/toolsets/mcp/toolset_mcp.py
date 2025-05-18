from holmes.core.tools import (
    Toolset,
    Tool,
    ToolParameter,
    StructuredToolResult,
    ToolResultStatus,
    CallablePrerequisite,
)

from typing import Dict, Any, List, Optional
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from mcp.types import Tool as MCP_Tool

import asyncio
from pydantic import field_validator, model_validator, Field
from typing import Tuple


class MCPTool(Tool):
    url: str
    headers: Optional[Dict[str, str]] = None

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            return asyncio.run(self._invoke_async(params))
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=str(e),
                params=params,
                invocation=f"MCPtool {self.name} with params {params}",
            )

    async def _invoke_async(self, params: Dict) -> StructuredToolResult:
        async with sse_client(self.url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                tool_result = await session.call_tool(self.name, params)

                merged_text = " ".join(
                    c.text for c in tool_result.content if c.type == "text"
                )
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=merged_text,
                    params=params,
                    invocation="",
                )

    @classmethod
    def create(cls, url: str, tool: MCP_Tool, headers: Optional[Dict[str, str]] = None):
        parameters = cls.parse_input_schema(tool.inputSchema)
        return cls(
            url=url,
            name=tool.name,
            description=tool.description or "",
            parameters=parameters,
            headers=headers,
        )

    @classmethod
    def parse_input_schema(
        cls, input_schema: dict[str, Any]
    ) -> Dict[str, ToolParameter]:
        required_list = input_schema.get("required", [])
        schema_params = input_schema.get("properties", {})
        parameters = {}
        for key, val in schema_params.items():
            parameters[key] = ToolParameter(
                description=val.get("description"),
                type=val.get("type", "string"),
                required=key in required_list,
            )

        return parameters

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Call mcp server {self.url} tool {self.name} with params {str(params)}"


class MCPToolset(Toolset):
    url: str
    headers: Optional[Dict[str, str]] = None
    tools: List[MCPTool] = Field(default_factory=list)
    icon_url: str = "https://registry.npmmirror.com/@lobehub/icons-static-png/1.46.0/files/light/mcp.png"

    @field_validator("url")
    def sse_endpoint(cls, v):
        if not v.endswith("/sse"):
            v = v.rstrip("/") + "/sse"

        return v

    @model_validator(mode="after")
    def set_tools_prerequisites(self):
        self.prerequisites = [CallablePrerequisite(callable=self.init_server_tools)]
        return self

    # used as a CallablePrerequisite, config added for that case.
    def init_server_tools(self, config: dict[str, Any]) -> Tuple[bool, str]:
        try:
            tools_result = asyncio.run(self._get_server_tools())
            self.tools = [
                MCPTool.create(self.url, tool, self.headers)
                for tool in tools_result.tools
            ]
            return (True, "")
        except Exception as e:
            # using e.args, the asyncio wrapper could stack another exception this helps printing them all.
            return (
                False,
                f"Failed to load mcp server {self.name} {self.url} tools: {str(e.args)}",
            )

    async def _get_server_tools(self):
        async with sse_client(self.url, headers=self.headers) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                return await session.list_tools()

    def get_example_config(self) -> Dict[str, Any]:
        return {}
