import asyncio
from unittest.mock import AsyncMock, patch

from holmes.core.tools import (
    ToolParameter,
    StructuredToolResultStatus,
)
from holmes.plugins.toolsets.mcp.toolset_mcp import (
    RemoteMCPToolset,
    RemoteMCPTool,
    MCPMode,
    get_initialized_mcp_session,
)
from mcp.types import ListToolsResult, Tool, CallToolResult, TextContent


def test_parse_mcp_tool():
    mcp_tool = Tool(
        name="b",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "qty": {"type": "integer", "description": "example for description"},
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                },
                "limit_price": {"type": "number"},
            },
            "required": ["symbol", "qty", "side"],
        },
        description="desc",
        annotations=None,
    )

    expected_schema = {
        "symbol": ToolParameter(type="string", required=True),
        "qty": ToolParameter(
            type="integer", required=True, description="example for description"
        ),
        "side": ToolParameter(type="string", required=True),
        "limit_price": ToolParameter(type="number", required=False),
    }

    tool = RemoteMCPTool.create("url", mcp_tool)
    assert tool.parameters == expected_schema
    assert tool.description == "desc"


def test_mcpserver_unreachable():
    mcp_toolset = RemoteMCPToolset(
        url="http://0.0.0.0:3009",
        name="test_mcp",
        description="",
    )

    result = mcp_toolset.init_server_tools(config=None)
    assert result[0] is False
    assert "Failed to load mcp server test_mcp http://0.0.0.0:3009/sse" in result[1]


def test_mcpserver_1tool(monkeypatch):
    mcp_toolset = RemoteMCPToolset(
        url="http://0.0.0.0/3005",
        name="test_mcp",
        description="demo mcp with 2 simple functions",
    )

    async def mock_get_server_tools():
        return ListToolsResult(
            tools=[
                Tool(
                    name="b",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                        },
                        "required": [],
                    },
                ),
            ]
        )

    monkeypatch.setattr(mcp_toolset, "_get_server_tools", mock_get_server_tools)
    mcp_toolset.init_server_tools(config=None)
    assert len(list(mcp_toolset.tools)) == 1


def test_mcpserver_headers(monkeypatch):
    mcp_toolset = RemoteMCPToolset(
        url="http://0.0.0.0/3005",
        name="test_mcp",
        description="demo mcp with 2 simple functions",
        config={"headers": {"header1": "test1", "header2": "test2"}},
    )

    assert mcp_toolset.get_headers().get("header1") == "test1"


def test_mcpserver_no_headers():
    mcp_toolset1 = RemoteMCPToolset(
        url="http://0.0.0.0/3005",
        name="test_mcp",
        description="demo mcp with 2 simple functions",
    )

    assert mcp_toolset1.get_headers() is None


def test_streamable_http_list_authorizations():
    streamable_http_response = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": '{\n  "ok": true,\n  "authorizations": [\n    {\n      "authorization_id": "auth_default_001",\n      "status": "authorized",\n      "amount": 150.0,\n      "currency": "USD",\n      "merchant_id": "merchant_001",\n      "card_last4": "4242"\n    }\n  ],\n  "count": 1,\n  "authorization_ids": ["auth_default_001"]\n}',
                }
            ]
        },
    }

    tool = Tool(
        name="list_authorizations",
        inputSchema={"type": "object", "properties": {}, "required": []},
        description="List all available authorization IDs",
    )

    mcp_tool = RemoteMCPTool.create(
        "http://localhost:1234/mcp/messages", tool, mode=MCPMode.STREAMABLE_HTTP
    )

    mock_read_stream = AsyncMock()
    mock_write_stream = AsyncMock()
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock(return_value=None)

    call_tool_result = CallToolResult(
        content=[
            TextContent(
                type="text",
                text=streamable_http_response["result"]["content"][0]["text"],
            )
        ],
        isError=False,
    )
    mock_session.call_tool = AsyncMock(return_value=call_tool_result)

    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(
        return_value=(mock_read_stream, mock_write_stream, None)
    )
    mock_client_context.__aexit__ = AsyncMock(return_value=None)

    mock_session_context = AsyncMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "holmes.plugins.toolsets.mcp.toolset_mcp.streamablehttp_client",
        return_value=mock_client_context,
    ):
        with patch(
            "holmes.plugins.toolsets.mcp.toolset_mcp.ClientSession",
            return_value=mock_session_context,
        ):
            result = asyncio.run(mcp_tool._invoke_async({}))

    assert result.status == StructuredToolResultStatus.SUCCESS
    assert streamable_http_response["result"]["content"][0]["text"] in result.data


def test_sse_list_authorizations():
    sse_response_text = '{\n  "ok": true,\n  "authorizations": [\n    {\n      "authorization_id": "auth_default_001",\n      "status": "authorized",\n      "amount": 150.0,\n      "currency": "USD",\n      "merchant_id": "merchant_001",\n      "card_last4": "4242"\n    }\n  ],\n  "count": 1,\n  "authorization_ids": ["auth_default_001"]\n}'

    tool = Tool(
        name="list_authorizations",
        inputSchema={"type": "object", "properties": {}, "required": []},
        description="List all available authorization IDs",
    )

    mcp_tool = RemoteMCPTool.create("http://localhost:1234/sse", tool, mode=MCPMode.SSE)

    mock_read_stream = AsyncMock()
    mock_write_stream = AsyncMock()
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock(return_value=None)

    call_tool_result = CallToolResult(
        content=[TextContent(type="text", text=sse_response_text)], isError=False
    )
    mock_session.call_tool = AsyncMock(return_value=call_tool_result)

    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(
        return_value=(mock_read_stream, mock_write_stream)
    )
    mock_client_context.__aexit__ = AsyncMock(return_value=None)

    mock_session_context = AsyncMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "holmes.plugins.toolsets.mcp.toolset_mcp.sse_client",
        return_value=mock_client_context,
    ):
        with patch(
            "holmes.plugins.toolsets.mcp.toolset_mcp.ClientSession",
            return_value=mock_session_context,
        ):
            result = asyncio.run(mcp_tool._invoke_async({}))

    assert result.status == StructuredToolResultStatus.SUCCESS
    assert sse_response_text in result.data


def test_streamable_http_authorize_payment():
    streamable_http_response = {
        "jsonrpc": "2.0",
        "id": "2",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": '{\n  "ok": true,\n  "authorization_id": "auth_test_123",\n  "status": "authorized"\n}',
                }
            ]
        },
    }

    tool = Tool(
        name="authorize_payment",
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "card_last4": {"type": "string"},
                "merchant_id": {"type": "string"},
            },
            "required": ["amount", "currency", "card_last4", "merchant_id"],
        },
        description="Reserve funds",
    )

    mcp_tool = RemoteMCPTool.create(
        "http://localhost:1234/mcp/messages", tool, mode=MCPMode.STREAMABLE_HTTP
    )

    mock_read_stream = AsyncMock()
    mock_write_stream = AsyncMock()
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock(return_value=None)

    call_tool_result = CallToolResult(
        content=[
            TextContent(
                type="text",
                text=streamable_http_response["result"]["content"][0]["text"],
            )
        ],
        isError=False,
    )
    mock_session.call_tool = AsyncMock(return_value=call_tool_result)

    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(
        return_value=(mock_read_stream, mock_write_stream, None)
    )
    mock_client_context.__aexit__ = AsyncMock(return_value=None)

    mock_session_context = AsyncMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=None)

    params = {
        "amount": 100.0,
        "currency": "USD",
        "card_last4": "1234",
        "merchant_id": "test-merchant",
    }

    with patch(
        "holmes.plugins.toolsets.mcp.toolset_mcp.streamablehttp_client",
        return_value=mock_client_context,
    ):
        with patch(
            "holmes.plugins.toolsets.mcp.toolset_mcp.ClientSession",
            return_value=mock_session_context,
        ):
            result = asyncio.run(mcp_tool._invoke_async(params))

    assert result.status == StructuredToolResultStatus.SUCCESS
    assert streamable_http_response["result"]["content"][0]["text"] in result.data
    assert "auth_test_123" in result.data
    assert "authorized" in result.data


def test_sse_authorize_payment():
    sse_response_text = '{\n  "ok": true,\n  "authorization_id": "auth_test_456",\n  "status": "authorized"\n}'

    tool = Tool(
        name="authorize_payment",
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "card_last4": {"type": "string"},
                "merchant_id": {"type": "string"},
            },
            "required": ["amount", "currency", "card_last4", "merchant_id"],
        },
        description="Reserve funds",
    )

    mcp_tool = RemoteMCPTool.create("http://localhost:1234/sse", tool, mode=MCPMode.SSE)

    mock_read_stream = AsyncMock()
    mock_write_stream = AsyncMock()
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock(return_value=None)

    call_tool_result = CallToolResult(
        content=[TextContent(type="text", text=sse_response_text)], isError=False
    )
    mock_session.call_tool = AsyncMock(return_value=call_tool_result)

    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(
        return_value=(mock_read_stream, mock_write_stream)
    )
    mock_client_context.__aexit__ = AsyncMock(return_value=None)

    mock_session_context = AsyncMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=None)

    params = {
        "amount": 100.0,
        "currency": "USD",
        "card_last4": "1234",
        "merchant_id": "test-merchant",
    }

    with patch(
        "holmes.plugins.toolsets.mcp.toolset_mcp.sse_client",
        return_value=mock_client_context,
    ):
        with patch(
            "holmes.plugins.toolsets.mcp.toolset_mcp.ClientSession",
            return_value=mock_session_context,
        ):
            result = asyncio.run(mcp_tool._invoke_async(params))

    assert result.status == StructuredToolResultStatus.SUCCESS
    assert sse_response_text in result.data
    assert "auth_test_456" in result.data
    assert "authorized" in result.data


class TestContextManagerCleanup:
    def _create_mock_session(self, call_tool_result=None, call_tool_side_effect=None):
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock(return_value=None)
        if call_tool_side_effect:
            mock_session.call_tool = AsyncMock(side_effect=call_tool_side_effect)
        elif call_tool_result:
            mock_session.call_tool = AsyncMock(return_value=call_tool_result)
        return mock_session

    def _create_mock_client_context(self, return_value):
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=return_value)
        mock_exit = AsyncMock(return_value=None)
        mock_context.__aexit__ = mock_exit
        return mock_context, mock_exit

    def _create_mock_session_context(self, session):
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=session)
        mock_exit = AsyncMock(return_value=None)
        mock_context.__aexit__ = mock_exit
        return mock_context, mock_exit

    def _verify_exit_called_with_no_exception(self, client_exit, session_exit):
        client_exit.assert_called_once()
        session_exit.assert_called_once()

        client_args = client_exit.call_args[0]
        session_args = session_exit.call_args[0]

        assert client_args[0] is None
        assert client_args[1] is None
        assert client_args[2] is None

        assert session_args[0] is None
        assert session_args[1] is None
        assert session_args[2] is None

    def _verify_exit_called_with_exception(self, client_exit, session_exit, exc_type, exc_val):
        client_exit.assert_called_once()
        session_exit.assert_called_once()

        client_args = client_exit.call_args[0]
        session_args = session_exit.call_args[0]

        assert client_args[0] == exc_type
        assert client_args[1] == exc_val
        assert client_args[2] is not None

        assert session_args[0] == exc_type
        assert session_args[1] == exc_val
        assert session_args[2] is not None

    def test_sse_context_managers_closed_on_success(self):
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_session = self._create_mock_session(
            call_tool_result=CallToolResult(
                content=[TextContent(type="text", text="test")], isError=False
            )
        )

        mock_sse_context, mock_sse_exit = self._create_mock_client_context(
            (mock_read_stream, mock_write_stream)
        )
        mock_session_context, mock_session_exit = self._create_mock_session_context(mock_session)

        with patch(
            "holmes.plugins.toolsets.mcp.toolset_mcp.sse_client",
            return_value=mock_sse_context,
        ):
            with patch(
                "holmes.plugins.toolsets.mcp.toolset_mcp.ClientSession",
                return_value=mock_session_context,
            ):
                async def run_test():
                    async with get_initialized_mcp_session(
                        "http://localhost:1234/sse", None, MCPMode.SSE
                    ) as session:
                        await session.call_tool("test", {})

                asyncio.run(run_test())

        self._verify_exit_called_with_no_exception(mock_sse_exit, mock_session_exit)

    def test_streamable_http_context_managers_closed_on_success(self):
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_session = self._create_mock_session()
        mock_session.list_tools = AsyncMock(return_value=ListToolsResult(tools=[]))

        mock_streamable_context, mock_streamable_exit = self._create_mock_client_context(
            (mock_read_stream, mock_write_stream, None)
        )
        mock_session_context, mock_session_exit = self._create_mock_session_context(mock_session)

        with patch(
            "holmes.plugins.toolsets.mcp.toolset_mcp.streamablehttp_client",
            return_value=mock_streamable_context,
        ):
            with patch(
                "holmes.plugins.toolsets.mcp.toolset_mcp.ClientSession",
                return_value=mock_session_context,
            ):
                async def run_test():
                    async with get_initialized_mcp_session(
                        "http://localhost:1234/mcp/messages", None, MCPMode.STREAMABLE_HTTP
                    ) as session:
                        await session.list_tools()

                asyncio.run(run_test())

        self._verify_exit_called_with_no_exception(mock_streamable_exit, mock_session_exit)

    def test_context_managers_closed_on_exception(self):
        test_error = RuntimeError("Test error")
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_session = self._create_mock_session(call_tool_side_effect=test_error)

        mock_sse_context, mock_sse_exit = self._create_mock_client_context(
            (mock_read_stream, mock_write_stream)
        )
        mock_session_context, mock_session_exit = self._create_mock_session_context(mock_session)

        with patch(
            "holmes.plugins.toolsets.mcp.toolset_mcp.sse_client",
            return_value=mock_sse_context,
        ):
            with patch(
                "holmes.plugins.toolsets.mcp.toolset_mcp.ClientSession",
                return_value=mock_session_context,
            ):
                async def run_test():
                    try:
                        async with get_initialized_mcp_session(
                            "http://localhost:1234/sse", None, MCPMode.SSE
                        ) as session:
                            await session.call_tool("test", {})
                    except RuntimeError:
                        pass

                asyncio.run(run_test())

        self._verify_exit_called_with_exception(
            mock_sse_exit, mock_session_exit, RuntimeError, test_error
        )
