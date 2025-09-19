import pytest
import re
from holmes.core.tools import (
    ToolParameter,
)
from mcp.types import ListToolsResult, Tool
from holmes.plugins.toolsets.mcp.toolset_mcp import (
    RemoteMCPToolset,
    RemoteMCPTool,
    StdioMCPToolset,
    get_mcp_toolset_from_config,
)


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
                    # find more examples to improve description with format hints.
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
        config={"url": "http://0.0.0.0:3009"},
        name="test_mcp",
        description="",
    )

    result = mcp_toolset.init_server_tools(config=None)
    assert result[0] is False
    assert "Failed to load remote mcp server test_mcp" in result[1]


def test_mcpserver_1tool(monkeypatch):
    mcp_toolset = RemoteMCPToolset(
        config={"url": "http://0.0.0.0/3005"},
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
        config={
            "url": "http://0.0.0.0/3005",
            "headers": {"header1": "test1", "header2": "test2"},
        },
        name="test_mcp",
        description="demo mcp with 2 simple functions",
    )

    assert mcp_toolset.headers.get("header1") == "test1"


def test_mcpserver_no_headers():
    mcp_toolset1 = RemoteMCPToolset(
        config={"url": "http://0.0.0.0/3005"},
        name="test_mcp",
        description="demo mcp with 2 simple functions",
    )

    assert mcp_toolset1.headers is None


def test_stdio_mcpserver_notfound():
    mcp_toolset = StdioMCPToolset(
        config={"command": "/user/bin/mcp_server", "args": ["--transport", "stdio"]},
        name="test_mcp",
        description="demo mcp with 2 simple functions",
    )

    result = mcp_toolset.init_server_tools(config=None)
    assert result[0] is False
    assert "Failed to load stdio mcp server test_mcp" in result[1]


def test_get_mcp_toolset_from_config_empty_config():
    """Test that empty config raises ValueError"""
    with pytest.raises(ValueError, match="Config must not be empty"):
        get_mcp_toolset_from_config({}, "test")


def test_get_mcp_toolset_from_config_sse_type():
    """Test creating RemoteMCPToolset with explicit 'sse' type in config"""
    config = {"config": {"type": "sse", "url": "http://example.com/sse"}}
    toolset = get_mcp_toolset_from_config(config, "test_sse")

    assert isinstance(toolset, RemoteMCPToolset)
    assert toolset.name == "test_sse"
    assert toolset.url == "http://example.com/sse"


def test_get_mcp_toolset_from_config_stdio_type():
    """Test creating StdioMCPToolset with explicit 'stdio' type in config"""
    config = {
        "config": {"type": "stdio", "command": "python", "args": ["/path/to/server.py"]}
    }
    toolset = get_mcp_toolset_from_config(config, "test_stdio")

    assert isinstance(toolset, StdioMCPToolset)
    assert toolset.name == "test_stdio"
    assert toolset.config.get("command") == "python"
    assert toolset.config.get("args") == ["/path/to/server.py"]


def test_get_mcp_toolset_from_config_backward_compatibility_with_url():
    """Test backward compatibility when using top-level url key"""
    config = {"url": "http://example.com/api"}
    toolset = get_mcp_toolset_from_config(config, "test_backward")

    assert isinstance(toolset, RemoteMCPToolset)
    assert toolset.name == "test_backward"
    # /sse gets appended by the validator
    assert toolset.url == "http://example.com/api/sse"


def test_get_mcp_toolset_from_config_backward_compatibility_url_already_has_sse():
    """Test backward compatibility when url already ends with /sse"""
    config = {"url": "http://example.com/api/sse"}
    toolset = get_mcp_toolset_from_config(config, "test_backward_sse")

    assert isinstance(toolset, RemoteMCPToolset)
    assert toolset.name == "test_backward_sse"
    assert toolset.url == "http://example.com/api/sse"


def test_get_mcp_toolset_from_config_no_url_no_type():
    """Test that missing url and type raises ValueError"""
    config = {"config": {}, "some_other_key": "value"}
    with pytest.raises(
        ValueError,
        match=re.escape(
            "MCP Server config must include a transport type ('sse' or 'stdio') either in 'config.type' or by providing transport-specific keys."
        ),
    ):
        get_mcp_toolset_from_config(config, "test_no_url")


def test_get_mcp_toolset_from_config_with_additional_params():
    """Test config with additional parameters like headers"""
    config = {
        "config": {
            "type": "sse",
            "url": "http://example.com",
            "headers": {"Authorization": "***"},
        },
        "description": "Test toolset",
    }
    toolset = get_mcp_toolset_from_config(config, "test_extra_params")

    assert isinstance(toolset, RemoteMCPToolset)
    assert toolset.name == "test_extra_params"
    assert toolset.description == "Test toolset"
    assert toolset.config["headers"]["Authorization"] == "***"


def test_get_mcp_toolset_from_config_stdio_with_empty_args():
    """Test stdio config with empty args list"""
    config = {"config": {"type": "stdio", "command": "node", "args": []}}
    toolset = get_mcp_toolset_from_config(config, "test_stdio_no_args")

    assert isinstance(toolset, StdioMCPToolset)
    assert toolset.name == "test_stdio_no_args"
    assert toolset.config.get("command") == "node"
    assert toolset.config.get("args") == []
