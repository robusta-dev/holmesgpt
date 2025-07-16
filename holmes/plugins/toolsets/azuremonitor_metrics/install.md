# Azure Monitor Metrics Toolset Installation Guide

## Overview

The Azure Monitor Metrics toolset enables HolmesGPT to query Azure Monitor managed Prometheus metrics for AKS cluster analysis and troubleshooting. This toolset automatically detects AKS cluster configuration and provides filtered access to cluster-specific metrics.

## Prerequisites

### 1. AKS Cluster with Azure Monitor

Your AKS cluster must have Azure Monitor managed Prometheus enabled. You can enable this in several ways:

#### Option A: Enable via Azure Portal
1. Navigate to your AKS cluster in the Azure Portal
2. Go to **Monitoring** > **Insights**
3. Click **Configure monitoring**
4. Enable **Prometheus metrics**
5. Select or create an Azure Monitor workspace

#### Option B: Enable via Azure CLI
```bash
# Create Azure Monitor workspace (if needed)
az monitor account create \
  --name myAzureMonitorWorkspace \
  --resource-group myResourceGroup \
  --location eastus

# Enable managed Prometheus on existing AKS cluster
az aks update \
  --resource-group myResourceGroup \
  --name myAKSCluster \
  --enable-azure-monitor-metrics \
  --azure-monitor-workspace-resource-id /subscriptions/{subscription-id}/resourceGroups/myResourceGroup/providers/microsoft.monitor/accounts/myAzureMonitorWorkspace
```

#### Option C: Enable via ARM Template/Bicep
Include Azure Monitor configuration in your AKS deployment templates.

### 2. Azure Credentials

The toolset uses Azure DefaultAzureCredential, which supports multiple authentication methods:

#### When running inside AKS (Recommended)
- Uses **Managed Identity** automatically
- No additional configuration required
- Most secure approach

#### When running locally or in CI/CD
Choose one of these methods:

**Azure CLI Authentication:**
```bash
az login
az account set --subscription "your-subscription-id"
```

**Service Principal (Environment Variables):**
```bash
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
```

**Managed Identity (when running on Azure VM):**
```bash
export AZURE_CLIENT_ID="your-managed-identity-client-id"
```

### 3. Required Azure Permissions

The credential used must have the following permissions:

- **Reader** role on the AKS cluster resource
- **Reader** role on the Azure Monitor workspace
- **Monitoring Reader** role for querying metrics
- Access to execute Azure Resource Graph queries

## Configuration

### Automatic Configuration (Recommended)

The toolset auto-detects configuration when running in AKS:

```yaml
# ~/.holmes/config.yaml
toolsets:
  azuremonitor-metrics:
    auto_detect_cluster: true  # Default: true
    cache_duration_seconds: 1800  # Default: 30 minutes
```

### Manual Configuration

For explicit configuration or when running outside AKS:

```yaml
# ~/.holmes/config.yaml
toolsets:
  azuremonitor-metrics:
    azure_monitor_workspace_endpoint: "https://your-workspace.prometheus.monitor.azure.com/"
    cluster_name: "your-aks-cluster-name"
    cluster_resource_id: "/subscriptions/xxx/resourceGroups/xxx/providers/Microsoft.ContainerService/managedClusters/xxx"
    auto_detect_cluster: false
    cache_duration_seconds: 1800
    tool_calls_return_data: true
```

### Environment Variables

You can also configure via environment variables:

```bash
export AZURE_MONITOR_WORKSPACE_ENDPOINT="https://your-workspace.prometheus.monitor.azure.com/"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
```

## Verification

Test the toolset configuration:

```bash
# Check if toolset is enabled
holmes ask "Check if Azure Monitor metrics toolset is available"

# Test AKS detection
holmes ask "Am I running in an AKS cluster?"

# Verify Azure Monitor Prometheus
holmes ask "Is Azure Monitor managed Prometheus enabled for this cluster?"

# Test a simple query
holmes ask "Show current pod count in this cluster"
```

## Troubleshooting

### Common Issues

**1. "Not running in AKS cluster"**
- Verify you're running inside a Kubernetes pod with service account
- Check if Azure Instance Metadata Service is accessible
- Consider using manual configuration

**2. "Azure Monitor managed Prometheus is not enabled"**
- Follow the prerequisites to enable managed Prometheus
- Verify the data collection rule is properly configured
- Check if the cluster is associated with an Azure Monitor workspace

**3. "Authentication failed"**
- Verify Azure credentials are properly configured
- Check if the credential has required permissions
- For Managed Identity, ensure it's enabled on the AKS cluster

**4. "Query returned no results"**
- Check if the metric exists in your cluster
- Verify cluster filtering is not too restrictive
- Try disabling auto-cluster filtering temporarily

**5. "Failed to get AKS cluster resource ID"**
- Ensure proper Azure credentials
- Verify the credential has Reader access to the cluster
- Check if running in the correct subscription context

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
export HOLMES_LOG_LEVEL=DEBUG
holmes ask "Debug Azure Monitor toolset setup"
```

### Manual Testing

Test Azure Resource Graph connectivity:

```bash
# Test with Azure CLI
az graph query -q "resources | where type == 'Microsoft.ContainerService/managedClusters' | limit 5"
```

Test Azure Monitor workspace access:

```bash
# Test endpoint accessibility (replace with your endpoint)
curl -X POST "https://your-workspace.prometheus.monitor.azure.com/api/v1/query" \
  -d "query=up" \
  -H "Authorization: Bearer $(az account get-access-token --query accessToken -o tsv)"
```

## Security Considerations

1. **Use Managed Identity** when running in AKS for better security
2. **Limit permissions** to only what's required (Reader roles)
3. **Rotate credentials** regularly for service principals
4. **Monitor access** through Azure Activity Logs
5. **Use private endpoints** for Azure Monitor workspaces in production

## Support

For issues specific to this toolset:
1. Check the debug logs for detailed error messages
2. Verify Azure Monitor workspace is properly configured
3. Test Azure credentials and permissions
4. Consult the main HolmesGPT documentation

For Azure Monitor managed Prometheus issues:
- Azure Monitor documentation
- Azure support channels
- AKS monitoring troubleshooting guides
