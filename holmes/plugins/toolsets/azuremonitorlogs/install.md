# Azure Monitor Logs Toolset Installation Guide

## Overview
The Azure Monitor Logs toolset detects Azure Monitor Container Insights configuration and provides Log Analytics workspace details for AKS cluster log analysis via external Azure MCP server.

## Prerequisites

### 1. Azure Dependencies
Install required Azure SDK packages:
```bash
pip install azure-identity azure-mgmt-resourcegraph azure-mgmt-resource
```

### 2. Azure Authentication
The toolset uses `DefaultAzureCredential` for authentication. Ensure one of the following is configured:

#### Option A: Azure CLI (Recommended for development)
```bash
az login
az account set --subscription "your-subscription-id"
```

#### Option B: Managed Identity (Recommended for production in AKS)
When running in AKS, configure managed identity with appropriate permissions.

#### Option C: Service Principal (Alternative)
```bash
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
```

### 3. Required Azure Permissions
The authentication principal needs these permissions:

- **Reader** role on the AKS cluster resource
- **Reader** role on the Log Analytics workspace
- **Reader** role on Data Collection Rules (for Container Insights detection)

### 4. AKS Cluster Requirements
- AKS cluster with Azure Monitor Container Insights enabled
- Access to kubectl configured for the target cluster (for auto-detection)

## Configuration

### Basic Configuration (Auto-detection)
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
    cluster_resource_id: "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.ContainerService/managedClusters/my-cluster"
    log_analytics_workspace_id: "87654321-4321-4321-4321-210987654321"
    log_analytics_workspace_resource_id: "/subscriptions/12345678-1234-1234-1234-123456789012/resourcegroups/my-rg/providers/microsoft.operationalinsights/workspaces/my-workspace"
```

## Verification

### 1. Check Toolset Status
```bash
holmes toolset list | grep azuremonitorlogs
```

Expected output:
```
azuremonitorlogs    │ True    │ enabled  │ built-in │      │
```

### 2. Test AKS Detection
```bash
holmes ask "is this an aks cluster?"
```

### 3. Test Container Insights Detection
```bash
holmes ask "is azure monitor logs enabled for this cluster?"
```

Expected response should include:
- Container Insights status
- Log Analytics workspace details
- Available log streams
- Azure MCP configuration guidance

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
```
Error: DefaultAzureCredential failed to retrieve a token
```

**Solution**: Ensure Azure authentication is properly configured (see Prerequisites section).

#### 2. No AKS Cluster Detected
```
Error: Could not determine AKS cluster resource ID
```

**Solutions**:
- Ensure kubectl is connected to an AKS cluster: `kubectl config current-context`
- Verify Azure CLI is logged in: `az account show`
- Manually specify cluster resource ID in configuration

#### 3. Container Insights Not Found
```
Error: Azure Monitor Container Insights (logs) is not enabled
```

**Solutions**:
- Enable Container Insights in Azure portal for the AKS cluster
- Verify Data Collection Rules are properly configured
- Check Azure Resource Graph permissions

#### 4. Missing Dependencies
```
ImportError: No module named 'azure.mgmt.resourcegraph'
```

**Solution**: Install required packages:
```bash
pip install azure-mgmt-resourcegraph
```

### Debug Mode
Enable debug logging to troubleshoot issues:
```bash
export HOLMES_LOG_LEVEL=DEBUG
holmes ask "check azure monitor logs status"
```

## Azure MCP Server Integration

Once the Azure Monitor Logs toolset detects your workspace, configure Azure MCP server:

### 1. Azure MCP Server Installation
Follow Azure MCP server documentation for installation and configuration.

### 2. Workspace Configuration
Use the workspace details provided by this toolset:
```json
{
  "workspace_id": "detected-workspace-guid",
  "workspace_resource_id": "/subscriptions/.../workspaces/workspace-name",
  "cluster_filter": "| where _ResourceId == \"/subscriptions/.../clusters/cluster-name\""
}
```

### 3. Required KQL Query Filtering
ALL KQL queries via Azure MCP server MUST include cluster filtering:
```kql
ContainerLogV2 
| where _ResourceId == "/subscriptions/.../clusters/your-cluster"
| where TimeGenerated > ago(1h)
```

## Support
For issues specific to this toolset, check:
1. Azure authentication and permissions
2. AKS cluster connectivity
3. Container Insights configuration
4. Azure Resource Graph API access

For Azure MCP server issues, refer to the Azure MCP server documentation.
