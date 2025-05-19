from holmes.core.tools import (
    ToolParameter,
)
from mcp.types import ListToolsResult, Tool
from holmes.plugins.toolsets.mcp.toolset_mcp import RemoteMCPToolset, RemoteMCPTool


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
                },  # find more examples to improve description with format hints.
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

    assert (
        False,
        "Failed to load mcp server test_mcp http://0.0.0.0:3009/sse ('unhandled errors in a TaskGroup', [ConnectError('All connection attempts failed')])",
    ) == mcp_toolset.init_server_tools(config=None)


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
