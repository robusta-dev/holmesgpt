# Azure Monitor Container Insights Cost Optimization - Analysis Runbook

## Goal

**ALWAYS EXECUTE LIVE ANALYSIS**: When asked about Container Insights cost optimization, IMMEDIATELY run KQL queries using azure mcp server tool to analyze the actual cluster. Do NOT provide generic recommendations - ALWAYS execute the 7 KQL query sets below to get real cost data and specific USD savings calculations.

**MANDATORY DUAL TABLE ANALYSIS**: This runbook MUST analyze BOTH ContainerLog (v1) AND ContainerLogV2 volumes/costs separately, then recommend migrating from ContainerLog to ContainerLogV2 to unlock Basic Logs tier optimization and kubernetes metadata collection (these optimizations ONLY work with ContainerLogV2).

**MANDATORY EXECUTION**: This runbook requires active query execution, not passive reference. Execute all queries to provide cluster-specific cost optimization with actual data.

---

## Analysis Workflow

**EXECUTE IMMEDIATELY** - Do not provide theoretical recommendations:

* **STEP 1**: Use azuremonitorlogs toolset to detect Log Analytics workspace and cluster resource ID
  - If workspace/cluster not immediately detectable, use `check_aks_cluster_context` to get current cluster
  - If resource group needed, use `get_aks_cluster_resource_id` with available cluster names
* **STEP 1B**: **CRITICAL - Parse Resource Group**: Extract resource group from workspace resource ID
  - Parse format: `/subscriptions/{sub}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.OperationalInsights/workspaces/{name}`
  - Extract the resource group name from the workspace resource ID for azure mcp server tool calls
* **STEP 1C**: Use azuremonitormetrics toolset to check if Azure Monitor Metrics (managed Prometheus) is enabled
* **STEP 2**: IMMEDIATELY after detecting workspace and parsing resource group, use azure mcp server tool to execute ALL 7 KQL cost analysis query sets against the detected workspace
* **STEP 3**: Replace `{CLUSTER_RESOURCE_ID}` in all queries with the actual cluster resource ID from azuremonitorlogs
* **STEP 4**: **MANDATORY DUAL ANALYSIS**: Execute BOTH ContainerLog (v1) AND ContainerLogV2 queries to compare volumes and costs
* **STEP 5**: **CRITICAL MIGRATION RECOMMENDATION**: If ContainerLog (v1) data exists, ALWAYS recommend migration to ContainerLogV2 to unlock Basic Logs tier + kubernetes metadata optimizations
* **STEP 6**: Calculate specific USD savings based on query results and provide competitive analysis
* **STEP 7**: Check Azure Monitor Metrics status and conditionally recommend enablement only if NOT already enabled
* **STEP 8**: **ALWAYS GENERATE COMPLETE EXECUTIVE REPORT** using the template below, even if some queries fail - provide available analysis and note missing data

**MANDATORY**: Always execute queries when asked about Container Insights cost optimization - never provide generic advice without running queries first.

**PROACTIVE DETECTION**: When asked about Container Insights cost optimization, IMMEDIATELY attempt to detect workspace and cluster information using available tools. Do NOT ask user for resource group names - try to discover them first.

**CRITICAL**: If you detect workspace ID and cluster resource ID, DO NOT STOP - proceed immediately to execute KQL queries using azure mcp server tool. Do not ask for permission or provide "next steps" - execute the queries now.

**FALLBACK STRATEGY**: If workspace detection fails, provide a comprehensive cost optimization analysis template with typical savings estimates and clear implementation guidance, noting that actual analysis requires workspace access.

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
2. **Resource group parsing**: Extract resource group from workspace resource ID format: `/subscriptions/{sub}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.OperationalInsights/workspaces/{name}`
3. **azure mcp server tool**: Execute cost analysis queries using "monitor workspace log query" tool
4. **Usage table access**: Use workspace-level Usage analysis (no cluster filtering needed)
5. **Schema information**: Use correct column names - PodNamespace (not Namespace), LogMessage (not LogEntry), LogLevel (has level info)
6. **Tool parameters**: 
   - **--subscription**: Parse from workspace resource ID
   - **--resource-group**: REQUIRED - Parse from workspace resource ID after `/resourceGroups/` and before next `/`
   - **--workspace**: Use detected workspace GUID
   - **--table-name**: Usage, ContainerLogV2, etc.
   - **--query**: Individual KQL queries per table

**CRITICAL**: All azure mcp server tool calls MUST include `--resource-group` parameter to avoid "Missing Required options" errors.

**Important**: The Usage table IS accessible through azure mcp server tool. Do not skip Usage table queries - they are required for cost analysis.

**Usage Table Filtering**: The Usage table does NOT have _ResourceId column. Use workspace-level analysis for Usage queries.

**Data Tables Schema**: _ResourceId is a hidden column that does NOT appear in schema discovery but EXISTS in every data table (ContainerLogV2, Perf, InsightsMetrics, etc.) EXCEPT Usage table. This is normal Azure Monitor behavior - the column is invisible in schema but is ALWAYS usable in queries for filtering.

**Tool Execution Pattern**: 
- **Resource Group Extraction**: Parse from workspace resource ID: `/subscriptions/{sub}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.OperationalInsights/workspaces/{name}`
- **Usage table**: Execute workspace-level queries using --table-name Usage --resource-group {RESOURCE_GROUP}
- **ContainerLogV2**: Execute cluster-specific queries with _ResourceId filtering --resource-group {RESOURCE_GROUP}
- **Each query**: Separate tool call per table with appropriate KQL query and resource group parameter

---

## Cost Analysis Metrics and Queries

### 1. Overall Usage and Cost Assessment

**Step 1 - Find Cluster Data Types** - Execute using azure mcp server with any table name (e.g., --table-name ContainerLogV2):
```kql
find where TimeGenerated > ago(2h) and _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize count() by Type
```

**Step 2 - Get Usage for Those Types** - Execute using azure mcp server with --table-name Usage:
```kql
Usage
| where TimeGenerated > ago(2h)
| where DataType in ("ContainerLog", "ContainerLogV2", "KubePodInventory", "Perf", "InsightsMetrics", "KubeEvents")
| summarize 
    TotalGB = sum(Quantity) / 1024,
    TwoHourCostUSD = sum(Quantity) / 1024 * 2.99
by DataType
| extend 
    DailyCostUSD = TwoHourCostUSD * 12, // 12 x 2-hour periods in 24 hours
    MonthlyCostUSD = TwoHourCostUSD * 12 * 30, // Extrapolate to 30 days
    OptimizationPotential = case(
        DataType in ("Perf", "InsightsMetrics"), "HIGH: Move to Prometheus (80% savings)",
        DataType == "KubePodInventory", "HIGH: Eliminate with ContainerLogV2 metadata collection (85% savings)",
        DataType == "ContainerLog", "HIGH: Migrate to ContainerLogV2 + Basic tier (98% savings)",
        DataType == "ContainerLogV2", "MEDIUM: Move to Basic tier (83% savings)",
        "LOW: Keep essential logs"
    )
| order by TotalGB desc
```

### 2. Metrics-as-Logs Cost Analysis

**Metrics Usage Query** - Execute via azure mcp server tool with --table-name Usage:
```kql
Usage
| where TimeGenerated > ago(2h)
| where DataType in ("Perf", "InsightsMetrics")
| summarize 
    MetricsAsLogsGB = sum(Quantity) / 1024,
    TwoHourCostUSD = sum(Quantity) / 1024 * 2.99,
    CurrentMonthlyCostUSD = sum(Quantity) / 1024 * 2.99 * 12 * 30 // 12 x 2-hour periods per day, 30 days
by DataType
| extend 
    PrometheusEquivalentCostUSD = CurrentMonthlyCostUSD * 0.20,
    MonthlySavingsUSD = CurrentMonthlyCostUSD * 0.80,
    SavingsPercentage = 80.0
| project DataType, MetricsAsLogsGB, CurrentMonthlyCostUSD, PrometheusEquivalentCostUSD, MonthlySavingsUSD, SavingsPercentage
```

### 3. Enhanced ContainerLogV2 Namespace Analysis

**Comprehensive Namespace Query** - Raw analysis of ALL namespaces with actionable recommendations:
```kql
ContainerLogV2
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeBytes = sum(estimate_data_size(*)),
    UniqueContainers = dcount(ContainerName),
    UniquePods = dcount(PodName)
by PodNamespace
| extend 
    SizeGB = SizeBytes / 1024.0 / 1024.0 / 1024.0,
    TwoHourAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99,
    TwoHourBasicCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 0.50,
    DailyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12,
    DailyBasicCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 0.50 * 12,
    MonthlyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    MonthlyBasicCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 0.50 * 12 * 30,
    PotentialMonthlySavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.49 * 12 * 30
| extend 
    PercentageOfTotal = round(SizeBytes * 100.0 / toscalar(
        ContainerLogV2 
        | where TimeGenerated > ago(2h) and _ResourceId =` "{CLUSTER_RESOURCE_ID}"
        | summarize sum(estimate_data_size(*))
    ), 2),
    FilteringRecommendation = case(
        SizeGB > 1.0, strcat("HIGH PRIORITY: ", PodNamespace, " (", round(SizeGB, 3), " GB/month, $", round(MonthlyAnalyticsCostUSD, 2), ") - Filter to save $", round(PotentialMonthlySavingsUSD, 2), "/month"),
        SizeGB > 0.1, strcat("MEDIUM: ", PodNamespace, " (", round(SizeGB, 3), " GB/month, $", round(MonthlyAnalyticsCostUSD, 2), ") - Consider filtering to save $", round(PotentialMonthlySavingsUSD, 2), "/month"),
        SizeGB > 0.01, strcat("LOW: ", PodNamespace, " (", round(SizeGB, 3), " GB/month, $", round(MonthlyAnalyticsCostUSD, 2), ") - Minimal impact"),
        strcat("MINIMAL: ", PodNamespace, " (", round(SizeGB, 3), " GB/month, $", round(MonthlyAnalyticsCostUSD, 2), ") - Keep")
    ),
    ConfigMapEntry = case(
        SizeGB > 0.05, strcat('"', PodNamespace, '"'),
        ""
    )
| order by SizeGB desc
```

**Namespace ConfigMap Generator** - Generate dynamic ConfigMap recommendations based on analysis:
```kql
ContainerLogV2
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeBytes = sum(estimate_data_size(*)),
    UniqueContainers = dcount(ContainerName),
    UniquePods = dcount(PodName)
by PodNamespace
| extend 
    SizeGB = SizeBytes / 1024.0 / 1024.0 / 1024.0,
    MonthlyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    PotentialMonthlySavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.49 * 12 * 30,
    PercentageOfTotal = round(SizeBytes * 100.0 / toscalar(
        ContainerLogV2 
        | where TimeGenerated > ago(2h) and _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
        | summarize sum(estimate_data_size(*))
    ), 2)
| where SizeGB > 0.05  // Only include namespaces with meaningful volume
| extend 
    FilterCategory = case(
        PodNamespace in ("kube-system", "kube-public", "kube-node-lease"), "SYSTEM",
        PodNamespace contains "monitoring" or PodNamespace contains "prometheus" or PodNamespace contains "grafana", "MONITORING", 
        PodNamespace contains "logging" or PodNamespace contains "fluent" or PodNamespace contains "elastic", "LOGGING",
        PodNamespace contains "istio" or PodNamespace contains "linkerd" or PodNamespace contains "envoy", "SERVICE_MESH",
        SizeGB > 1.0, "HIGH_VOLUME_APP",
        "NORMAL_APP"
    )
| extend 
    FilterPriority = case(
        FilterCategory == "SYSTEM" and SizeGB > 0.5, 1,
        FilterCategory == "MONITORING" and SizeGB > 0.3, 2,
        FilterCategory == "LOGGING" and SizeGB > 0.3, 3,
        FilterCategory == "SERVICE_MESH" and SizeGB > 0.2, 4,
        FilterCategory == "HIGH_VOLUME_APP", 5,
        999
    )
| extend 
    ConfigMapGuidance = case(
        FilterPriority <= 5, strcat("RECOMMENDED: Add '", PodNamespace, "' to exclude_namespaces (saves $", round(PotentialMonthlySavingsUSD, 2), "/month)"),
        strcat("OPTIONAL: Consider '", PodNamespace, "' for filtering if needed")
    )
| order by FilterPriority asc, SizeGB desc
| project PodNamespace, SizeGB, MonthlyAnalyticsCostUSD, PotentialMonthlySavingsUSD, PercentageOfTotal, FilterCategory, ConfigMapGuidance
```

**Namespace Pattern Analysis** - Simple volume and cost analysis by namespace:
```kql
ContainerLogV2
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    TotalSizeBytes = sum(estimate_data_size(*)),
    LogCount = count(),
    UniqueContainers = dcount(ContainerName),
    UniquePods = dcount(PodName)
by PodNamespace
| extend 
    TotalSizeGB = TotalSizeBytes / 1024.0 / 1024.0 / 1024.0,
    MonthlyCostUSD = TotalSizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    BasicLogsSavingsUSD = TotalSizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.49 * 12 * 30,
    PercentageOfTotal = round(TotalSizeBytes * 100.0 / toscalar(
        ContainerLogV2 
        | where TimeGenerated > ago(2h) and _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
        | summarize sum(estimate_data_size(*))
    ), 2)
| order by TotalSizeGB desc
```

### 4. Enhanced Log Level Distribution Analysis

**Robust Log Level Query** - Raw log level distribution analysis without filtering bias:
```kql
ContainerLogV2
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| extend LogLevelParsed = case(
    // Primary: Check structured LogLevel column (case-insensitive)
    tolower(tostring(LogLevel)) == "info", "INFO",
    tolower(tostring(LogLevel)) == "debug", "DEBUG", 
    tolower(tostring(LogLevel)) == "warning" or tolower(tostring(LogLevel)) == "warn", "WARN",
    tolower(tostring(LogLevel)) == "error" or tolower(tostring(LogLevel)) == "err", "ERROR",
    tolower(tostring(LogLevel)) == "fatal" or tolower(tostring(LogLevel)) == "critical", "FATAL",
    tolower(tostring(LogLevel)) == "trace", "TRACE",
    // Secondary: Pattern matching in LogMessage content (case-insensitive)
    LogMessage matches regex @"(?i)\b(FATAL|CRITICAL)\b", "FATAL",
    LogMessage matches regex @"(?i)\b(ERROR|ERR)\b", "ERROR",
    LogMessage matches regex @"(?i)\b(WARN|WARNING)\b", "WARN",
    LogMessage matches regex @"(?i)\b(INFO|INFORMATION)\b", "INFO", 
    LogMessage matches regex @"(?i)\b(DEBUG|DBG)\b", "DEBUG",
    LogMessage matches regex @"(?i)\b(TRACE|TRC)\b", "TRACE",
    // Tertiary: Log level indicators at start of message
    LogMessage startswith "[ERROR]" or LogMessage startswith "ERROR:", "ERROR",
    LogMessage startswith "[WARN]" or LogMessage startswith "WARN:", "WARN",
    LogMessage startswith "[INFO]" or LogMessage startswith "INFO:", "INFO",
    LogMessage startswith "[DEBUG]" or LogMessage startswith "DEBUG:", "DEBUG",
    LogMessage startswith "[TRACE]" or LogMessage startswith "TRACE:", "TRACE",
    // Quaternary: JSON structured log detection (simplified)
    LogMessage contains '"level":"error"' or LogMessage contains '"level":"ERROR"', "ERROR",
    LogMessage contains '"level":"warn"' or LogMessage contains '"level":"WARN"', "WARN",
    LogMessage contains '"level":"info"' or LogMessage contains '"level":"INFO"', "INFO",
    LogMessage contains '"level":"debug"' or LogMessage contains '"level":"DEBUG"', "DEBUG",
    LogMessage contains '"level":"trace"' or LogMessage contains '"level":"TRACE"', "TRACE",
    // Default: Categorize as UNKNOWN for analysis
    "UNKNOWN"
)
| summarize 
    LogCount = count(),
    SizeBytes = sum(estimate_data_size(*))
by LogLevelParsed
| extend 
    SizeGB = SizeBytes / 1024.0 / 1024.0 / 1024.0,
    TwoHourAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99,
    DailyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12,
    MonthlyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    PercentageOfLogs = round(LogCount * 100.0 / toscalar(
        ContainerLogV2 
        | where TimeGenerated > ago(2h) and _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
        | count
    ), 2),
    PercentageOfVolume = round(SizeBytes * 100.0 / toscalar(
        ContainerLogV2 
        | where TimeGenerated > ago(2h) and _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
        | summarize sum(estimate_data_size(*))
    ), 2)
| order by SizeGB desc
```

**Log Level Summary Query** - Overall log level distribution for executive reporting:
```kql
ContainerLogV2
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| extend HasStructuredLogLevel = case(
    isnotempty(LogLevel) and LogLevel != "", "STRUCTURED",
    LogMessage contains '"level"' or LogMessage contains '"severity"', "JSON_STRUCTURED", 
    LogMessage matches regex @"(?i)\[(DEBUG|INFO|WARN|ERROR|FATAL|TRACE)\]", "BRACKETED",
    LogMessage matches regex @"(?i)\b(DEBUG|INFO|WARN|ERROR|FATAL|TRACE)\b", "KEYWORD_BASED",
    "UNSTRUCTURED"
)
| summarize 
    TotalLogCount = count(),
    TotalSizeBytes = sum(estimate_data_size(*))
by HasStructuredLogLevel
| extend 
    TotalSizeGB = TotalSizeBytes / 1024.0 / 1024.0 / 1024.0,
    TotalMonthlyCostUSD = TotalSizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    LogStructurePercentage = round(TotalLogCount * 100.0 / toscalar(
        ContainerLogV2 
        | where TimeGenerated > ago(2h) and _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
        | count
    ), 1),
    FilteringFeasibility = case(
        HasStructuredLogLevel in ("STRUCTURED", "JSON_STRUCTURED"), "HIGH: Structured log levels available",
        HasStructuredLogLevel in ("BRACKETED", "KEYWORD_BASED"), "MEDIUM: Pattern-based filtering possible",
        "LOW: Requires application-level changes"
    )
| order by TotalSizeGB desc
```

### 5. Legacy ContainerLog (v1) Analysis

**ContainerLog Full Analysis** - Complete analysis without namespace breakdown (ContainerLog v1 has limited schema):
```kql
ContainerLog
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeBytes = sum(estimate_data_size(*)),
    UniqueContainers = dcount(Name),
    UniquePods = dcount(tostring(split(Name, '/')[1])),
    UniqueComputers = dcount(Computer)
| extend 
    SizeGB = SizeBytes / 1024.0 / 1024.0 / 1024.0,
    TwoHourAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99,
    DailyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12,
    MonthlyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    MigrationSavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 22.41 * 12,
    BasicTierSavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 74.7 * 12,
    TotalMigrationSavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12
| extend 
    MigrationRecommendation = case(
        SizeGB > 2.0, strcat("HIGH PRIORITY: Migrate to ContainerLogV2 + Basic tier - Save $", round(SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12, 2), "/month"),
        SizeGB > 0.5, strcat("MEDIUM: Migrate to ContainerLogV2 + Basic tier - Save $", round(SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12, 2), "/month"),
        SizeGB > 0.0, strcat("LOW: Migrate when convenient - Save $", round(SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12, 2), "/month"),
        "No data to migrate"
    )
```

**ContainerLog Volume by Computer** - Analyze legacy container logs by node:
```kql
ContainerLog
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeBytes = sum(estimate_data_size(*)),
    UniqueContainers = dcount(Name)
by Computer
| extend 
    SizeGB = SizeBytes / 1024.0 / 1024.0 / 1024.0,
    MonthlyAnalyticsCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    MigrationSavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 22.41 * 12,
    BasicTierSavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 74.7 * 12,
    TotalMigrationSavingsUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12
| extend 
    MigrationRecommendation = case(
        SizeGB > 2.0, strcat("HIGH PRIORITY: Migrate to ContainerLogV2 + Basic tier - Save $", round(SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12, 2), "/month"),
        SizeGB > 0.5, strcat("MEDIUM: Migrate to ContainerLogV2 + Basic tier - Save $", round(SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12, 2), "/month"),
        SizeGB > 0.0, strcat("LOW: Migrate when convenient - Save $", round(SizeBytes / 1024.0 / 1024.0 / 1024.0 * 97.11 * 12, 2), "/month"),
        "No data to migrate"
    )
| order by SizeGB desc
```

**ContainerLog Source Analysis** - Identify noisy log sources for exclusion (using available columns only):
```kql
ContainerLog
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeBytes = sum(estimate_data_size(*)),
    SampleLogEntries = take_any(LogEntry, 3)
by LogEntrySource, Name
| extend 
    SizeGB = SizeBytes / 1024.0 / 1024.0 / 1024.0,
    MonthlyCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30,
    NoiseClassification = case(
        LogEntrySource == "stdout" and (Name contains "nginx" or Name contains "apache"), "WEB_ACCESS_LOGS",
        LogEntrySource == "stdout" and (Name contains "prometheus" or Name contains "grafana"), "MONITORING_LOGS", 
        LogEntrySource == "stdout" and Name contains "fluentd", "LOG_FORWARDING",
        LogEntrySource == "stderr" and SizeGB > 1.0, "HIGH_VOLUME_ERRORS",
        LogEntrySource == "stdout" and SizeGB > 2.0, "HIGH_VOLUME_STDOUT",
        LogEntrySource == "stdout", "NORMAL_STDOUT",
        LogEntrySource == "stderr", "NORMAL_STDERR",
        "OTHER"
    ),
    FilteringRecommendation = case(
        NoiseClassification == "WEB_ACCESS_LOGS", strcat("CONSIDER: Filter access logs - Potential $", round(MonthlyCostUSD * 0.8, 2), "/month savings"),
        NoiseClassification == "MONITORING_LOGS", strcat("EVALUATE: Reduce monitoring verbosity - Potential $", round(MonthlyCostUSD * 0.6, 2), "/month savings"),
        NoiseClassification == "LOG_FORWARDING", strcat("OPTIMIZE: Check log forwarding efficiency - Potential $", round(MonthlyCostUSD * 0.5, 2), "/month savings"),
        SizeGB > 2.0, strcat("HIGH PRIORITY: Investigate high volume - Potential $", round(MonthlyCostUSD * 0.7, 2), "/month savings"),
        "KEEP: Normal volume"
    )
| order by SizeGB desc
| take 20
```

### 6. KubePodInventory Replacement Analysis

**KubePodInventory Volume and Replacement Strategy** - Analyze inventory data for metadata collection replacement:
```kql
Usage
| where TimeGenerated > ago(2h)
| where DataType == "KubePodInventory"
| summarize 
    TotalGB = sum(Quantity) / 1024,
    TwoHourCostUSD = sum(Quantity) / 1024 * 2.99,
    DailyCostUSD = sum(Quantity) / 1024 * 2.99 * 12, // 12 x 2-hour periods per day
    MonthlyCostUSD = sum(Quantity) / 1024 * 2.99 * 12 * 30, // Extrapolate to 30 days
    MetadataCollectionSavingsUSD = sum(Quantity) / 1024 * 2.99 * 12 * 30 * 0.85 // 85% reduction with metadata collection
| extend 
    ReplacementStrategy = case(
        TotalGB > 1.0, strcat("HIGH PRIORITY: Replace with metadata collection - Save $", round(MetadataCollectionSavingsUSD, 2), "/month"),
        TotalGB > 0.1, strcat("MEDIUM: Replace with metadata collection - Save $", round(MetadataCollectionSavingsUSD, 2), "/month"),
        TotalGB > 0.0, strcat("LOW: Replace when migrating to ContainerLogV2 - Save $", round(MetadataCollectionSavingsUSD, 2), "/month"),
        "No KubePodInventory data found"
    )
| project TotalGB, DailyCostUSD, MonthlyCostUSD, MetadataCollectionSavingsUSD, ReplacementStrategy
```

**KubePodInventory Detail Analysis** - Understand current inventory data usage (using available columns only):
```kql
KubePodInventory
| where TimeGenerated > ago(2h)
| where ClusterName contains "{CLUSTER_RESOURCE_ID}" or _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    PodCount = dcount(PodUid),
    NamespaceCount = dcount(Namespace),
    RecordCount = count(),
    UniqueLabels = dcount(tostring(PodLabel))
by Namespace
| extend 
    MigrationPriority = case(
        PodCount > 50, "HIGH: Large inventory overhead",
        PodCount > 10, "MEDIUM: Moderate inventory overhead", 
        "LOW: Minimal inventory overhead"
    ),
    ReplacementStrategy = "Replace with ContainerLogV2 metadata collection for 85% cost reduction"
| order by PodCount desc
```

### 7. Container Volume Analysis (ContainerLogV2)

**Container Volume Query** - Identify high-volume containers in ContainerLogV2:
```kql
ContainerLogV2
| where TimeGenerated > ago(2h)
| where _ResourceId =~ "{CLUSTER_RESOURCE_ID}"
| summarize 
    LogCount = count(),
    SizeBytes = sum(estimate_data_size(*))
by ContainerName, PodNamespace
| extend 
    SizeGB = SizeBytes / 1024.0 / 1024.0 / 1024.0,
    MonthlyCostUSD = SizeBytes / 1024.0 / 1024.0 / 1024.0 * 2.99 * 12 * 30
| order by SizeGB desc
| take 20
```

---

## ContainerLog v1 → ContainerLogV2 Migration Benefits

### **Critical Migration Advantages**

**ContainerLogV2 is the ONLY container logging table that supports Basic Logs tier conversion**, providing massive cost optimization opportunities not available with legacy ContainerLog v1.

| **Benefit** | **ContainerLog (v1)** | **ContainerLogV2** | **Impact** |
|-------------|----------------------|-------------------|------------|
| **Basic Logs Tier Support** | ❌ Not supported | ✅ **Fully supported** | **<span style="color: #28a745; font-weight: bold;">83% cost reduction</span>** |
| **Pricing Optimization** | Stuck at <span style="color: #dc3545; font-weight: bold;">$2.99/GB</span> | Can use <span style="color: #28a745; font-weight: bold;">$0.50/GB</span> Basic tier | **<span style="color: #28a745; font-weight: bold;">$2.49/GB savings</span>** |
| **KubePodInventory Replacement** | ❌ Requires separate collection | ✅ **Built-in metadata collection** | **<span style="color: #28a745; font-weight: bold;">85% inventory cost reduction</span>** |
| **Pod Metadata** | Requires KubePodInventory | Integrated via metadata collection | **Eliminates redundant data** |
| **Namespace Filtering** | Basic exclusion only | Advanced namespace/pod filtering | **Granular cost control** |
| **Schema Efficiency** | Legacy format | Optimized schema | **<span style="color: #17a2b8; font-weight: bold;">25% storage efficiency</span>** |
| **Query Performance** | Standard | Enhanced indexing | **Faster log searches** |

### **Why ContainerLogV2 Migration is Essential**

#### **1. Basic Logs Tier Eligibility**
- **EXCLUSIVE FEATURE**: Only ContainerLogV2 can be converted to Basic Logs tier ($0.50/GB vs $2.99/GB)
- **ContainerLog v1 limitation**: Forever locked at Analytics tier pricing
- **Cost impact**: 83% immediate savings on container log ingestion costs
- **No functionality loss**: Container debugging and troubleshooting remain fully functional

#### **2. KubePodInventory Elimination**
- **Metadata integration**: ContainerLogV2 can collect pod labels, annotations, images directly
- **Redundancy removal**: Eliminates need for separate KubePodInventory table
- **Combined savings**: Container logs + inventory data in single optimized table
- **Metadata fields available**: podLabels, podAnnotations, podUid, image, imageID, imageRepo, imageTag

#### **3. Architecture Simplification**
```
BEFORE (ContainerLog v1):
├── ContainerLog table ($2.99/GB - Analytics only)
├── KubePodInventory table ($2.99/GB - Separate collection)
└── Limited filtering options

AFTER (ContainerLogV2):
├── ContainerLogV2 table ($0.50/GB - Basic tier eligible)
├── Integrated metadata (replaces KubePodInventory)
└── Advanced filtering capabilities
```

### **Migration Implementation Strategy**

#### **Step 1: Enable ContainerLogV2 Schema**
```yaml
[log_collection_settings.schema]
  containerlog_schema_version = "v2"
```

#### **Step 2: Enable Kubernetes Metadata Collection (Replaces KubePodInventory)**
```yaml
[log_collection_settings.metadata_collection]
  enabled = true
  include_fields = ["podLabels","podAnnotations","podUid","image","imageID","imageRepo","imageTag"]
```

**Alternative Kubernetes Metadata Setting:**
```yaml
[log_collection_settings.kubernetes_metadata]
  enabled = true
```

#### **Step 3: Disable KubePodInventory Collection**
```yaml
[metric_collection_settings.collect_kube_pod_inventory]
  enabled = false
```

#### **Step 4: Convert to Basic Logs Tier**
```bash
az monitor log-analytics workspace table update \
  --name ContainerLogV2 --plan Basic
```

### **Cost Optimization Formula**

**Legacy Architecture (ContainerLog v1):**
```
Monthly Cost = (ContainerLog Volume × $2.99) + (KubePodInventory Volume × $2.99)
Example: (10GB × $89.70) + (2GB × $59.80) = $956.40/month
```

**Optimized Architecture (ContainerLogV2):**
```
Monthly Cost = (ContainerLogV2 Volume × $0.50) + (Eliminated KubePodInventory)
Example: (10GB × $15.00) + $0 = $15.00/month
Savings: $941.40/month (98.4% reduction)
```

### **<span style="color: #28a745; font-weight: bold;">💰 Example Cost Impact</span>**
- **Current Monthly Cost**: <span style="color: #dc3545; font-weight: bold;">$956.40</span>
- **Optimized Monthly Cost**: <span style="color: #28a745; font-weight: bold;">$15.00</span>
- **Monthly Savings**: <span style="color: #28a745; font-weight: bold;">$941.40</span>
- **Annual Savings**: <span style="color: #28a745; font-weight: bold;">$11,296.80</span>
- **Cost Reduction**: <span style="color: #28a745; font-weight: bold;">98.4%</span>

---

## Log Analytics Pricing Tiers: Analytics vs Basic Logs

### Tier Comparison Overview

| **Feature** | **Analytics Logs** | **Basic Logs** | **Cost Impact** |
|-------------|-------------------|----------------|-----------------|
| **Pricing** | <span style="color: #dc3545; font-weight: bold;">$2.99/GB</span> | <span style="color: #28a745; font-weight: bold;">$0.50/GB</span> | **<span style="color: #28a745; font-weight: bold;">83% savings</span>** |
| **Retention** | Up to 12 years | Max 30 days | Limited archival |
| **Query Capabilities** | Full KQL support | Basic search only | Reduced analytics |
| **Real-time Alerting** | ✅ Supported | ❌ Not supported | No live alerts |
| **Workbooks/Dashboards** | ✅ Full support | ⚠️ Limited | Reduced visualization |
| **Best Use Case** | Critical monitoring | Log archival/compliance | Different objectives |

### ContainerLogV2 Basic Logs Assessment

**Why ContainerLogV2 is Perfect for Basic Logs:**
- **Primary use case**: Debugging and troubleshooting (doesn't need real-time alerting)
- **Compliance/auditing**: 30-day retention often sufficient for container logs
- **Alert source**: Real-time monitoring typically comes from metrics (Prometheus), not logs
- **Query patterns**: Most container log queries are simple searches, not complex analytics
- **Cost impact**: 83% cost reduction with minimal functional impact

### Implementation: Enable Basic Logs for ContainerLogV2

**Azure CLI Command:**
```bash
# Set ContainerLogV2 table to Basic Logs tier
az monitor log-analytics workspace table update \
  --resource-group <resource-group> \
  --workspace-name <workspace-name> \
  --name ContainerLogV2 \
  --plan Basic
```

**Azure PowerShell:**
```powershell
# Alternative PowerShell command
Set-AzOperationalInsightsTable -ResourceGroupName "<resource-group>" `
  -WorkspaceName "<workspace-name>" `
  -TableName "ContainerLogV2" `
  -Plan "Basic"
```

**Verification Query:**
```kql
# Check current table plan
.show table ContainerLogV2 details
```

### Basic Logs Limitations & Considerations

**⚠️ Important Limitations:**
- **30-day retention maximum**: Cannot extend beyond 30 days
- **No real-time alerting**: Cannot create alerts directly on Basic Logs data
- **Limited KQL functions**: Some advanced analytics functions not supported
- **Search-only queries**: Complex joins and aggregations may not work
- **Workbook limitations**: Some visualizations may not function properly

**✅ What Still Works:**
- **Basic search queries**: Text searches, simple filtering
- **Compliance/auditing**: Perfect for log retention and review
- **Manual troubleshooting**: Searching logs for specific errors or events
- **Cost optimization**: 83% cost reduction with minimal impact

**🎯 Ideal Scenarios for Basic Logs:**
- Container stdout/stderr logs (debugging)
- Compliance and audit log retention
- Historical log analysis (non-real-time)
- High-volume, low-criticality log streams

---

## ContainerLogV2 Detailed Optimization Guide

### Log Level Optimization Strategy

**Debug/Trace Logs Elimination:**
- **Impact**: Debug logs often represent 40-60% of total volume
- **Recommendation**: Filter out DEBUG and TRACE levels entirely
- **Implementation**: Application-level configuration + ConfigMap filtering
- **Savings**: Up to 60% volume reduction

**Info Log Selective Filtering:**
- **Strategy**: Keep critical INFO logs, filter verbose INFO messages
- **Patterns to filter**: Health checks, routine status messages, request logging
- **Implementation**: Regex-based filtering in ConfigMap
- **Savings**: 20-40% additional volume reduction

### Namespace-Based Optimization

**Data-Driven Namespace Analysis:**

Execute the namespace analysis queries to identify high-volume namespaces in your specific cluster. Common patterns may include:

- **System namespaces**: Often generate significant operational logs
- **Application namespaces**: Vary widely by workload characteristics  
- **Monitoring namespaces**: Can be high-volume depending on configuration
- **Development namespaces**: May have different optimization priorities

**Analysis-Driven Strategy:**
- **High-volume namespaces**: Consider Basic Logs tier (83% savings)
- **Critical application namespaces**: Keep Analytics tier, implement log level filtering
- **Development/staging namespaces**: Evaluate filtering or Basic Logs based on requirements
- **Low-volume namespaces**: May not require optimization

### Container-Specific Optimization

**High-Volume Container Patterns:**
- **Ingress controllers**: Often generate 30-50% of cluster logs
- **Service mesh sidecars**: Istio/Linkerd proxies generate significant volume
- **Monitoring agents**: Ironically, monitoring tools can be very verbose
- **CI/CD pods**: Build and deployment containers with extensive logging

**Optimization Approaches:**
1. **Selective logging**: Configure applications to reduce log verbosity
2. **Namespace exclusion**: Move high-volume, low-criticality workloads
3. **Container-specific rules**: Target individual high-volume containers
4. **Sampling**: Implement log sampling for high-volume patterns

### Advanced ConfigMap Configuration

**Comprehensive Optimization ConfigMap with Metadata Collection:**
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
          # Configure namespace exclusions based on your analysis results
          # exclude_namespaces = ["namespace1", "namespace2"]
       [log_collection_settings.stderr]
          enabled = true
          # Configure namespace exclusions based on your analysis results
          # exclude_namespaces = ["namespace1", "namespace2"]
       [log_collection_settings.schema]
          containerlog_schema_version = "v2"
       [log_collection_settings.filtering]
          # Configure log level filtering based on your analysis results
          # exclude_log_levels = ["DEBUG", "TRACE"]
          # Configure regex filtering based on your analysis results
          # exclude_regex_patterns = [".*pattern1.*", ".*pattern2.*"]
       [log_collection_settings.metadata_collection]
          # Enable metadata collection to replace KubePodInventory
          enabled = true
          include_fields = ["podLabels","podAnnotations","podUid","image","imageID","imageRepo","imageTag"]
    [metric_collection_settings]
       [metric_collection_settings.collect_kube_system_metrics]
          enabled = false
       [metric_collection_settings.collect_kube_pod_inventory]
          # Disable KubePodInventory when using metadata collection
          enabled = false
```

**Legacy ContainerLog (v1) Filtering ConfigMap:**
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
          # Configure namespace exclusions based on your analysis results
          # exclude_namespaces = ["namespace1", "namespace2"]
          # Configure container exclusions based on your analysis results
          # exclude_containers = ["container1", "container2"]
          # Configure regex filtering based on your analysis results
          # exclude_regex_patterns = [".*pattern1.*", ".*pattern2.*"]
       [log_collection_settings.stderr]
          enabled = true
          # Configure namespace exclusions based on your analysis results
          # exclude_namespaces = ["namespace1", "namespace2"]
       [log_collection_settings.schema]
          # Migrate to v2 schema for better efficiency
          containerlog_schema_version = "v2"
    [metric_collection_settings]
       [metric_collection_settings.collect_kube_system_metrics]
          enabled = false
```

### Cost Calculation Formulas

**Analytics Tier Cost:**
```
Monthly Cost = Daily Volume (GB) × $2.99 × 30 days
```

**Basic Logs Tier Cost:**
```
Monthly Cost = Daily Volume (GB) × $0.50 × 30 days
Savings = Analytics Cost - Basic Cost = Daily Volume × $2.49 × 30
Savings Percentage = 83.3%
```

**Combined Optimization Impact:**
```
Total Savings = Namespace Filtering (30-50%) + Basic Logs (83% of remaining) + Log Level Filtering (20-40% additional)
Potential Total Reduction = 85-95% of original Analytics tier cost
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

### Azure Monitor Metrics (Managed Prometheus) Conditional Recommendations

**CRITICAL CHECK**: Use azuremonitormetrics toolset to detect current Azure Monitor Metrics status.

**IF Azure Monitor Metrics is ALREADY ENABLED:**
- ✅ **CONFIGURATION OPTIMAL**: Managed Prometheus is already enabled
- ✅ **Metrics Cost Optimized**: Already achieving 80% cost reduction vs metrics-as-logs
- ✅ **No Action Required**: Skip Prometheus enablement recommendation
- 📊 **Focus on**: Log optimization opportunities (Basic Logs, filtering, etc.)

**IF Azure Monitor Metrics is NOT ENABLED:**
- 🚨 **HIGH PRIORITY RECOMMENDATION**: Enable Azure Monitor Metrics (Managed Prometheus) 
- 💰 **Immediate benefit**: 80% cost reduction for all performance metrics
- 🔄 **Replace**: Perf and InsightsMetrics data streams with efficient Prometheus metrics
- 💲 **Cost impact**: Can save $40-160/month for typical clusters based on current Perf/InsightsMetrics volume
- ⏱️ **Implementation**: 5-minute setup via Azure portal or CLI

**Enable Azure Monitor Metrics Command (only if not already enabled):**
```bash
az aks update --resource-group <resource-group> --name <cluster-name> --enable-azure-monitor-metrics
```

**Verification**: Check azuremonitormetrics toolset confirms successful enablement.

### Architecture Optimization Strategy

**Optimal Configuration:**
- ✅ Azure Monitor Metrics (Managed Prometheus): ALL performance metrics
- ✅ ContainerLogV2: Container stdout/stderr logs + Kubernetes events  
- ❌ Remove: Perf, InsightsMetrics, KubePodInventory tables
- ❌ Filter: High-volume namespaces based on analysis results

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

Deploy this ConfigMap to implement filtering and schema optimization based on your analysis results:

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
          # Configure namespace exclusions based on your analysis results
          # exclude_namespaces = ["namespace1", "namespace2"]
       [log_collection_settings.stderr]
          enabled = true
          # Configure namespace exclusions based on your analysis results
          # exclude_namespaces = ["namespace1", "namespace2"]
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
| **P2** | **Enable Basic Logs for ContainerLogV2** | **83% log tier cost** | **2 minutes** |
| **P3** | Deploy ConfigMap optimization | 30-50% log volume | 10 minutes |
| **P4** | Monitor and validate | Confirm savings | 24-48 hours |

---

## Executive Report Template

### Analysis Results Format

Present findings using this structure:

```
🤖 AI-GENERATED AZURE MONITOR LOGS COST OPTIMIZATION REPORT

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

## 💡 ACTION ITEMS & SAVINGS BREAKDOWN

### Immediate Actions (High Impact)
| Priority | Action | Monthly Savings | Implementation | Status |
|----------|--------|----------------|---------------|--------|
| P1 | Enable Azure Monitor Metrics (if not enabled) | $${metrics_savings} | 5 minutes | ${prometheus_status} |
| P2 | Enable Basic Logs for ContainerLogV2 | $${basic_logs_savings} | 2 minutes | Recommended |
| P3 | Deploy namespace filtering ConfigMap | $${namespace_filtering_savings} | 10 minutes | Recommended |
| P4 | Implement log level filtering | $${log_level_savings} | 15 minutes | Optional |

### Detailed Action Items

**1. Azure Monitor Metrics Optimization**
- **Current Status**: ${prometheus_current_status}
- **Action Required**: ${prometheus_action_required}
- **Expected Savings**: $${metrics_savings}/month (${metrics_savings_percentage}% reduction)
- **Implementation**: ${prometheus_implementation_command}

**2. Basic Logs Tier Migration**
- **Current Tier**: Analytics ($2.99/GB)
- **Recommended Tier**: Basic ($0.50/GB)
- **Expected Savings**: $${basic_logs_savings}/month (83% tier cost reduction)
- **Volume Impact**: ${containerlogv2_volume_gb} GB/month affected
- **Implementation**: `az monitor log-analytics workspace table update --name ContainerLogV2 --plan Basic`

**⚠️ Important Basic Logs Limitations:**
- **30-day retention maximum**: Cannot extend beyond 30 days (vs up to 12 years in Analytics)
- **No real-time alerting**: Cannot create alerts directly on Basic Logs data
- **Limited KQL functions**: Some advanced analytics functions not supported
- **Search-only queries**: Complex joins and aggregations may not work
- **Workbook limitations**: Some visualizations may not function properly
- **Best for**: Container debugging, compliance logs, historical analysis (non-real-time)
- **Not suitable for**: Real-time monitoring, long-term data retention, complex analytics

**3. Namespace Filtering Optimization**

**EXECUTE NAMESPACE ANALYSIS IMMEDIATELY**: When generating this report, you MUST execute the "Namespace ConfigMap Generator" query from Section 3 and provide actual namespace-by-namespace results, NOT placeholder text.

**Namespace Analysis Results**: Based on executed ContainerLogV2 namespace queries, provide detailed breakdown:

**Volume & Cost by Namespace:**
- Display results from "Comprehensive Namespace Query" showing each namespace's volume, cost, and filtering recommendations
- Include specific GB amounts, USD costs, and percentage of total cluster logs per namespace
- Show the actual FilteringRecommendation field results for each namespace

**ConfigMap Implementation Guidance:**
- Display results from "Namespace ConfigMap Generator" query showing specific namespaces to filter
- Provide exact namespace names and their FilterCategory (SYSTEM, MONITORING, LOGGING, etc.)
- Include specific dollar savings amounts per namespace from the ConfigMapGuidance field

**Sample ConfigMap with Real Data:**
Generate dynamic ConfigMap based on actual analysis results:
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
          # Based on analysis results - add high-volume namespaces here:
          # exclude_namespaces = [ACTUAL_NAMESPACE_LIST_FROM_ANALYSIS]
       [log_collection_settings.stderr]
          enabled = true
          # exclude_namespaces = [ACTUAL_NAMESPACE_LIST_FROM_ANALYSIS]
       [log_collection_settings.schema]
          containerlog_schema_version = "v2"
```

**MANDATORY EXECUTION**: Do NOT use generic text like "No high-volume namespaces detected" - ALWAYS execute the namespace analysis queries and provide actual cluster-specific results with real namespace names, volumes, and costs.

**4. Log Level Filtering (Conditional)**
- **Debug/Trace Volume**: ${debug_trace_volume_gb} GB/month (${debug_trace_status})
- **Info Log Volume**: ${info_volume_gb} GB/month (${info_volume_status})
- **Log Structure Assessment**: ${log_structure_feasibility}
- **Expected Savings**: $${log_level_savings}/month
- **Implementation**: ${log_level_implementation_strategy}
- **Alternative**: If structured levels unavailable, focus on application-level logging configuration

### Total Optimization Impact
- **Current Monthly Cost**: $${current_total_cost}
- **Optimized Monthly Cost**: $${optimized_total_cost}
- **Total Monthly Savings**: $${total_savings} (${total_savings_percentage}% reduction)
- **Annual Savings**: $${annual_savings}

### Implementation Timeline
- **Week 1**: Enable Azure Monitor Metrics + Basic Logs (P1, P2)
- **Week 2**: Deploy namespace filtering ConfigMap (P3)  
- **Week 3**: Implement log level filtering (P4)
- **Week 4**: Monitor and validate savings
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
