# Azure Monitor Metrics Toolset Setup Guide

## Issue Description

When running HolmesGPT from outside an AKS cluster (such as from a local development environment), you may encounter this error:

```
Cannot determine if Azure Monitor metrics is enabled because this environment is not running inside an AKS cluster. Please run this from within your AKS cluster or provide cluster details.
```

This happens because the Azure Monitor metrics toolset is designed to auto-detect cluster configuration when running inside AKS pods, but fails when running externally.

## Solution

The Azure Monitor metrics toolset now has enhanced auto-detection capabilities using kubectl and Azure CLI. It can automatically discover AKS clusters from external environments.

### Step 1: Prerequisites

Ensure you have the following tools installed and configured:

1. **kubectl** - Connected to your AKS cluster
2. **Azure CLI** - Logged in with `az login`

### Step 2: Automatic Detection (Recommended)

The toolset can now automatically detect your AKS cluster if kubectl is connected:

```yaml
toolsets:
  azuremonitor-metrics:
    auto_detect_cluster: true  # Enable auto-detection via kubectl and Azure CLI
    cache_duration_seconds: 1800
    tool_calls_return_data: true
```

### Step 3: Manual Configuration (If Auto-Detection Fails)

If automatic detection doesn't work, configure manually:

```yaml
toolsets:
  azuremonitor-metrics:
    auto_detect_cluster: false
    cache_duration_seconds: 1800
    tool_calls_return_data: true
    # Option 1: Provide full details
    azure_monitor_workspace_endpoint: "https://your-workspace.prometheus.monitor.azure.com/"
    cluster_name: "your-aks-cluster-name"
    cluster_resource_id: "/subscriptions/xxx/resourceGroups/xxx/providers/Microsoft.ContainerService/managedClusters/xxx"
    
    # Option 2: Just provide cluster_resource_id (toolset will discover workspace)
    # cluster_resource_id: "/subscriptions/xxx/resourceGroups/xxx/providers/Microsoft.ContainerService/managedClusters/xxx"
```

### How Auto-Detection Works

The enhanced detection mechanism uses multiple methods:

1. **kubectl Analysis**: Examines current kubectl context and cluster server URL
2. **Node Labels**: Checks AKS-specific node labels for cluster resource ID
3. **Azure CLI Integration**: Uses `az aks list` to find matching clusters
4. **Server URL Parsing**: Extracts cluster name and region from AKS API server URL

### Manual Configuration (If Needed)

If auto-detection fails, you can manually configure:

#### Method 1: Using Azure CLI

```bash
# List your AKS clusters
az aks list --output table

# Get specific cluster details
az aks show --resource-group <your-resource-group> --name <your-cluster-name> --query id --output tsv

# Example output:
# /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.ContainerService/managedClusters/my-cluster
```

#### Method 2: Using kubectl

```bash
# Check current context
kubectl config current-context

# Get cluster info
kubectl cluster-info

# Check if connected to AKS (look for azmk8s.io in server URL)
kubectl config view --minify --output jsonpath='{.clusters[].cluster.server}'
```

#### Method 3: Update Configuration

Edit the `config.yaml` file with your cluster details:

```yaml
toolsets:
  azuremonitor-metrics:
    auto_detect_cluster: false
    cache_duration_seconds: 1800
    tool_calls_return_data: true
    azure_monitor_workspace_endpoint: "https://myworkspace-abc123.prometheus.monitor.azure.com/"
    cluster_name: "my-aks-cluster"
    cluster_resource_id: "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.ContainerService/managedClusters/my-aks-cluster"
```

### Step 4: Verify kubectl Connection

Make sure kubectl is connected to your AKS cluster:

```bash
# Check current context
kubectl config current-context

# Test connection
kubectl get nodes

# Verify you're connected to AKS (server URL should contain azmk8s.io)
kubectl cluster-info
```

### Step 5: Ensure Azure Authentication

Make sure you have Azure credentials configured. The toolset uses Azure DefaultAzureCredential, which supports:

1. **Azure CLI** (recommended for local development):
   ```bash
   az login
   az account set --subscription <your-subscription-id>
   ```

2. **Environment Variables**:
   ```bash
   export AZURE_CLIENT_ID="your-client-id"
   export AZURE_CLIENT_SECRET="your-client-secret"
   export AZURE_TENANT_ID="your-tenant-id"
   export AZURE_SUBSCRIPTION_ID="your-subscription-id"
   ```

3. **Managed Identity** (when running in Azure)

### Step 6: Verify Required Permissions

Ensure your Azure credentials have the following permissions:

- **Reader** role on the AKS cluster resource
- **Reader** role on the Azure Monitor workspace  
- **Monitoring Reader** role for querying metrics
- Permission to execute Azure Resource Graph queries

### Step 7: Test the Configuration

Run HolmesGPT again to test:

```bash
poetry run python3 holmes_cli.py ask "is azure monitor metrics enabled for this cluster?" --model="azure/gpt-4.1"
```

## Alternative: Simplified Configuration

If you only provide the cluster resource ID, the toolset will attempt to automatically discover the associated Azure Monitor workspace:

```yaml
toolsets:
  azuremonitor-metrics:
    auto_detect_cluster: false
    cluster_resource_id: "/subscriptions/xxx/resourceGroups/xxx/providers/Microsoft.ContainerService/managedClusters/xxx"
```

This approach uses Azure Resource Graph queries to find the workspace configuration automatically.

## Troubleshooting

### "Azure Monitor managed Prometheus is not enabled"

This means your AKS cluster doesn't have Azure Monitor managed Prometheus enabled. Enable it using:

```bash
az aks update \
  --resource-group <your-resource-group> \
  --name <your-cluster-name> \
  --enable-azure-monitor-metrics
```

### "Authentication failed"

1. Verify you're logged in to Azure CLI: `az account show`
2. Check you have the correct subscription selected: `az account set --subscription <id>`
3. Verify your permissions on the cluster and workspace resources

### "Query returned no results"

1. Verify the cluster name is correct
2. Check if metrics are actually being collected in Azure Monitor
3. Try disabling auto-cluster filtering temporarily:

```bash
poetry run python3 holmes_cli.py ask "run a prometheus query: up" --model="azure/gpt-4.1"
```

## Benefits of External Configuration

Running HolmesGPT externally (not in AKS) provides several advantages:

1. **Development Environment**: Test queries and troubleshooting from your local machine
2. **CI/CD Integration**: Include in automated pipelines for cluster health checks
3. **Multi-Cluster Support**: Configure multiple clusters and switch between them
4. **Enhanced Security**: Run with specific permissions rather than cluster-wide access

## Example Usage After Configuration

Once configured, you can use Azure Monitor metrics queries:

```bash
# Check cluster health
poetry run python3 holmes_cli.py ask "what is the current resource utilization of this cluster?" --model="azure/gpt-4.1"

# Investigate specific issues
poetry run python3 holmes_cli.py ask "show me pods with high memory usage in the last hour" --model="azure/gpt-4.1"

# Custom PromQL queries
poetry run python3 holmes_cli.py ask "run this prometheus query: container_cpu_usage_seconds_total" --model="azure/gpt-4.1"
```

The toolset will automatically add cluster filtering to ensure queries are scoped to your specific cluster.
