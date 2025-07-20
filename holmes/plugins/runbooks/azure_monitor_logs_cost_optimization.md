# Azure Monitor Container Insights Cost Optimization - Analysis Runbook

## Goal

**ALWAYS EXECUTE LIVE ANALYSIS**: When asked about Container Insights cost optimization, IMMEDIATELY run KQL queries using azure mcp server tool to analyze the actual cluster. Do NOT provide generic recommendations - ALWAYS execute the 5 KQL queries below to get real cost data and specific USD savings calculations.

**MANDATORY EXECUTION**: This runbook requires active query execution, not passive reference. Execute all queries to provide cluster-specific cost optimization with actual data.

---

## Analysis Workflow

**EXECUTE IMMEDIATELY** - Do not provide theoretical recommendations:

* **STEP 1**: Use azuremonitorlogs toolset to detect Log Analytics workspace and cluster resource ID
* **STEP 1B**: Use azuremonitormetrics toolset to check if Azure Monitor Metrics (managed Prometheus) is enabled
* **STEP 2**: IMMEDIATELY after detecting workspace, use azure mcp server tool to execute ALL 5 KQL cost analysis queries against the detected workspace
* **STEP 3**: Replace `{CLUSTER_RESOURCE_ID}` in all queries with the actual cluster resource ID from azuremonitorlogs
* **STEP 4**: Calculate specific USD savings based on query results and provide competitive analysis
* **STEP 5**: If Azure Monitor Metrics is NOT enabled, include high-priority recommendation to enable it for 80% metrics cost savings

**MANDATORY**: Always execute queries when asked about Container Insights cost optimization - never provide generic advice without running queries first.

**CRITICAL**: If you detect workspace ID and cluster resource ID, DO NOT STOP - proceed immediately to execute KQL queries using azure mcp server tool. Do not ask for permission or provide "next steps" - execute the queries now.

**MANDATORY REPORT FORMAT**: After executing all queries, you MUST generate the complete executive report exactly as shown in the Executive Report Template section below. Use the exact format with tables, competitive analysis, and structured sections. Do NOT provide brief bullet points or summaries - ALWAYS generate the full structured report with all sections.

**CRITICAL TIMESTAMP REQUIREMENT**: When generating the report, you MUST replace `{CURRENT_UTC_TIMESTAMP}` with the actual current UTC timestamp in ISO 8601 format (e.g., 2025-07-20T17:16:00Z). DO NOT use any hardcoded or old dates - always use the current date and time.

**REQUIRED SECTIONS**: Your response MUST include:
1. Complete header with "🤖 AI-GENERATED AZURE MONITOR LOGS COST OPTIMIZATION REPORT"
2. Cost Overview table with Current/Optimized/Savings columns
3. Competitive Analysis table comparing Azure vs all competitors
4. Action Items with specific USD savings amounts
5. Total Potential Savings calculation

**DUAL OUTPUT REQUIREMENT**: After executing all queries, you MUST:
1. **DISPLAY the complete executive report** in the console using the exact format from the Executive Report Template
2. **IMMEDIATELY call generate_cost_optimization_pdf** tool to create a PDF file with the same report content

**CRITICAL**: Do NOT skip displaying the full report in the console. Users must see both the complete report on screen AND receive the PDF download link.

### Tool Usage Requirements

1. **azuremonitorlogs toolset**: Detect workspace ID, cluster resource ID, and current configuration
2. **azure mcp server tool**: Execute cost analysis queries using "monitor workspace log query" tool
3. **Usage table access**: Use workspace-level Usage analysis (no cluster filtering needed)
4. **Schema information**: Use correct column names - PodNamespace (not Namespace), LogMessage (not LogEntry), LogLevel (has level info)
5. **Tool parameters**: 
   - **--subscription**: Parse from workspace resource ID
   - **--workspace**: Use detected workspace GUID
   - **--table-name**: Usage, ContainerLogV2, etc.
   - **--query**: Individual KQL queries per table

**Important**: The Usage table IS accessible through azure mcp server tool. Do not skip Usage table queries - they are required for cost analysis.

**Usage Table Filtering**: The Usage table does NOT have _ResourceId column. Use workspace-level analysis for Usage queries.

**Data Tables Schema**: _ResourceId is a hidden column that does NOT appear in schema discovery but EXISTS in every data table (ContainerLogV2, Perf, InsightsMetrics, etc.) EXCEPT Usage table. This is normal Azure Monitor behavior - the column is invisible in schema but is ALWAYS usable in queries for filtering.

**Tool Execution Pattern**: 
- **Usage table**: Execute workspace-level queries using --table-name Usage
- **ContainerLogV2**: Execute cluster-specific queries with _ResourceId filtering
- **Each query**: Separate tool call per table with appropriate KQL query

---

## Cost Analysis Metrics and Queries

### 1. Overall Usage and Cost Assessment

**Step 1 - Find Cluster Data Types** - Execute using azure mcp server with any table name (e.g., --table-name ContainerLogV2):
```kql
find where TimeGenerated > ago(24h) and _ResourceId == "{CLUSTER_RESOURCE_ID}"
| summarize count() by Type
```

**Step 2 - Get Usage for Those Types** - Execute using azure mcp server with --table-name Usage:
```kql
Usage
| where TimeGenerated > ago(24h)
| where DataType in ("ContainerLogV2", "KubePodInventory", "Perf", "InsightsMetrics", "KubeEvents")
| summarize 
    TotalGB = sum(Quantity) / 1024,
    DailyCostUSD = sum(Quantity) / 1024 * 0.50
by DataType
| extend 
    MonthlyCostUSD = DailyCostUSD * 30,
    OptimizationPotential = case(
        DataType in ("Perf", "InsightsMetrics"), "HIGH: Move to Prometheus (80% savings)",
        DataType == "KubePodInventory", "MEDIUM: Eliminate with ContainerLogV2",
        DataType == "ContainerLog", "MEDIUM: Migrate to ContainerLogV2",
        "LOW: Keep essential logs"
    )
| order by TotalGB desc
```

### 2. Metrics-as-Logs Cost Analysis

**Metrics Usage Query** - Execute via azure mcp server tool with --table-name Usage:
```kql
Usage
| where TimeGenerated > ago(24h)
| where DataType in ("Perf", "InsightsMetrics")
| summarize 
    MetricsAsLogsGB = sum(Quantity) / 1024,
    CurrentMonthlyCostUSD = sum(Quantity) / 1024 * 0.50 * 30
| extend 
    PrometheusEquivalentCostUSD = CurrentMonthlyCostUSD * 0.20,
    MonthlySavingsUSD = CurrentMonthlyCostUSD * 0.80,
    SavingsPercentage = 80.0
| project MetricsAsLogsGB, CurrentMonthlyCostUSD, PrometheusEquivalentCostUSD, MonthlySavingsUSD, SavingsPercentage
```

### 3. Namespace Volume Analysis  

**Namespace Filtering Query** - Identify high-volume namespaces for exclusion:
```kql
ContainerLogV2
| where TimeGenerated > ago(24h)
| where _ResourceId == "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeGB = sum(estimate_data_size(*)) / 1024/1024/1024,
    DailyCostUSD = sum(estimate_data_size(*)) / 1024/1024/1024 * 0.10
by PodNamespace
| extend MonthlyCostUSD = DailyCostUSD * 30
| extend FilteringRecommendation = case(
    PodNamespace in ("kube-system", "gatekeeper-system", "azure-system", "calico-system"), 
    strcat("HIGH PRIORITY: Filter out - Save $", round(MonthlyCostUSD, 2), "/month"),
    SizeGB > 1.0, 
    strcat("MEDIUM: High volume (", round(SizeGB, 1), " GB/day) - Consider filtering"),
    "LOW: Keep - Low volume"
)
| order by SizeGB desc
```

### 4. Log Level Distribution Analysis

**Log Level Query** - Identify debug/info logs for filtering:
```kql
ContainerLogV2
| where TimeGenerated > ago(24h)
| where _ResourceId == "{CLUSTER_RESOURCE_ID}"
| extend LogLevelParsed = case(
    LogLevel == "Info", "INFO",
    LogLevel == "Debug", "DEBUG", 
    LogLevel == "Warning", "WARN",
    LogLevel == "Error", "ERROR",
    LogMessage has_any ("ERROR", "FATAL", "CRITICAL"), "ERROR",
    LogMessage has_any ("WARN", "WARNING"), "WARN",
    LogMessage has_any ("INFO"), "INFO", 
    LogMessage has_any ("DEBUG", "TRACE"), "DEBUG",
    "OTHER"
)
| summarize 
    SizeGB = sum(estimate_data_size(*)) / 1024/1024/1024,
    DailyCostUSD = sum(estimate_data_size(*)) / 1024/1024/1024 * 0.10
by LogLevelParsed
| extend MonthlyCostUSD = DailyCostUSD * 30
| extend PotentialSavingsUSD = case(
    LogLevelParsed in ("DEBUG", "TRACE"), MonthlyCostUSD,
    LogLevelParsed == "INFO", MonthlyCostUSD * 0.5,
    0.0
)
| order by SizeGB desc
```

### 5. Container Volume Analysis

**Container Volume Query** - Identify high-volume containers:
```kql
ContainerLogV2
| where TimeGenerated > ago(24h)
| where _ResourceId == "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeGB = sum(estimate_data_size(*)) / 1024/1024/1024
by ContainerName, PodNamespace
| extend MonthlyCostUSD = SizeGB * 0.10 * 30
| order by SizeGB desc
| take 20
```

---

## Cost Optimization Opportunities

### Primary Optimization Targets

| **Data Type** | **Typical Cost Impact** | **Optimization Strategy** | **Expected Savings** |
|---------------|------------------------|---------------------------|---------------------|
| **Perf, InsightsMetrics** | High ($50-200/month) | Migrate to Managed Prometheus | 80% cost reduction |
| **ContainerLog** | Medium ($20-100/month) | Migrate to ContainerLogV2 | 20-30% reduction |
| **KubePodInventory** | Medium ($10-50/month) | Eliminate with ContainerLogV2 | 100% elimination |
| **System Namespaces** | Variable ($5-50/month) | ConfigMap exclusion | 100% elimination |
| **Debug/Info Logs** | Variable ($10-30/month) | Log level filtering | 50-100% reduction |

### Azure Monitor Metrics (Managed Prometheus) Detection

**CRITICAL CHECK**: Use azuremonitormetrics toolset to detect if Azure Monitor Metrics is enabled.

**If Azure Monitor Metrics is NOT enabled:**
- **HIGH PRIORITY RECOMMENDATION**: Enable Azure Monitor Metrics (Managed Prometheus) 
- **Immediate benefit**: 80% cost reduction for all performance metrics
- **Replace**: Perf and InsightsMetrics data streams with efficient Prometheus metrics
- **Cost impact**: Can save $40-160/month for typical clusters
- **Implementation**: 5-minute setup via Azure portal or CLI

**Enable Azure Monitor Metrics Command:**
```bash
az aks update --resource-group <resource-group> --name <cluster-name> --enable-azure-monitor-metrics
```

**Verification**: Check azuremonitormetrics toolset confirms successful enablement.

### Architecture Optimization Strategy

**Optimal Configuration:**
- ✅ Azure Monitor Metrics (Managed Prometheus): ALL performance metrics
- ✅ ContainerLogV2: Container stdout/stderr logs + Kubernetes events  
- ❌ Remove: Perf, InsightsMetrics, KubePodInventory tables
- ❌ Filter: System namespaces (kube-system, gatekeeper-system, etc.)

---

## Competitive Cost Analysis

### Post-Optimization Pricing Comparison

Calculate costs using optimized volume and compare against competitors:

| **Platform** | **Pricing Model** | **Calculation** |
|--------------|------------------|-----------------|
| **Azure Monitor (Optimized)** | $0.10/GB Basic Logs + Prometheus | Baseline cost |
| **Amazon CloudWatch** | $0.50/GB Logs + Metrics | 5x higher logs cost |
| **Google Cloud Logging** | $0.50/GB + Monitoring | 5x higher logs cost |
| **Datadog** | $1.27/GB + Infrastructure | 12x higher cost |
| **New Relic** | $0.30/GB + Platform | 3x higher cost |
| **Oracle OCI** | $0.30/GB + Monitoring | 3x higher cost |

---

## Implementation Recommendations

### Cost-Optimized ConfigMap Template

Deploy this ConfigMap to implement filtering and schema optimization:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: container-azm-ms-agentconfig
  namespace: kube-system
data:
  schema-version: v1
  config-version: ver1
  log-data-collection-settings: |-
    [log_collection_settings]
       [log_collection_settings.stdout]
          enabled = true
          exclude_namespaces = ["kube-system", "gatekeeper-system", "azure-system", "calico-system"]
       [log_collection_settings.stderr]
          enabled = true
          exclude_namespaces = ["kube-system", "gatekeeper-system", "azure-system"]
       [log_collection_settings.schema]
          containerlog_schema_version = "v2"
    [metric_collection_settings]
       [metric_collection_settings.collect_kube_system_metrics]
          enabled = false
```

### Implementation Priority

| **Priority** | **Action** | **Expected Savings** | **Implementation Time** |
|--------------|------------|---------------------|------------------------|
| **P1** | Enable Azure Monitor Metrics | 80% metrics cost | 5 minutes |
| **P2** | Deploy ConfigMap optimization | 30-50% log volume | 10 minutes |
| **P3** | Monitor and validate | Confirm savings | 24-48 hours |

---

## Executive Report Template

### Analysis Results Format

Present findings using this structure:

```
🤖 AI-GENERATED AZURE MONITOR LOGS COST OPTIMIZATION REPORT
📅 Analysis Date: {CURRENT_UTC_TIMESTAMP}

## 📊 COST OVERVIEW
| Metric | Current | Optimized | Savings | Status |
|--------|---------|-----------|---------|--------|
| Monthly Volume | {current_GB} GB | {optimized_GB} GB | {savings_GB} GB | High Volume |
| Monthly Cost | ${current_cost} USD | ${optimized_cost} USD | ${savings_cost} USD | Expensive |

## 🏆 COMPETITIVE ANALYSIS (After Optimization)
| Platform | Monthly Cost | vs Azure | Cost Difference |
|----------|--------------|----------|-----------------|
| Azure Monitor (Optimized) | ${azure_cost} | - | Baseline |
| Amazon CloudWatch | ${aws_cost} | +{aws_percent}% | +${aws_diff} |
| Google Cloud Logging | ${gcp_cost} | +{gcp_percent}% | +${gcp_diff} |
| Datadog | ${dd_cost} | +{dd_percent}% | +${dd_diff} |

## 💡 ACTION ITEMS
1. Enable Azure Monitor Metrics: ${metrics_savings}/month savings
2. Deploy optimized ConfigMap: ${configmap_savings}/month savings  
3. Monitor results after 24-48 hours

Total Potential Savings: ${total_savings} USD/month
```

---

## Data Sources and Documentation

### Required Tools Integration
- **azuremonitorlogs**: Workspace and cluster resource ID detection
- **azuremonitormetrics**: Prometheus configuration detection  
- **azure mcp server**: KQL query execution against Log Analytics
- **kubectl**: ConfigMap analysis and deployment

### Reference Documentation
- Container Insights Configuration: https://learn.microsoft.com/en-us/azure/azure-monitor/containers/container-insights-data-collection-configure
- Azure Monitor Metrics: https://learn.microsoft.com/en-us/azure/azure-monitor/containers/prometheus-metrics-enable
- Basic Logs Tier: https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-table-plans

---

## Analysis Disclaimers

**🤖 AI-Generated Analysis**: This cost optimization analysis is generated by HolmesGPT AI. All recommendations should be independently verified by Azure specialists before implementation.

**📊 Data Limitations**: Analysis based on 24-hour samples extrapolated to monthly estimates using generic Azure Monitor pricing. Actual costs may vary by region and enterprise agreements.

**⚠️ Verification Required**: Test all changes in non-production environments first. Monitor actual costs after implementation to validate estimates.
