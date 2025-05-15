from holmes.core.tools import (
    ToolParameter,
)
from mcp.types import ListToolsResult, Tool
from holmes.plugins.toolsets.mcp.toolset_mcp import MCPToolset, MCPTool


def test_parse_mcp_tool_input_schema_conversion():
    input_schema_sample = {
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
    }

    expected_ouput = {
        "symbol": ToolParameter(type="string", required=True),
        "qty": ToolParameter(
            type="integer", required=True, description="example for description"
        ),
        "side": ToolParameter(type="string", required=True),
        "limit_price": ToolParameter(type="number", required=False),
    }
    tool_params = MCPTool.parse_input_schema(input_schema_sample)

    assert tool_params == expected_ouput


def test_parse_mcp_tool():
    mcp_tool = Tool(
        name="b",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
            },
            "required": [],
        },
        description="desc",
        annotations=None,
    )

    tool = MCPTool.create("url", mcp_tool)
    assert tool.description == "desc"


def test_mcpserver_unreachable():
    mcp_toolset = MCPToolset(
        url="http://0.0.0.0/3009",
        name="test_mcp",
        description="",
    )
    assert (
        False,
        "Failed to load mcp server test_mcp http://0.0.0.0/3009/sse tools: ('unhandled errors in a TaskGroup', [ConnectError('All connection attempts failed')])",
    ) == mcp_toolset.init_server_tools()


def test_mcpserver_1tool(monkeypatch):
    mcp_toolset = MCPToolset(
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
    mcp_toolset.init_server_tools()
    assert len(list(mcp_toolset.tools)) == 1
