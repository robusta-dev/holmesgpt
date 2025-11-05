from holmes.core.tools import (
    ToolInvokeContext,
    Toolset,
    Tool,
    ToolParameter,
    StructuredToolResult,
    StructuredToolResultStatus,
    CallablePrerequisite,
)

from typing import Dict, Any, List, Optional
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from mcp.types import Tool as MCP_Tool

import asyncio
from pydantic import Field, AnyUrl, model_validator
from typing import Tuple
import logging
from enum import Enum


class MCPMode(str, Enum):
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


def get_mode_from_dict(data: dict[str, Any] | None) -> MCPMode:
    if data is None:
        return MCPMode.SSE
    mode_value = data.get("mode") or (data.get("config") or {}).get("mode") or "sse"
    try:
        return MCPMode(mode_value)
    except ValueError:
        logging.error(f'Mode "{mode_value}" is not supported, falling back to SSE')
        return MCPMode.SSE


def get_mode_from_config(config: dict[str, Any] | None) -> MCPMode:
    if config is None:
        return MCPMode.SSE
    mode_value = config.get("mode") or "sse"
    try:
        return MCPMode(mode_value)
    except ValueError:
        logging.error(f'Mode "{mode_value}" is not supported, falling back to SSE')
        return MCPMode.SSE


class RemoteMCPTool(Tool):
    url: str
    headers: Optional[Dict[str, str]] = None
    mode: MCPMode = MCPMode.SSE

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        try:
            return asyncio.run(self._invoke_async(params))
        except Exception as e:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=str(e.args),
                params=params,
                invocation=f"MCPtool {self.name} with params {params}",
            )

    async def _call_tool_with_session(self, read_stream, write_stream, params):
        async with ClientSession(read_stream, write_stream) as session:
            _ = await session.initialize()
            return await session.call_tool(self.name, params)

    async def _invoke_async(self, params: Dict) -> StructuredToolResult:
        tool_result = None
        if self.mode == MCPMode.SSE:
            async with sse_client(self.url, self.headers) as (
                read_stream,
                write_stream,
            ):
                tool_result = await self._call_tool_with_session(
                    read_stream, write_stream, params
                )
        else:
            async with streamablehttp_client(self.url, headers=self.headers) as (
                read_stream,
                write_stream,
                _,
            ):
                tool_result = await self._call_tool_with_session(
                    read_stream, write_stream, params
                )

        merged_text = " ".join(c.text for c in tool_result.content if c.type == "text")
        return StructuredToolResult(
            status=(
                StructuredToolResultStatus.ERROR
                if tool_result.isError
                else StructuredToolResultStatus.SUCCESS
            ),
            data=merged_text,
            params=params,
            invocation=f"MCPtool {self.name} with params {params}",
        )

    @classmethod
    def create(
        cls,
        url: str,
        tool: MCP_Tool,
        headers: Optional[Dict[str, str]] = None,
        mode: MCPMode = MCPMode.SSE,
    ):
        parameters = cls.parse_input_schema(tool.inputSchema)
        return cls(
            url=url,
            name=tool.name,
            description=tool.description or "",
            parameters=parameters,
            headers=headers,
            mode=mode,
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
        return f"Call MCP Server ({self.url} - {self.name})"


class RemoteMCPToolset(Toolset):
    url: AnyUrl
    tools: List[RemoteMCPTool] = Field(default_factory=list)  # type: ignore
    icon_url: str = "https://registry.npmmirror.com/@lobehub/icons-static-png/1.46.0/files/light/mcp.png"
    mode: MCPMode = MCPMode.SSE

    def model_post_init(self, __context: Any) -> None:
        self.prerequisites = [CallablePrerequisite(callable=self.init_server_tools)]

    def get_headers(self) -> Optional[Dict[str, str]]:
        return self.config and self.config.get("headers")

    @model_validator(mode="before")
    @classmethod
    def append_suffix_if_missing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mode = get_mode_from_dict(data)
            data["mode"] = mode

            url = data.get("url")
            if (
                isinstance(url, str)
                and mode == MCPMode.SSE
                and not url.rstrip("/").endswith("/sse")
            ):
                data["url"] = url.rstrip("/") + "/sse"
        return data

    # used as a CallablePrerequisite, config added for that case.
    def init_server_tools(self, config: dict[str, Any]) -> Tuple[bool, str]:
        try:
            self.mode = get_mode_from_config(config)

            tools_result = asyncio.run(self._get_server_tools())

            self.tools = [
                RemoteMCPTool.create(str(self.url), tool, self.get_headers(), self.mode)
                for tool in tools_result.tools
            ]

            if not self.tools:
                logging.warning(f"mcp server {self.name} loaded 0 tools.")

            return (True, "")
        except Exception as e:
            # using e.args, the asyncio wrapper could stack another exception this helps printing them all.
            return (
                False,
                f"Failed to load mcp server {self.name} {self.url} {str(e.args)}",
            )

    async def _list_tools_with_session(self, read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            _ = await session.initialize()
            return await session.list_tools()

    async def _get_server_tools(self):
        if self.mode == MCPMode.SSE:
            async with sse_client(str(self.url), headers=self.get_headers()) as (
                read_stream,
                write_stream,
            ):
                return await self._list_tools_with_session(read_stream, write_stream)
        else:
            async with streamablehttp_client(
                str(self.url), headers=self.get_headers()
            ) as (read_stream, write_stream, _):
                return await self._list_tools_with_session(read_stream, write_stream)

    def get_example_config(self) -> Dict[str, Any]:
        return {}
