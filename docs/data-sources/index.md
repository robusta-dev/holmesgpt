# Data Sources

HolmesGPT can incorporate data sources from various tools to improve its root cause analysis. This is done through configuring different types of integrations:

## Integration Types

### Built-in Toolsets
Pre-configured analysis capabilities that HolmesGPT can use to fetch data from common tools:

- **[View all Built-in Toolsets](builtin-toolsets/)** - Complete list of 19 supported integrations

### Custom Toolsets
User-defined investigation extensions for tools not covered by built-in toolsets:

- **[Custom Toolsets](custom-toolsets.md)** - Build your own integrations

### Remote MCP Servers
Additional data connection options through the Model Context Protocol:

- **[Remote MCP Servers](remote-mcp-servers.md)** - Connect external data sources (Tech Preview)

## Getting Started

1. **Review** the [built-in toolsets](builtin-toolsets/) to see what's available
2. **Configure** credentials for the data sources you want to use
3. **Test** with a sample investigation

Most toolsets work out-of-the-box with Kubernetes, while external services require API keys or authentication setup.
