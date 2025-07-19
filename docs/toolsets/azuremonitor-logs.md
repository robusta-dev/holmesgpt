# Azure Monitor Logs Toolset

## Overview

The Azure Monitor Logs toolset detects Azure Monitor Container Insights configuration and provides Log Analytics workspace details for AKS cluster log analysis. This toolset **does not execute KQL queries directly** - instead, it provides workspace configuration details for external Azure MCP server integration.

## Purpose

- **Container Insights Detection**: Automatically detect if Azure Monitor Container Insights is enabled for AKS clusters
- **Workspace Discovery**: Extract Log Analytics workspace ID and full Azure resource ID
- **Stream Profiling**: Identify enabled log streams and map them to Log Analytics tables
- **Azure MCP Integration**: Provide configuration details for external Azure MCP server setup

## Prerequisites

### Azure Dependencies
```bash
pip install azure-identity azure-mgmt-resourcegraph azure-mgmt-resource
```

### Authentication
The toolset uses `DefaultAzureCredential` for authentication. Configure one of:

- **Azure CLI** (recommended for development): `az login`
- **Managed Identity** (recommended for production in AKS)
- **Service Principal** (alternative method)

### Required Permissions
- **Reader** role on AKS cluster resource
- **Reader** role on Log Analytics workspace  
- **Reader** role on Data Collection Rules

### AKS Requirements
- AKS cluster with Azure Monitor Container Insights enabled
- kubectl access to target cluster (for auto-detection)

## Configuration

### Default Configuration (Auto-detection)
```yaml
toolsets:
  azuremonitorlogs:
    enabled: true
    auto_detect_cluster: true
```

### Advanced Configuration
```yaml
toolsets:
  azuremonitorlogs:
    enabled: true
    auto_detect_cluster: true
    cluster_name: "my-aks-cluster"
    cluster_resource_id: "/subscriptions/.../managedClusters/my-cluster"
    log_analytics_workspace_id: "12345678-1234-1234-1234-123456789012"
    log_analytics_workspace_resource_id: "/subscriptions/.../workspaces/my-workspace"
```

## Available Tools

### 1. check_aks_cluster_context
Checks if the current environment is running inside an AKS cluster.

**Usage**: Automatically called when investigating AKS-related issues.

### 2. get_aks_cluster_resource_id  
Gets the full Azure resource ID of the current AKS cluster.

**Usage**: Auto-detects cluster information for workspace discovery.

### 3. check_azure_monitor_logs_enabled
Detects if Azure Monitor Container Insights is enabled and provides workspace details.

**Usage**: Primary tool for Container Insights detection and Azure MCP configuration.

**Returns**:
- Container Insights status
- Log Analytics workspace ID and resource ID
- Available log streams
- Data collection configuration
- Azure MCP server configuration guidance

## Azure MCP Server Integration

This toolset provides configuration details for Azure MCP server setup:

### Workspace Configuration
- **Workspace ID** (GUID): For KQL query execution
- **Workspace Resource ID** (full path): For ARM API access
- **Cluster Filter**: Required `_ResourceId` value for query filtering

### Log Stream Information
- **Available Streams**: ContainerLogV2, KubePodInventory, KubeEvents, etc.
- **Table Mapping**: Stream names to Log Analytics table names
- **Sample Queries**: Properly filtered KQL query examples

## Critical KQL Query Requirements

**ALL KQL queries executed via Azure MCP server MUST include cluster filtering:**

```kql
| where _ResourceId == "/subscriptions/.../clusters/your-cluster"
```

### Common Log Analytics Tables
Based on detected streams:
- **ContainerLogV2**: Container stdout/stderr logs
- **KubePodInventory**: Pod metadata and status
- **KubeEvents**: Kubernetes events
- **KubeNodeInventory**: Node information
- **Perf**: Performance metrics
- **InsightsMetrics**: Additional metrics data

## Example Workflows

### Initial Setup Detection
```bash
holmes ask "Is Azure Monitor logs enabled for this cluster?"
```

Expected response includes:
- Container Insights enablement status
- Log Analytics workspace details
- Available log streams
- Azure MCP configuration guidance

### Log Analysis Workflow
1. **Detection**: Use toolset to detect workspace configuration
2. **MCP Setup**: Configure Azure MCP server with detected details
3. **Querying**: Use Azure MCP server for actual KQL log queries

### Stream Availability Check
```bash
holmes ask "What log data is available for this cluster?"
```

Returns available streams and corresponding Log Analytics tables.

## Troubleshooting

### Authentication Issues
```
Error: DefaultAzureCredential failed to retrieve a token
```
**Solution**: Verify Azure authentication configuration (CLI, managed identity, or service principal).

### AKS Cluster Not Detected
```
Error: Could not determine AKS cluster resource ID
```
**Solutions**:
- Check kubectl connection: `kubectl config current-context`
- Verify Azure CLI login: `az account show`
- Manually specify cluster resource ID in configuration

### Container Insights Not Found
```
Error: Azure Monitor Container Insights (logs) is not enabled
```
**Solutions**:
- Enable Container Insights in Azure portal
- Verify Data Collection Rules configuration
- Check Azure Resource Graph API permissions

### Missing Dependencies
```
ImportError: No module named 'azure.mgmt.resourcegraph'
```
**Solution**: Install required packages:
```bash
pip install azure-mgmt-resourcegraph
```

## Debug Mode
Enable debug logging:
```bash
export HOLMES_LOG_LEVEL=DEBUG
holmes ask "check azure monitor logs status"
```

## Integration with Azure MCP Server

1. **Use this toolset** to detect workspace configuration
2. **Configure Azure MCP server** with detected workspace details:
   ```json
   {
     "workspace_id": "detected-workspace-guid",
     "workspace_resource_id": "/subscriptions/.../workspaces/name",
     "cluster_filter": "| where _ResourceId == \"cluster-resource-id\""
   }
   ```
3. **Execute KQL queries** via Azure MCP server with mandatory cluster filtering

## Support

For toolset-specific issues:
1. Verify Azure authentication and permissions
2. Check AKS cluster connectivity  
3. Confirm Container Insights configuration
4. Test Azure Resource Graph API access

For Azure MCP server issues, refer to Azure MCP server documentation.

## Related Documentation
- [Azure Monitor Metrics Toolset](azuremonitor-metrics.md)
- [Azure Container Insights Documentation](https://docs.microsoft.com/en-us/azure/azure-monitor/containers/container-insights-overview)
- [Azure Resource Graph Documentation](https://docs.microsoft.com/en-us/azure/governance/resource-graph/)
