import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
from mcp.types import Tool as MCP_Tool
from pydantic import AnyUrl, Field, field_validator

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
)


class BaseMCPTool(Tool):
    """Base class for MCP tools with shared functionality"""

    headers: Optional[Dict[str, str]] = None

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            return asyncio.run(self._invoke_async(params))
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=str(e.args),
                params=params,
                invocation=f"{self.__class__.__name__} {self.name} with params {params}",
            )

    async def _invoke_async(self, params: Dict) -> StructuredToolResult:
        """Override this method in subclasses"""
        raise NotImplementedError

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


class RemoteMCPTool(BaseMCPTool):
    url: str

    async def _invoke_async(self, params: Dict) -> StructuredToolResult:
        async with sse_client(self.url, self.headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                tool_result: CallToolResult = await session.call_tool(self.name, params)

                merged_text = " ".join(
                    c.text for c in tool_result.content if c.type == "text"
                )
                return StructuredToolResult(
                    status=(
                        ToolResultStatus.ERROR
                        if tool_result.isError
                        else ToolResultStatus.SUCCESS
                    ),
                    data=merged_text,
                    params=params,
                    invocation=f"MCPtool {self.name} with params {params}",
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

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Call mcp server {self.url} tool {self.name} with params {str(params)}"


class StdioMCPTool(BaseMCPTool):
    server_params: StdioServerParameters

    async def _invoke_async(self, params: Dict) -> StructuredToolResult:
        async with stdio_client(self.server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                tool_result: CallToolResult = await session.call_tool(self.name, params)

                merged_text = " ".join(
                    c.text for c in tool_result.content if c.type == "text"
                )
                return StructuredToolResult(
                    status=(
                        ToolResultStatus.ERROR
                        if tool_result.isError
                        else ToolResultStatus.SUCCESS
                    ),
                    data=merged_text,
                    params=params,
                    invocation=f"Stdio MCP tool {self.name} with params {params}",
                )

    @classmethod
    def create(
        cls,
        server_params: StdioServerParameters,
        tool: MCP_Tool,
        headers: Optional[Dict[str, str]] = None,
    ):
        parameters = cls.parse_input_schema(tool.inputSchema)
        return cls(
            server_params=server_params,
            name=tool.name,
            description=tool.description or "",
            parameters=parameters,
            headers=headers,
        )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Call stdio mcp server tool {self.name} with params {str(params)}"


class BaseMCPToolset(Toolset):
    """Base class for MCP toolsets with shared functionality"""

    name: str
    description: str = "MCP toolset for managing and invoking tools from an MCP server."
    icon_url: str = "https://registry.npmmirror.com/@lobehub/icons-static-png/1.46.0/files/light/mcp.png"

    def model_post_init(self, __context: Any) -> None:
        self.prerequisites = [CallablePrerequisite(callable=self.init_server_tools)]

    def get_headers(self) -> Optional[Dict[str, str]]:
        return self.config and self.config.get("headers")

    def init_server_tools(self, config: dict[str, Any]) -> Tuple[bool, str]:
        try:
            tools_result = asyncio.run(self._get_server_tools())
            self.tools = self._create_tools(tools_result.tools)

            if not self.tools:
                logging.warning(
                    f"{self._get_server_type()} mcp server {self.name} loaded 0 tools."
                )
            return (True, "")
        except Exception as e:
            return (
                False,
                f"Failed to load {self._get_server_type()} mcp server {self.name} {self._get_connection_info()} {str(e.args)}",
            )

    def _create_tools(self, tools: List[MCP_Tool]) -> List[Tool]:
        """Override this method in subclasses to create appropriate tool instances"""
        raise NotImplementedError

    def _get_server_type(self) -> str:
        """Override this method in subclasses to return server type for logging"""
        raise NotImplementedError

    def _get_connection_info(self) -> str:
        """Override this method in subclasses to return connection info for logging"""
        raise NotImplementedError

    async def _get_server_tools(self):
        """Override this method in subclasses"""
        raise NotImplementedError


class RemoteMCPToolset(BaseMCPToolset):
    url: AnyUrl
    tools: List[RemoteMCPTool] = Field(default_factory=list)  # type: ignore

    @field_validator("url", mode="before")
    def append_sse_if_missing(cls, v):
        if isinstance(v, str) and not v.rstrip("/").endswith("/sse"):
            v = v.rstrip("/") + "/sse"
        return v

    def _create_tools(self, tools: List[MCP_Tool]) -> List[Tool]:
        return [
            RemoteMCPTool.create(str(self.url), tool, self.get_headers())
            for tool in tools
        ]

    def _get_server_type(self) -> str:
        return "remote"

    def _get_connection_info(self) -> str:
        return str(self.url)

    async def _get_server_tools(self):
        async with sse_client(str(self.url), headers=self.get_headers()) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                return await session.list_tools()

    def get_example_config(self) -> Dict[str, Any]:
        return {}


class StdioMCPToolset(BaseMCPToolset):
    command: str
    args: List[str] = Field(default_factory=list)
    tools: List[StdioMCPTool] = Field(default_factory=list)  # type: ignore

    def _create_tools(self, tools: List[MCP_Tool]) -> List[Tool]:
        server_params = StdioServerParameters(command=self.command, args=self.args)

        return [
            StdioMCPTool.create(server_params, tool, self.get_headers())
            for tool in tools
        ]

    def _get_server_type(self) -> str:
        return "stdio"

    def _get_connection_info(self) -> str:
        return f"{self.command} {' '.join(self.args)}"

    async def _get_server_tools(self):
        server_params = StdioServerParameters(command=self.command, args=self.args)
        async with stdio_client(server_params) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                return await session.list_tools()

    def get_example_config(self) -> Dict[str, Any]:
        return {"command": "python", "args": ["/path/to/mcp_server.py"]}


def get_mcp_toolset_from_config(config: dict[str, Any], name: str) -> BaseMCPToolset:
    if not config:
        raise ValueError("Config must not be empty")
    url = config.get("url")
    command = config.get("command")
    if url:
        return RemoteMCPToolset(**config, name=name)
    elif command:
        return StdioMCPToolset(**config, name=name)
    else:
        raise ValueError(
            "Neither 'url' required for SSE MCP server nor 'command' required for Stdio MCP Server is provided to create an MCP toolset."
        )
