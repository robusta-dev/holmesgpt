# Model Context Protocol (MCP)

!!! info "Tech Preview"
    This feature is currently in tech preview. The configuration may change in future releases.

Connect HolmesGPT to external MCP servers to extend its capabilities with custom tools and data sources. MCP provides a standardized way to integrate external services.

## Prerequisites

1. An external MCP server running and accessible
2. MCP server endpoint URL
3. Any required authentication credentials for the MCP server

## Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      mcp/remote:
        enabled: true
        config:
          servers:
            - name: "custom-tools"
              endpoint: "http://your-mcp-server:8080"
              mode: "sse"  # Server-Sent Events mode
              headers:
                Authorization: "Bearer your-token"
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        mcp/remote:
          enabled: true
          config:
            servers:
              - name: "custom-tools"
                endpoint: "http://your-mcp-server:8080"
                mode: "sse"
                headers:
                  Authorization: "Bearer your-token"
    ```

## Advanced Configuration

You can configure multiple MCP servers with different settings:

```yaml
toolsets:
  mcp/remote:
    enabled: true
    config:
      timeout: 30  # Request timeout in seconds
      max_retries: 3  # Maximum number of retries
      servers:
        - name: "primary-tools"
          endpoint: "http://primary-mcp-server:8080"
          timeout: 60  # Server-specific timeout
          headers:
            Authorization: "Bearer <token>"
            X-API-Version: "v1"
        - name: "backup-tools"
          endpoint: "https://backup-mcp-server.com"
          verify_ssl: false  # For development/testing
```

## MCP Server Examples

Popular MCP servers you can integrate:

- **Database MCP**: Direct database query capabilities
- **Cloud Provider MCP**: AWS/Azure/GCP specific tools
- **Monitoring MCP**: Custom monitoring system integration
- **Internal Tools MCP**: Company-specific tooling

## Capabilities

The capabilities depend on the connected MCP servers. Common tool types include:

| Tool Category | Description |
|---------------|-------------|
| Data Sources | Access to external databases, APIs, or files |
| Custom Commands | Organization-specific operational commands |
| Specialized Analysis | Domain-specific analysis tools |
| External Integrations | Third-party service integrations |

!!! info "Dynamic Capabilities"
    The exact tools available through MCP servers are discovered dynamically when the toolset connects to each server.

## Creating Your Own MCP Server

To create a custom MCP server for your organization:

1. Implement the MCP specification
2. Expose your tools via the MCP protocol
3. Configure HolmesGPT to connect to your server
4. Your custom tools will be automatically available to Holmes

See the [MCP documentation](https://github.com/modelcontextprotocol/specification) for implementation details.
