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

### 2. Azure Credentials and Subscription Context

**Critical Requirements:**
1. **Azure CLI** - Logged in with `az login`
2. **Correct Subscription Context** - Azure CLI must be set to the same subscription as your AKS cluster
3. **kubectl** - Connected to your AKS cluster

When running inside AKS, the toolset uses Managed Identity automatically. For external environments (local development, CI/CD), ensure Azure credentials are properly configured and the subscription context is correct.

**Verification Commands:**
```bash
# Check Azure CLI login status
az account show

# Verify current subscription matches your AKS cluster
az account list --output table

# Set correct subscription if needed
az account set --subscription <cluster-subscription-id>

# Verify kubectl context
kubectl config current-context
```

**Why This Matters:**
The toolset uses Azure CLI to discover cluster resource IDs and must search within the correct subscription context. If your Azure CLI is set to a different subscription than your AKS cluster, auto-detection will fail.

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

### `get_active_prometheus_alerts`
Retrieves active/fired Prometheus metric alerts for the AKS cluster.

**Parameters:**
- `cluster_resource_id` (optional): Azure resource ID of the AKS cluster
- `alert_id` (optional): Specific alert ID to investigate

**Usage:**
```bash
holmes ask "Show all active Prometheus alerts for this cluster"
holmes ask "Get details for alert ID /subscriptions/.../alerts/12345"
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
    tool_calls_return_data: true
    # Optional: Query performance tuning
    default_step_seconds: 3600    # Default step size for range queries (1 hour)
    min_step_seconds: 60          # Minimum allowed step size (1 minute)
    max_data_points: 1000         # Maximum data points per query
```

### Configuration Options Explained

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `azure_monitor_workspace_endpoint` | string | None | Full URL to your Azure Monitor workspace Prometheus endpoint |
| `cluster_name` | string | None | Name of your AKS cluster (used for query filtering) |
| `cluster_resource_id` | string | None | Full Azure resource ID of your AKS cluster |
| `auto_detect_cluster` | boolean | true | Enable automatic cluster detection via kubectl/Azure CLI |
| `tool_calls_return_data` | boolean | true | Include raw Prometheus data in tool responses |
| `default_step_seconds` | integer | 3600 | Default step size for range queries (in seconds) |
| `min_step_seconds` | integer | 60 | Minimum allowed step size to prevent excessive data points |
| `max_data_points` | integer | 1000 | Maximum data points per query to prevent token limit issues |

#### Query Performance Tuning

The step size configuration helps manage query performance and token limits:

- **`default_step_seconds`**: Used when no step is specified in range queries. 1 hour (3600s) provides good balance between detail and performance.
- **`min_step_seconds`**: Prevents overly granular queries that could return excessive data points and hit token limits.
- **`max_data_points`**: Automatically adjusts step size if a query would return too many data points.

**Example scenarios:**
- **24-hour query with default 1-hour step**: Returns ~24 data points
- **24-hour query with 1-minute step**: Would return 1440 points, gets auto-adjusted to stay under `max_data_points`
- **1-hour query with 30-second step**: Gets adjusted to `min_step_seconds` (60s) minimum

## Alert Investigation

Holmes supports investigating Azure Monitor Prometheus metric alerts with a two-step workflow for better control and focused analysis.

### Step 1: List Active Alerts

First, get a list of all active alerts to see what's currently firing:

```bash
holmes ask "show me all active azure monitor metric alerts"
```

This will display all active alerts with beautiful formatting, icons, and their full alert IDs, allowing you to select which specific alert to investigate.

### Step 2: Investigate Specific Alert

Investigate a specific alert by providing its full alert ID:

```bash
holmes investigate azuremonitormetrics /subscriptions/12345/providers/Microsoft.AlertsManagement/alerts/abcd-1234
```

This targeted approach allows you to:
1. See all available alerts at once with enhanced visual formatting
2. Choose which alert is most critical to investigate
3. Get focused AI-powered root cause analysis for the selected alert

### Alert Information Displayed

For each alert, Holmes shows with beautiful formatting and icons:
- **🔔 Alert Header**: Cluster name with visual indicator
- **📋 Alert ID**: Full Azure resource ID in code blocks for easy copying
- **🔬 Alert Type**: "Prometheus Metric Alert" for clear identification
- **⚡ Query**: The Prometheus metric query that triggered the alert
- **📝 Description**: Alert description and configuration
- **🎯 Status Line**: Severity, status, and fired time in one organized line
- **Visual Indicators**: Color-coded severity icons (🔴🟠🟡🔵) and status icons (🚨👁️✅)

### Example Output

```
🔔 **Active Prometheus Alerts for Cluster: my-cluster**

💡 **How to investigate:** Copy an Alert ID and run:
   `holmes investigate azuremonitormetrics <ALERT_ID>`

────────────────────────────────────────────────────────────────────────────────

**1. 🔴 High CPU Usage** 🚨
   📋 **Alert ID:** `/subscriptions/.../alerts/12345`
   🔬 **Type:** Prometheus Metric Alert
   ⚡ **Query:** `container_cpu_usage_seconds_total`
   📝 **Description:** Container CPU usage above 80%
   🎯 **Severity:** Critical | **State:** New | **Condition:** Fired
   🕒 **Fired Time:** 2025-01-15 17:30 UTC

**2. 🟡 Memory Pressure** 🚨
   📋 **Alert ID:** `/subscriptions/.../alerts/67890`
   🔬 **Type:** Prometheus Metric Alert
   ⚡ **Query:** `container_memory_working_set_bytes`
   📝 **Description:** Container memory usage above 90%
   🎯 **Severity:** Warning | **State:** New | **Condition:** Fired
   🕒 **Fired Time:** 2025-01-15 17:25 UTC
```

### Visual Elements

The alert listing includes professional visual elements:
- **🔔** Header with cluster identification
- **💡** Clear instructions for next steps
- **📋** Code blocks for easy Alert ID copying
- **🔬** Alert type identification
- **⚡** Query information for troubleshooting
- **🎯** Organized metadata display
- **Severity Icons**: 🔴 Critical, 🟠 Error, 🟡 Warning, 🔵 Info
- **Status Icons**: 🚨 New, 👁️ Acknowledged, ✅ Closed

### Common Options

```bash
# Basic investigation (recommended)
holmes investigate azuremonitormetrics /subscriptions/.../alerts/12345

# Save results to JSON file
holmes investigate azuremonitormetrics /subscriptions/.../alerts/12345 --json-output-file alert-analysis.json

# Verbose output for debugging
holmes investigate azuremonitormetrics /subscriptions/.../alerts/12345 --verbose
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

## Diagnostic Runbooks

The Azure Monitor toolset includes comprehensive diagnostic runbooks that enhance the LLM's investigation capabilities. These runbooks provide systematic, step-by-step guidance for analyzing Azure Monitor alerts.

### How Runbooks Work

When investigating Azure Monitor alerts using `holmes investigate azuremonitormetrics <ALERT_ID>`, the runbooks automatically:

1. **Guide the LLM** through systematic diagnostic steps
2. **Ensure comprehensive coverage** of all relevant investigation areas
3. **Provide structured methodology** for root cause analysis
4. **Suggest appropriate tool usage** for each diagnostic step

### Available Runbooks

#### Generic Azure Monitor Runbook

A comprehensive diagnostic runbook that applies to all Azure Monitor alerts:

```yaml
runbooks:
  - match:
      source_type: "azuremonitoralerts"
    instructions: >
      10-step systematic diagnostic approach covering:
      - Alert context analysis
      - Current state assessment
      - Resource investigation
      - Metric correlation and trends
      - Event timeline analysis
      - Log analysis
      - Dependency analysis
      - Root cause hypothesis
      - Impact assessment
      - Remediation recommendations
```

#### Specialized Runbooks

**High CPU Usage Alerts:**
- Focuses on CPU-specific metrics and throttling
- Analyzes application performance patterns
- Provides scaling and capacity recommendations

**Memory-Related Alerts:**
- Emphasizes memory leak detection
- Checks for OOM conditions
- Analyzes memory pressure impacts

**Pod Waiting State Alerts:**
- Focuses on pod lifecycle and scheduling issues
- Checks resource availability and constraints
- Analyzes image and configuration problems

### Configuring Runbooks

#### Built-in Runbooks (Automatic)

Azure Monitor diagnostic runbooks are **built into Holmes** and work automatically without any configuration:

```bash
# Runbooks are automatically active - no setup required!
holmes investigate azuremonitormetrics <ALERT_ID>
```

#### Optional: Using the Example Configuration

For additional customization, you can also copy the provided example configuration:

```bash
# Copy the example runbook configuration for customization
cp examples/azuremonitor_runbooks.yaml ~/.holmes/runbooks.yaml

# Or merge with existing runbooks
cat examples/azuremonitor_runbooks.yaml >> ~/.holmes/runbooks.yaml
```

#### Custom Runbooks

Create custom runbooks for your specific environment:

```yaml
runbooks:
  - match:
      issue_name: ".*MyApplication.*"
      source_type: "azuremonitoralerts"
    instructions: >
      Custom diagnostic steps for MyApplication alerts:
      1. Check application-specific metrics
      2. Verify database connectivity
      3. Analyze custom logs in /app/logs
      4. Check integration with external services
```

#### Configuration Location

Runbooks can be configured in:
- `~/.holmes/runbooks.yaml` (user-specific)
- `./runbooks.yaml` (project-specific)
- Via `--runbooks-file` command line option

### Runbook Matching

Runbooks are matched based on:
- **source_type**: "azuremonitoralerts" for all Azure Monitor alerts
- **issue_name**: Pattern matching against alert names
- **Custom criteria**: Additional matching rules as needed

**Priority:** More specific runbooks take precedence over generic ones.

### Benefits

**Enhanced Investigation Quality:**
- Systematic approach ensures nothing is missed
- Consistent methodology across all alerts
- Leverages best practices for each alert type

**Improved Efficiency:**
- Faster time to resolution
- Reduced investigation overhead
- Clear next steps and recommendations

**Knowledge Sharing:**
- Codifies expert knowledge in runbooks
- Consistent investigation approach across teams
- Easy to customize for specific environments

### Example Usage

```bash
# Investigate with automatic runbook guidance
holmes investigate azuremonitormetrics /subscriptions/.../alerts/12345

# The LLM will automatically:
# 1. Load the appropriate runbook
# 2. Follow systematic diagnostic steps
# 3. Use suggested tools and queries
# 4. Provide structured analysis and recommendations
```

### Customization Examples

**Team-Specific Runbooks:**
```yaml
runbooks:
  - match:
      issue_name: ".*frontend.*"
      source_type: "azuremonitoralerts"
    instructions: >
      Frontend application alert investigation:
      - Check CDN and load balancer metrics
      - Analyze user experience metrics
      - Verify API gateway connectivity
      - Check browser error rates
```

**Environment-Specific Runbooks:**
```yaml
runbooks:
  - match:
      issue_name: ".*production.*"
      source_type: "azuremonitoralerts"
    instructions: >
      Production alert investigation (high priority):
      - Immediate impact assessment
      - Escalation to on-call team if severe
      - Check business metrics and SLAs
      - Prepare incident communication
```

This runbook system transforms Azure Monitor alert investigation from ad-hoc analysis to systematic, comprehensive diagnostics guided by proven methodologies.
