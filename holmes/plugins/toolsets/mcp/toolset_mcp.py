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

from mcp.types import Tool as MCP_Tool
from mcp.types import CallToolResult

import asyncio
from pydantic import Field, AnyUrl, field_validator, PrivateAttr
from typing import Tuple
import logging
import httpx


class RemoteMCPTool(Tool):
    url: str
    headers: Optional[Dict[str, str]] = None
    _parent_toolset: Optional["RemoteMCPToolset"] = PrivateAttr(default=None)

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

    async def _invoke_async(self, params: Dict) -> StructuredToolResult:
        # Get auth from parent toolset if available
        auth = None
        if self._parent_toolset:
            auth = getattr(self._parent_toolset, "_auth", None)

        async with sse_client(self.url, self.headers, auth=auth) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                tool_result: CallToolResult = await session.call_tool(self.name, params)

                merged_text = " ".join(
                    c.text for c in tool_result.content if c.type == "text"
                )
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
        parent_toolset: Optional["RemoteMCPToolset"] = None,
    ):
        parameters = cls.parse_input_schema(tool.inputSchema)
        instance = cls(
            url=url,
            name=tool.name,
            description=tool.description or "",
            parameters=parameters,
            headers=headers,
        )
        instance._parent_toolset = parent_toolset
        return instance

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
    _auth: Optional[httpx.Auth] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        self.prerequisites = [CallablePrerequisite(callable=self.init_server_tools)]

    def get_headers(self) -> Optional[Dict[str, str]]:
        return self.config and self.config.get("headers")

    @field_validator("url", mode="before")
    def append_sse_if_missing(cls, v):
        if isinstance(v, str) and not v.rstrip("/").endswith("/sse"):
            v = v.rstrip("/") + "/sse"
        return v

    # used as a CallablePrerequisite, config added for that case.
    def init_server_tools(self, config: dict[str, Any]) -> Tuple[bool, str]:
        try:
            # Handle OAuth authentication if configured
            auth = None
            if self.config and self.config.get("auth_type") == "oauth":
                from .oauth_auth import MCPOAuthAuth

                auth = MCPOAuthAuth(str(self.url))

                # Check if authentication is needed
                if not auth.has_valid_token():
                    print(f"\nAuthentication required for MCP server: {self.name}")
                    print("A browser window will open for authentication...")
                    try:
                        auth.authenticate()
                    except Exception as auth_error:
                        return (
                            False,
                            f"OAuth authentication failed for {self.name}: {str(auth_error)}",
                        )

                self._auth = auth
            elif self.config and self.config.get("auth_type") == "bearer":
                # Support for direct Bearer token authentication
                token = self.config.get("token")
                if not token:
                    import os

                    # Try environment variable as fallback
                    env_var = self.config.get(
                        "token_env_var", f"MCP_{self.name.upper()}_TOKEN"
                    )
                    token = os.getenv(env_var)

                if token:
                    # Create a simple auth class for bearer token
                    class BearerAuth(httpx.Auth):
                        def __init__(self, token):
                            self.token = token

                        def auth_flow(self, request):
                            request.headers["Authorization"] = f"Bearer {self.token}"
                            yield request

                    self._auth = BearerAuth(token)
                else:
                    return (
                        False,
                        f"Bearer token authentication configured but no token provided for {self.name}",
                    )

            tools_result = asyncio.run(self._get_server_tools())
            self.tools = [
                RemoteMCPTool.create(
                    str(self.url), tool, self.get_headers(), parent_toolset=self
                )
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

    async def _get_server_tools(self):
        async with sse_client(
            str(self.url), headers=self.get_headers(), auth=getattr(self, "_auth", None)
        ) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                _ = await session.initialize()
                return await session.list_tools()

    def get_example_config(self) -> Dict[str, Any]:
        return {}
