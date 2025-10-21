# Configuring Toolsets

HolmesGPT provides flexible toolset configuration options for both CLI and Kubernetes deployments. This guide explains how to configure built-in toolsets and add custom toolsets.

## Configuration Overview

There are three types of toolset configurations:

1. **Built-in Toolset Configuration**: Modify settings for existing toolsets (enable/disable, change configuration)
2. **Custom Toolsets**: Add entirely new toolsets with custom tools
3. **MCP Servers**: Add Model Context Protocol servers for extended capabilities

!!! important "Configuration vs Override"
    You can **configure** built-in toolsets (change settings, enable/disable) but you cannot **override** them completely. To add new functionality, create a custom toolset with a unique name.

## CLI Configuration

### Built-in Toolset Configuration

Configure built-in toolsets in `~/.holmes/config.yaml`:

```yaml
# Configure built-in toolsets
toolsets:
  kubernetes/core:
    enabled: true
    config:
      timeout: 60

  prometheus/metrics:
    enabled: true
    config:
      url: "http://prometheus.monitoring:9090"

  datadog/metrics:
    enabled: false  # Disable this toolset

# Add MCP servers
mcp_servers:
  my-mcp-server:
    url: "http://localhost:8000/sse"
    description: "Custom MCP server"
```

### Custom Toolsets

Add custom toolsets by creating YAML files in `~/.holmes/custom_toolsets/`:

```bash
# Create the directory if it doesn't exist
mkdir -p ~/.holmes/custom_toolsets

# Create a custom toolset file
cat > ~/.holmes/custom_toolsets/my_tools.yaml << EOF
toolsets:
  my-monitoring:
    description: "Custom monitoring tools"
    tools:
      - name: check_service
        description: "Check service status"
        command: "systemctl status {{ service_name }}"
    enabled: true

mcp_servers:
  local-mcp:
    url: "http://localhost:8000/sse"
    description: "Local MCP server"
EOF
```

You can also specify custom toolset files using the `-t` flag:

```bash
holmes ask "check system status" -t /path/to/custom_toolset.yaml
```

## Kubernetes/Helm Configuration

When deploying with Helm, configuration is split into three sections:

### values.yaml Structure

```yaml
# 1. Configure built-in toolsets (can only configure, not override)
toolsets:
  kubernetes/core:
    enabled: true
    config:
      timeout: 60

  prometheus/metrics:
    enabled: true
    config:
      url: "http://prometheus.monitoring:9090"

  grafana/loki:
    enabled: true
    config:
      url: "http://loki.monitoring:3100"

# 2. Add custom toolsets (new toolsets with unique names)
custom_toolsets:
  my-monitoring:
    description: "Custom monitoring integration"
    tools:
      - name: check_custom_metric
        description: "Check custom application metrics"
        command: "curl http://my-app:8080/metrics"
    enabled: true

# 3. Add MCP servers
mcp_servers:
  production-mcp:
    url: "http://mcp-server.default:8000/sse"
    description: "Production MCP server"
    config:
      api_key: "{{ env.MCP_API_KEY }}"
```

### How It Works

1. **Built-in toolset configuration** (`toolsets:`) is passed via environment variable to the HolmesGPT container
2. **Custom toolsets and MCP servers** are mounted as files in `/etc/holmes/toolsets/`
3. The `CUSTOM_TOOLSET_DIR` environment variable points to `/etc/holmes/toolsets/`

## Configuration Merging

When configuring built-in toolsets, your configuration is **merged** with defaults:

```yaml
# Default built-in configuration
toolsets:
  prometheus/metrics:
    enabled: false
    config:
      url: "http://localhost:9090"
      timeout: 30
      retry_count: 3

# Your configuration
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      url: "http://prometheus.monitoring:9090"
      # timeout and retry_count are preserved from defaults

# Result after merging
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      url: "http://prometheus.monitoring:9090"  # Your value
      timeout: 30                                 # Default preserved
      retry_count: 3                              # Default preserved
```

## Migration Guide

### For CLI Users

If you previously had custom toolsets in your config.yaml trying to add new toolsets:

1. Move custom toolsets to `~/.holmes/custom_toolsets/`:
   ```bash
   mkdir -p ~/.holmes/custom_toolsets
   # Create a new file for your custom toolsets
   ```

2. Keep only built-in toolset configuration in `~/.holmes/config.yaml`:
   ```bash
   # Edit ~/.holmes/config.yaml and keep only built-in toolset config
   ```

### For Helm Users

If you previously configured toolsets in Helm values:

1. Keep built-in toolset configuration in the `toolsets:` section
2. Move any NEW custom toolsets to the `custom_toolsets:` section
3. MCP servers remain in the `mcp_servers:` section

**Before:**
```yaml
toolsets:
  kubernetes/core:
    enabled: true
  my-custom-tool:  # This would fail now
    description: "Custom tool"
    tools: [...]
```

**After:**
```yaml
toolsets:
  kubernetes/core:
    enabled: true

custom_toolsets:
  my-custom-tool:  # Moved to custom_toolsets
    description: "Custom tool"
    tools: [...]
```

## Environment Variables

### CLI Environment Variables

- `CUSTOM_TOOLSET_DIR`: Directory containing custom toolset YAML files (default: `~/.holmes/custom_toolsets`)

### Helm Environment Variables

The Helm chart automatically sets:
- `CUSTOM_TOOLSET_DIR=/etc/holmes/toolsets`
- `HOLMES_BUILTIN_TOOLSETS_CONFIG`: JSON-encoded built-in toolset configuration

## Validation and Errors

### Common Issues

1. **Attempting to override built-in toolset**:
   ```
   Error: Custom toolsets {'kubernetes/core'} conflict with builtin toolsets
   ```
   **Solution**: Use a different name for your custom toolset or configure the built-in one

2. **Invalid toolset configuration**:
   ```
   Error: Toolset 'my-tool' is invalid: missing required field 'description'
   ```
   **Solution**: Ensure all required fields are present in your toolset definition


## Best Practices

1. **Use descriptive names** for custom toolsets that don't conflict with built-ins
2. **Test custom toolsets** with `holmes toolset list` to verify they load correctly
3. **Keep sensitive configuration** in environment variables, not in YAML files
4. **Document prerequisites** clearly in your custom toolset definitions
5. **Version control** your custom toolset files for team sharing

## Reference

### Built-in Toolsets

To see all available built-in toolsets and their configuration options:

```bash
holmes toolset list --all
```

### Toolset Schema

```yaml
toolsets:
  <toolset-name>:
    description: string        # Required: Human-readable description
    enabled: boolean          # Optional: Default false
    tools: list              # Required: List of tools
    config: object          # Optional: Configuration values
    prerequisites: list     # Optional: Prerequisite checks
    tags: list             # Optional: Categorization tags
    additional_instructions: string  # Optional: Extra LLM instructions
```

### MCP Server Schema

```yaml
mcp_servers:
  <server-name>:
    url: string           # Required: Server endpoint URL
    description: string   # Required: Human-readable description
    config: object       # Optional: Server-specific configuration
```
