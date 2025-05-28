# Data Sources

HolmesGPT can integrate with a wide variety of data sources to provide comprehensive analysis of your infrastructure and applications.

## Integration Types

### Built-in Toolsets
Pre-built integrations with popular tools and platforms:

- **[Kubernetes](builtin-toolsets/kubernetes.md)** - Pods, services, events, logs
- **[AWS](builtin-toolsets/aws.md)** - EC2, ECS, CloudWatch, and more
- **[Grafana](builtin-toolsets/grafana.md)** - Loki logs and Tempo traces
- **[Prometheus](builtin-toolsets/prometheus.md)** - Metrics and alerting
- **[And 14 more...](builtin-toolsets/)** - Complete list of supported integrations

### Custom Integration Options

- **[Custom Toolsets](custom-toolsets.md)** - Build your own integrations
- **[Remote MCP Servers](remote-mcp-servers.md)** - Connect external data sources (Tech Preview)

## How It Works

HolmesGPT automatically:

1. **Detects** relevant data sources based on your alert context
2. **Fetches** logs, metrics, and configuration data
3. **Correlates** information across multiple sources
4. **Analyzes** patterns to identify root causes

## Getting Started

1. **Review** the [built-in toolsets](builtin-toolsets/) to see what's available
2. **Configure** credentials for the data sources you want to use
3. **Test** with a sample investigation

Most toolsets work out-of-the-box with Kubernetes, while external services require API keys or authentication setup.

Explore our [built-in toolsets](builtin-toolsets/) to see what integrations are available for your stack.