# Azure Monitor Metrics Toolset

## Overview

The Azure Monitor Metrics toolset enables HolmesGPT to query Azure Monitor managed Prometheus metrics for AKS cluster analysis and troubleshooting. This toolset is designed to work from external environments (such as local development machines, CI/CD pipelines, or management servers) and connects to AKS clusters remotely via Azure APIs, providing filtered access to cluster-specific metrics.

## Key Features

- **Automatic AKS Detection**: Auto-discovers AKS cluster context and Azure resource ID
- **Azure Monitor Integration**: Seamlessly connects to Azure Monitor managed Prometheus
- **Cluster-Specific Filtering**: Automatically filters all queries by cluster name to ensure relevant results
- **PromQL Support**: Execute both instant and range queries using standard PromQL syntax
- **Secure Authentication**: Uses Azure DefaultAzureCredential for secure, credential-free authentication in AKS

## Prerequisites

### 1. AKS Cluster with Azure Monitor managed Prometheus

Your AKS cluster must have Azure Monitor managed Prometheus enabled. This can be configured during cluster creation or added to existing clusters.

**Enable via Azure CLI:**
```bash
az aks update \
  --resource-group myResourceGroup \
  --name myAKSCluster \
  --enable-azure-monitor-metrics \
  --azure-monitor-workspace-resource-id /subscriptions/{subscription-id}/resourceGroups/myResourceGroup/providers/microsoft.monitor/accounts/myAzureMonitorWorkspace
```

### 2. Azure Credentials

When running inside AKS, the toolset uses Managed Identity automatically. For local development or CI/CD, ensure Azure credentials are configured via Azure CLI, environment variables, or other supported methods.

### 3. Required Permissions

- **Reader** role on the AKS cluster resource
- **Reader** role on the Azure Monitor workspace  
- **Monitoring Reader** role for querying metrics
- Access to execute Azure Resource Graph queries

## Available Tools

### `check_aks_cluster_context`
Verifies if the current environment is running inside an AKS cluster.

**Usage:**
```bash
holmes ask "Am I running in an AKS cluster?"
```

### `get_aks_cluster_resource_id`
Retrieves the full Azure resource ID of the current AKS cluster.

**Usage:**
```bash
holmes ask "What is the Azure resource ID of this cluster?"
```

### `check_azure_monitor_prometheus_enabled`
Checks if Azure Monitor managed Prometheus is enabled for the AKS cluster and retrieves workspace details.

**Parameters:**
- `cluster_resource_id` (optional): Azure resource ID of the AKS cluster

**Usage:**
```bash
holmes ask "Is Azure Monitor managed Prometheus enabled for this cluster?"
```

### `execute_azuremonitor_prometheus_query`
Executes instant PromQL queries against the Azure Monitor workspace.

**Parameters:**
- `query` (required): The PromQL query to execute
- `description` (required): Description of what the query analyzes
- `auto_cluster_filter` (optional): Enable/disable automatic cluster filtering (default: true)

**Usage:**
```bash
holmes ask "Query current CPU usage across all pods using Azure Monitor metrics"
```

### `execute_azuremonitor_prometheus_range_query`
Executes range PromQL queries for time-series data analysis.

**Parameters:**
- `query` (required): The PromQL query to execute
- `description` (required): Description of what the query analyzes  
- `start` (optional): Start time for the query range
- `end` (optional): End time for the query range
- `step` (required): Query resolution step width
- `output_type` (required): How to interpret results (Plain, Bytes, Percentage, CPUUsage)
- `auto_cluster_filter` (optional): Enable/disable automatic cluster filtering (default: true)

**Usage:**
```bash
holmes ask "Show CPU usage trends over the last hour using Azure Monitor metrics"
```

## Configuration

### Automatic Configuration

The toolset can attempt to auto-discover AKS clusters using Azure credentials:

```yaml
# ~/.holmes/config.yaml
toolsets:
  azuremonitor-metrics:
    auto_detect_cluster: true  # Attempts auto-discovery
    cache_duration_seconds: 1800  # 30 minutes
```

### Manual Configuration (Recommended)

For reliable operation and explicit cluster targeting:

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

## Common Use Cases

### Resource Monitoring

Query resource utilization metrics:

```bash
holmes ask "Show current memory usage for all pods in this cluster"
holmes ask "Which nodes have high CPU utilization?"
holmes ask "Are there any pods with memory issues?"
```

### Application Health

Monitor application-specific metrics:

```bash
holmes ask "Check pod restart counts in the last hour"
holmes ask "Show deployment replica status"
holmes ask "Are there any failed pods?"
```

### Infrastructure Analysis

Analyze cluster infrastructure:

```bash
holmes ask "Check node status and conditions"
holmes ask "Show filesystem usage across nodes"
holmes ask "Monitor network traffic patterns"
```

### Troubleshooting

Use for specific troubleshooting scenarios:

```bash
holmes ask "Investigate high CPU usage in the frontend namespace"
holmes ask "Check for resource constraints causing pod evictions"
holmes ask "Analyze performance during the last deployment"
```

## Automatic Cluster Filtering

All PromQL queries are automatically enhanced with cluster-specific filtering:

**Original Query:**
```promql
container_cpu_usage_seconds_total
```

**Enhanced Query:**
```promql
container_cpu_usage_seconds_total{cluster="my-cluster-name"}
```

This ensures queries only return metrics for the current AKS cluster, avoiding confusion when multiple clusters send metrics to the same Azure Monitor workspace.

## Common Metrics for AKS

The toolset works with standard Prometheus metrics available in Azure Monitor:

- `container_cpu_usage_seconds_total` - CPU usage by containers
- `container_memory_working_set_bytes` - Memory usage by containers
- `kube_pod_status_phase` - Pod status information
- `kube_node_status_condition` - Node health status
- `container_fs_usage_bytes` - Filesystem usage
- `kube_deployment_status_replicas` - Deployment replica status
- `container_network_receive_bytes_total` - Network ingress
- `container_network_transmit_bytes_total` - Network egress

## Troubleshooting

### "No AKS cluster specified"
- Provide cluster_resource_id parameter in queries
- Configure cluster details in config.yaml file
- Ensure Azure credentials have access to the target cluster
- See AZURE_MONITOR_SETUP_GUIDE.md for detailed configuration instructions

### "Azure Monitor managed Prometheus is not enabled"
- Enable managed Prometheus in Azure portal or via CLI
- Verify data collection rule configuration
- Ensure cluster is associated with Azure Monitor workspace

### "Query returned no results"
- Verify the metric exists in your cluster
- Check if cluster filtering is too restrictive
- Try disabling auto-cluster filtering temporarily

### Authentication Issues
- Verify Azure credentials are properly configured
- Check required permissions on cluster and workspace
- Ensure Managed Identity is enabled for in-cluster execution

## Security Considerations

- Uses Azure Managed Identity when running in AKS for secure, keyless authentication
- Respects Azure RBAC permissions and access controls
- Read-only access to metrics data
- All queries are automatically scoped to the current cluster

## Best Practices

1. **Use Descriptive Queries**: Always provide meaningful descriptions for your PromQL queries
2. **Leverage Auto-Detection**: Let the toolset auto-discover cluster configuration when possible
3. **Time Range Awareness**: Use appropriate time ranges for range queries based on investigation needs
4. **Resource Scope**: Take advantage of automatic cluster filtering to focus on relevant metrics
5. **Error Handling**: Check toolset status before executing queries to ensure proper setup

## Integration with Other Toolsets

The Azure Monitor Metrics toolset complements other HolmesGPT toolsets:

- **Kubernetes Toolset**: Combine metrics with pod logs and events
- **Bash Toolset**: Use kubectl commands alongside metric queries
- **Internet Toolset**: Research metric meanings and troubleshooting approaches

## Example Investigation Workflow

1. **Setup Verification:**
   ```bash
   holmes ask "Check if Azure Monitor metrics toolset is available"
   ```

2. **Environment Discovery:**
   ```bash
   holmes ask "Am I running in an AKS cluster and is Azure Monitor enabled?"
   ```

3. **Health Overview:**
   ```bash
   holmes ask "Show overall cluster health metrics"
   ```

4. **Specific Investigation:**
   ```bash
   holmes ask "Investigate high CPU usage in the production namespace over the last 2 hours"
   ```

5. **Root Cause Analysis:**
   ```bash
   holmes ask "Correlate CPU spikes with pod restart events"
   ```

This workflow leverages the toolset's automatic setup and cluster filtering to provide focused, relevant insights for AKS troubleshooting scenarios.
