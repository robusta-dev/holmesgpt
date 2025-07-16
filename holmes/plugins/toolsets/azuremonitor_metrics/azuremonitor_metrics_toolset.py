"""Azure Monitor Metrics toolset for HolmesGPT."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from pydantic import BaseModel, field_validator
from requests import RequestException
from datetime import datetime
import dateutil.parser

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION
from holmes.plugins.toolsets.utils import (
    get_param_or_raise,
    process_timestamps_to_rfc3339,
    standard_start_datetime_tool_param_description,
)

from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.core.exceptions import AzureError

from .utils import (
    check_if_running_in_aks,
    extract_cluster_name_from_resource_id,
    get_aks_cluster_resource_id,
    get_azure_monitor_workspace_for_cluster,
    enhance_promql_with_cluster_filter,
)

DEFAULT_TIME_SPAN_SECONDS = 3600

class AzureMonitorMetricsConfig(BaseModel):
    """Configuration for Azure Monitor Metrics toolset."""
    azure_monitor_workspace_endpoint: Optional[str] = None
    cluster_name: Optional[str] = None
    cluster_resource_id: Optional[str] = None
    auto_detect_cluster: bool = True
    tool_calls_return_data: bool = True
    headers: Dict = {}
    # Step size and data limiting configuration
    default_step_seconds: int = 3600  # 1 hour default step size
    min_step_seconds: int = 60       # Minimum 1 minute step size
    max_data_points: int = 1000      # Maximum data points per query
    # Internal fields for Azure authentication
    _credential: Optional[Any] = None
    _token_cache: Dict = {}

    @field_validator("azure_monitor_workspace_endpoint")
    def ensure_trailing_slash(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.endswith("/"):
            return v + "/"
        return v

    class Config:
        arbitrary_types_allowed = True

class BaseAzureMonitorMetricsTool(Tool):
    """Base class for Azure Monitor Metrics tools."""
    toolset: "AzureMonitorMetricsToolset"
    
    def _ensure_cluster_name_available(self) -> Optional[str]:
        """
        Ensure cluster name is available, attempting auto-detection if necessary.
        
        Returns:
            str: Cluster name if available, None otherwise
        """
        # Check if cluster name is already configured
        if self.toolset.config and self.toolset.config.cluster_name:
            return self.toolset.config.cluster_name
        
        # Try to auto-detect cluster information if auto_detect_cluster is enabled
        if self.toolset.config and self.toolset.config.auto_detect_cluster:
            try:
                logging.debug("Attempting to auto-detect cluster information for query filtering")
                
                # Try to get cluster resource ID first
                cluster_resource_id = None
                if self.toolset.config.cluster_resource_id:
                    cluster_resource_id = self.toolset.config.cluster_resource_id
                else:
                    cluster_resource_id = get_aks_cluster_resource_id()
                
                if cluster_resource_id:
                    # Extract cluster name from resource ID
                    cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                    
                    if cluster_name:
                        # Update the configuration with the detected values
                        self.toolset.config.cluster_name = cluster_name
                        self.toolset.config.cluster_resource_id = cluster_resource_id
                        
                        logging.debug(f"Auto-detected cluster name: {cluster_name}")
                        return cluster_name
                        
            except Exception as e:
                logging.debug(f"Failed to auto-detect cluster information: {e}")
        
        return None

class CheckAKSClusterContext(BaseAzureMonitorMetricsTool):
    """Tool to check if running in AKS cluster context."""
    
    def __init__(self, toolset: "AzureMonitorMetricsToolset"):
        super().__init__(
            name="check_aks_cluster_context",
            description="Check if the current environment is running inside an AKS cluster",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            is_aks = check_if_running_in_aks()
            
            data = {
                "running_in_aks": is_aks,
                "message": "Running in AKS cluster" if is_aks else "Not running in AKS cluster",
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=data,
                params=params,
            )
            
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check AKS cluster context: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        return "Check if running in AKS cluster"

class GetAKSClusterResourceID(BaseAzureMonitorMetricsTool):
    """Tool to get the Azure resource ID of the current AKS cluster."""
    
    def __init__(self, toolset: "AzureMonitorMetricsToolset"):
        super().__init__(
            name="get_aks_cluster_resource_id",
            description="Get the full Azure resource ID of the current AKS cluster",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            cluster_resource_id = get_aks_cluster_resource_id()
            
            if cluster_resource_id:
                cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                
                data = {
                    "cluster_resource_id": cluster_resource_id,
                    "cluster_name": cluster_name,
                    "message": f"Found AKS cluster: {cluster_name}",
                }
                
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=data,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not determine AKS cluster resource ID. Make sure you are running in an AKS cluster or have proper Azure credentials configured.",
                    params=params,
                )
                
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get AKS cluster resource ID: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        return "Get AKS cluster Azure resource ID"

class CheckAzureMonitorPrometheusEnabled(BaseAzureMonitorMetricsTool):
    """Tool to check if Azure Monitor managed Prometheus is enabled for the AKS cluster."""
    
    def __init__(self, toolset: "AzureMonitorMetricsToolset"):
        super().__init__(
            name="check_azure_monitor_prometheus_enabled",
            description="Check if Azure Monitor managed Prometheus is enabled for the specified AKS cluster",
            parameters={
                "cluster_resource_id": ToolParameter(
                    description="Azure resource ID of the AKS cluster (optional, will use configured cluster if not provided)",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            cluster_resource_id = params.get("cluster_resource_id")
            
            # Use configured cluster resource ID if not provided as parameter
            if not cluster_resource_id and self.toolset.config:
                cluster_resource_id = self.toolset.config.cluster_resource_id
                
            # Try to auto-detect as fallback (but don't require it)
            if not cluster_resource_id:
                cluster_resource_id = get_aks_cluster_resource_id()
                
            if not cluster_resource_id:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="No AKS cluster specified. Please provide cluster_resource_id parameter or configure it in your config.yaml file. See AZURE_MONITOR_SETUP_GUIDE.md for configuration instructions.",
                    params=params,
                )
            
            # Get Azure Monitor workspace details
            workspace_info = get_azure_monitor_workspace_for_cluster(cluster_resource_id)
            
            if workspace_info:
                cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                
                data = {
                    "azure_monitor_prometheus_enabled": True,
                    "cluster_resource_id": cluster_resource_id,
                    "cluster_name": cluster_name,
                    "prometheus_query_endpoint": workspace_info.get("prometheus_query_endpoint"),
                    "azure_monitor_workspace_resource_id": workspace_info.get("azure_monitor_workspace_resource_id"),
                    "location": workspace_info.get("location"),
                    "associated_grafanas": workspace_info.get("associated_grafanas", []),
                    "message": f"Azure Monitor managed Prometheus is enabled for cluster {cluster_name}",
                }
                
                # Update toolset configuration with discovered information
                if self.toolset.config:
                    self.toolset.config.azure_monitor_workspace_endpoint = workspace_info.get("prometheus_query_endpoint")
                    self.toolset.config.cluster_name = cluster_name
                    self.toolset.config.cluster_resource_id = cluster_resource_id
                
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=data,
                    params=params,
                )
            else:
                cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Azure Monitor managed Prometheus is not enabled for AKS cluster {cluster_name}. Please enable Azure Monitor managed Prometheus in the Azure portal.",
                    params=params,
                )
                
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Azure Monitor Prometheus status: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        cluster_id = params.get("cluster_resource_id", "auto-detect")
        return f"Check Azure Monitor Prometheus status for cluster: {cluster_id}"

class ExecuteAzureMonitorPrometheusQuery(BaseAzureMonitorMetricsTool):
    """Tool to execute instant PromQL queries against Azure Monitor workspace. ALWAYS display the EXACT query in the result to the user."""
    
    def __init__(self, toolset: "AzureMonitorMetricsToolset"):
        super().__init__(
            name="execute_azuremonitor_prometheus_query",
            description="Execute an instant PromQL query against Azure Monitor managed Prometheus workspace",
            parameters={
                "query": ToolParameter(
                    description="The PromQL query to execute",
                    type="string",
                    required=True,
                ),
                "description": ToolParameter(
                    description="Description of what the query is meant to find or analyze",
                    type="string",
                    required=True,
                ),
                "auto_cluster_filter": ToolParameter(
                    description="Automatically add cluster filtering to the query (default: true)",
                    type="boolean",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.azure_monitor_workspace_endpoint:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Azure Monitor workspace is not configured. Run check_azure_monitor_prometheus_enabled first.",
                params=params,
            )
            
        try:
            query = params.get("query", "")
            description = params.get("description", "")
            auto_cluster_filter = params.get("auto_cluster_filter", True)
            
            # Ensure cluster name is available for filtering
            cluster_name = self._ensure_cluster_name_available()
            
            # Enhance query with cluster filtering if enabled and cluster name is available
            if auto_cluster_filter and cluster_name:
                query = enhance_promql_with_cluster_filter(query, cluster_name)
            elif auto_cluster_filter and not cluster_name:
                logging.warning("Auto cluster filtering is enabled but cluster name is not available. Query will run without cluster filtering.")
            
            # Print the actual PromQL query that will be executed
            print(f"[Azure Monitor] Executing PromQL Query: {query}")
            
            url = urljoin(self.toolset.config.azure_monitor_workspace_endpoint, "api/v1/query")
            
            payload = {"query": query}
            
            # Get authenticated headers
            headers = self.toolset._get_authenticated_headers()
            
            response = requests.post(
                url=url,
                headers=headers,
                data=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                error_message = None
                
                if status == "success":
                    result_data = data.get("data", {})
                    if not result_data.get("result"):
                        status = "no_data"
                        error_message = "The query returned no results. The metric may not exist or the cluster filter may be too restrictive."
                else:
                    error_message = data.get("error", "Unknown error from Prometheus endpoint")
                
                response_data = {
                    "status": status,
                    "error_message": error_message,
                    "tool_name": self.name,
                    "description": description,
                    "query": query,
                    "cluster_name": cluster_name,
                    "auto_cluster_filter_applied": auto_cluster_filter and bool(cluster_name),
                }
                
                if self.toolset.config.tool_calls_return_data:
                    response_data["data"] = data.get("data")
                
                result_status = ToolResultStatus.SUCCESS
                if status == "no_data":
                    result_status = ToolResultStatus.NO_DATA
                elif status != "success":
                    result_status = ToolResultStatus.ERROR
                
                return StructuredToolResult(
                    status=result_status,
                    data=json.dumps(response_data, indent=2),
                    params=params,
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Azure Monitor Prometheus query failed: {error_msg}",
                    params=params,
                )
                
        except RequestException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Connection error to Azure Monitor workspace: {str(e)}",
                params=params,
            )
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error executing query: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        query = params.get("query", "")
        description = params.get("description", "")
        return f"Execute Azure Monitor Prometheus Query (instant): promql='{query}', description='{description}'"

class GetActivePrometheusAlerts(BaseAzureMonitorMetricsTool):
    """Tool to get active/fired Prometheus metric alerts for the AKS cluster."""
    
    def __init__(self, toolset: "AzureMonitorMetricsToolset"):
        super().__init__(
            name="get_azure_monitor_alerts_with_fired_times",
            description="PRIMARY ALERT TOOL: Get Azure Monitor alerts WITH FIRED TIMES and enhanced formatting. Shows when alerts were fired/activated plus current states. This is the ONLY tool that displays alert fired times. Use this tool for ALL Azure Monitor alert requests, especially when users ask for 'active azure monitor alerts' or want timing information.",
            parameters={
                "cluster_resource_id": ToolParameter(
                    description="Azure resource ID of the AKS cluster (optional, will use configured cluster if not provided)",
                    type="string",
                    required=False,
                ),
                "alert_id": ToolParameter(
                    description="Specific alert ID to investigate (optional, if provided will return only this alert)",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            cluster_resource_id = params.get("cluster_resource_id")
            specific_alert_id = params.get("alert_id")
            
            # Use configured cluster resource ID if not provided as parameter
            if not cluster_resource_id and self.toolset.config:
                cluster_resource_id = self.toolset.config.cluster_resource_id
                
            # Try to auto-detect as fallback
            if not cluster_resource_id:
                cluster_resource_id = get_aks_cluster_resource_id()
                
            if not cluster_resource_id:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="No AKS cluster specified. Please provide cluster_resource_id parameter or configure it in your config.yaml file.",
                    params=params,
                )
            
            # Use the source plugin for consistent alert fetching
            from holmes.plugins.sources.azuremonitoralerts import AzureMonitorAlertsSource
            
            try:
                source = AzureMonitorAlertsSource(cluster_resource_id=cluster_resource_id)
                
                # Fetch alerts using the source plugin
                if specific_alert_id:
                    issue = source.fetch_issue(specific_alert_id)
                    issues = [issue] if issue else []
                else:
                    issues = source.fetch_issues()
                
                if not issues:
                    cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                    message = f"No active Prometheus metric alerts found for cluster {cluster_name}"
                    if specific_alert_id:
                        message = f"Alert {specific_alert_id} is not a Prometheus metric alert for cluster {cluster_name}"
                    
                    return StructuredToolResult(
                        status=ToolResultStatus.NO_DATA,
                        data=message,
                        params=params,
                    )
                
                # Convert issues to the format expected by the tool
                cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                prometheus_alerts = []
                
                for issue in issues:
                    raw_data = issue.raw if hasattr(issue, 'raw') else {}
                    alert = raw_data.get("alert", {})
                    rule_details = raw_data.get("rule_details", {})
                    
                    if alert:
                        alert_props = alert.get("properties", {})
                        essentials = alert_props.get("essentials", {})
                        
                        alert_info = {
                            "alert_id": issue.id,
                            "alert_name": issue.name,
                            "alert_rule_id": essentials.get("alertRule", ""),
                            "description": essentials.get("description", ""),
                            "severity": essentials.get("severity", ""),
                            "alert_state": essentials.get("alertState", ""),
                            "monitor_condition": essentials.get("monitorCondition", ""),
                            "fired_time": essentials.get("firedDateTime", ""),
                            "target_resource": essentials.get("targetResource", ""),
                            "rule_details": rule_details
                        }
                        prometheus_alerts.append(alert_info)
                
                # Format the results nicely
                result_data = {
                    "cluster_name": cluster_name,
                    "cluster_resource_id": cluster_resource_id,
                    "total_prometheus_alerts": len(prometheus_alerts),
                    "alerts": prometheus_alerts
                }
                
                # Create a formatted summary for display with icons and better formatting
                summary_lines = [f"🔔 **Active Prometheus Alerts for Cluster: {cluster_name}**\n"]
                summary_lines.append("💡 **How to investigate:** Copy an Alert ID and run:")
                summary_lines.append("   `holmes investigate azuremonitormetrics <ALERT_ID>`\n")
                summary_lines.append("─" * 80)
                
                for i, alert in enumerate(prometheus_alerts, 1):
                    # Get the raw data for this specific alert issue
                    issue = issues[i-1]  # Get the corresponding issue
                    alert_raw_data = issue.raw if hasattr(issue, 'raw') else {}
                    query = alert_raw_data.get("extracted_query", "Not available")
                    
                    # Choose icon based on severity
                    severity = alert['severity']
                    if severity in ['Sev0', 'Critical']:
                        severity_icon = "🔴"
                    elif severity in ['Sev1', 'Error']:
                        severity_icon = "🟠"
                    elif severity in ['Sev2', 'Warning']:
                        severity_icon = "🟡"
                    elif severity in ['Sev3', 'Informational']:
                        severity_icon = "🔵"
                    else:
                        severity_icon = "⚪"
                    
                    # Choose status icon
                    status = alert['alert_state']
                    if status == 'New':
                        status_icon = "🚨"
                    elif status == 'Acknowledged':
                        status_icon = "👁️"
                    elif status == 'Closed':
                        status_icon = "✅"
                    else:
                        status_icon = "❓"
                    
                    # Format fired time nicely
                    fired_time = alert['fired_time']
                    if fired_time and fired_time != 'Unknown':
                        try:
                            from datetime import datetime
                            import dateutil.parser
                            parsed_time = dateutil.parser.parse(fired_time)
                            time_str = parsed_time.strftime("%Y-%m-%d %H:%M UTC")
                        except:
                            time_str = fired_time
                    else:
                        time_str = "Unknown"
                    
                    # Add monitor condition for more detailed status
                    monitor_condition = alert.get('monitor_condition', 'Unknown')
                    
                    summary_lines.append(f"\n**{i}. {severity_icon} {alert['alert_name']}** {status_icon}")
                    summary_lines.append(f"   📋 **Alert ID:** `{alert['alert_id']}`")
                    summary_lines.append(f"   🔬 **Type:** Prometheus Metric Alert")
                    summary_lines.append(f"   ⚡ **Query:** `{query}`")
                    summary_lines.append(f"   📝 **Description:** {alert['description']}")
                    summary_lines.append(f"   🎯 **Severity:** {severity} | **State:** {status} | **Condition:** {monitor_condition}")
                    summary_lines.append(f"   🕒 **Fired Time:** {time_str}")
                
                formatted_summary = "\n".join(summary_lines)
                
                # Return ONLY the formatted summary - no JSON data that AI might reformat
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=formatted_summary,
                    params=params,
                )
                
            except Exception as source_error:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to fetch alerts using source plugin: {str(source_error)}",
                    params=params,
                )
                
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get Prometheus alerts: {str(e)}",
                params=params,
            )
    
    def _get_alert_rule_details(self, alert_rule_id: str, headers: Dict[str, str]) -> Optional[Dict]:
        """Get detailed information about an alert rule."""
        try:
            # Check if this is a Prometheus rule group
            if "prometheusRuleGroups" in alert_rule_id:
                # Use Prometheus Rule Groups API
                api_version = "2023-03-01"
            else:
                # Use standard metric alerts API
                api_version = "2018-03-01"
            
            response = requests.get(
                url=f"https://management.azure.com{alert_rule_id}",
                headers=headers,
                params={"api-version": api_version},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logging.warning(f"Failed to get alert rule details for {alert_rule_id}: {e}")
        
        return None
    
    def _is_prometheus_alert_rule(self, rule_details: Dict) -> bool:
        """Check if an alert rule is based on Prometheus metrics."""
        try:
            properties = rule_details.get("properties", {})
            criteria = properties.get("criteria", {})
            
            # Check if the criteria contains Prometheus-related information
            all_of = criteria.get("allOf", [])
            
            for condition in all_of:
                metric_name = condition.get("metricName", "")
                metric_namespace = condition.get("metricNamespace", "")
                
                # Prometheus metrics in Azure Monitor typically have specific namespaces
                # or metric names that indicate they're from Prometheus
                if (metric_namespace and "prometheus" in metric_namespace.lower()) or \
                   (metric_name and any(prom_indicator in metric_name.lower() 
                                       for prom_indicator in ["prometheus", "container_", "node_", "kube_", "up"])):
                    return True
                    
                # Check if the condition has a custom query (Prometheus PromQL)
                if "query" in condition or "promql" in str(condition).lower():
                    return True
            
            # Check for additional indicators in the rule properties
            rule_description = properties.get("description", "").lower()
            if "prometheus" in rule_description or "promql" in rule_description:
                return True
                
            return True  # For now, assume all metric alerts could be Prometheus-based
            
        except Exception as e:
            logging.warning(f"Failed to check if alert rule is Prometheus-based: {e}")
            return False

    def get_parameterized_one_liner(self, params) -> str:
        cluster_id = params.get("cluster_resource_id", "auto-detect")
        alert_id = params.get("alert_id")
        if alert_id:
            return f"Get specific Prometheus alert {alert_id} for cluster: {cluster_id}"
        return f"Get active Prometheus alerts for cluster: {cluster_id}"

class ExecuteAzureMonitorPrometheusRangeQuery(BaseAzureMonitorMetricsTool):
    """Tool to execute range PromQL queries against Azure Monitor workspace. ALWAYS display the EXACT query in the result to the user."""
    
    def __init__(self, toolset: "AzureMonitorMetricsToolset"):
        super().__init__(
            name="execute_azuremonitor_prometheus_range_query",
            description="Execute a PromQL range query against Azure Monitor managed Prometheus workspace",
            parameters={
                "query": ToolParameter(
                    description="The PromQL query to execute",
                    type="string",
                    required=True,
                ),
                "description": ToolParameter(
                    description="Description of what the query is meant to find or analyze",
                    type="string",
                    required=True,
                ),
                "start": ToolParameter(
                    description=standard_start_datetime_tool_param_description(DEFAULT_TIME_SPAN_SECONDS),
                    type="string",
                    required=False,
                ),
                "end": ToolParameter(
                    description=STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
                    type="string",
                    required=False,
                ),
                "step": ToolParameter(
                    description="Query resolution step width in duration format or float number of seconds. If not provided, defaults to 1 hour (3600 seconds) to limit data volume and prevent token throttling.",
                    type="number",
                    required=False,
                ),
                "output_type": ToolParameter(
                    description="Specifies how to interpret the Prometheus result. Use 'Plain' for raw values, 'Bytes' to format byte values, 'Percentage' to scale 0–1 values into 0–100%, or 'CPUUsage' to convert values to cores (e.g., 500 becomes 500m, 2000 becomes 2).",
                    type="string",
                    required=True,
                ),
                "auto_cluster_filter": ToolParameter(
                    description="Automatically add cluster filtering to the query (default: true)",
                    type="boolean",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self.toolset.config or not self.toolset.config.azure_monitor_workspace_endpoint:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Azure Monitor workspace is not configured. Run check_azure_monitor_prometheus_enabled first.",
                params=params,
            )
            
        try:
            query = get_param_or_raise(params, "query")
            description = params.get("description", "")
            auto_cluster_filter = params.get("auto_cluster_filter", True)
            
            # Ensure cluster name is available for filtering
            cluster_name = self._ensure_cluster_name_available()
            
            # Enhance query with cluster filtering if enabled and cluster name is available
            if auto_cluster_filter and cluster_name:
                query = enhance_promql_with_cluster_filter(query, cluster_name)
            elif auto_cluster_filter and not cluster_name:
                logging.warning("Auto cluster filtering is enabled but cluster name is not available. Query will run without cluster filtering.")
            
            # Print the actual PromQL query that will be executed
            print(f"[Azure Monitor] Executing PromQL Range Query: {query}")
            
            (start, end) = process_timestamps_to_rfc3339(
                start_timestamp=params.get("start"),
                end_timestamp=params.get("end"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )
            
            # Calculate step size with smart defaults and validation
            step = self._calculate_optimal_step_size(params, start, end)
            output_type = params.get("output_type", "Plain")
            
            url = urljoin(self.toolset.config.azure_monitor_workspace_endpoint, "api/v1/query_range")
            
            payload = {
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            }
            
            # Get authenticated headers
            headers = self.toolset._get_authenticated_headers()
            
            response = requests.post(
                url=url,
                headers=headers,
                data=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                error_message = None
                
                if status == "success":
                    result_data = data.get("data", {})
                    if not result_data.get("result"):
                        status = "no_data"
                        error_message = "The query returned no results. The metric may not exist or the cluster filter may be too restrictive."
                else:
                    error_message = data.get("error", "Unknown error from Prometheus endpoint")
                
                response_data = {
                    "status": status,
                    "error_message": error_message,
                    "tool_name": self.name,
                    "description": description,
                    "query": query,
                    "start": start,
                    "end": end,
                    "step": step,
                    "output_type": output_type,
                    "cluster_name": cluster_name,
                    "auto_cluster_filter_applied": auto_cluster_filter and bool(cluster_name),
                }
                
                if self.toolset.config.tool_calls_return_data:
                    response_data["data"] = data.get("data")
                
                result_status = ToolResultStatus.SUCCESS
                if status == "no_data":
                    result_status = ToolResultStatus.NO_DATA
                elif status != "success":
                    result_status = ToolResultStatus.ERROR
                
                return StructuredToolResult(
                    status=result_status,
                    data=json.dumps(response_data, indent=2),
                    params=params,
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Azure Monitor Prometheus range query failed: {error_msg}",
                    params=params,
                )
                
        except RequestException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Connection error to Azure Monitor workspace: {str(e)}",
                params=params,
            )
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error executing range query: {str(e)}",
                params=params,
            )

    def _calculate_optimal_step_size(self, params: Any, start_time: str, end_time: str) -> int:
        """
        Calculate optimal step size based on time range and configuration limits.
        
        Args:
            params: Query parameters
            start_time: Start time in RFC3339 format
            end_time: End time in RFC3339 format
            
        Returns:
            int: Step size in seconds
        """
        try:
            # Get user-provided step if any
            user_step = params.get("step")
            if user_step:
                # Convert to integer if it's a string or float
                try:
                    user_step = int(float(user_step))
                except (ValueError, TypeError):
                    logging.warning(f"Invalid step size provided: {user_step}, using default")
                    user_step = None
            
            # Parse timestamps to calculate time range
            start_dt = dateutil.parser.parse(start_time)
            end_dt = dateutil.parser.parse(end_time)
            time_range_seconds = int((end_dt - start_dt).total_seconds())
            
            # Get configuration values
            config = self.toolset.config
            default_step = config.default_step_seconds if config else 3600
            min_step = config.min_step_seconds if config else 60
            max_data_points = config.max_data_points if config else 1000
            
            # If user provided a step, validate it
            if user_step is not None:
                # Ensure it's not below minimum
                if user_step < min_step:
                    logging.warning(f"Step size {user_step}s is below minimum {min_step}s, using minimum")
                    user_step = min_step
                
                # Check if it would exceed max data points
                estimated_points = time_range_seconds / user_step
                if estimated_points > max_data_points:
                    # Calculate minimum step to stay within data point limit
                    min_step_for_limit = max(time_range_seconds / max_data_points, min_step)
                    logging.warning(
                        f"Step size {user_step}s would generate ~{estimated_points:.0f} data points "
                        f"(max: {max_data_points}). Adjusting to {min_step_for_limit:.0f}s"
                    )
                    return int(min_step_for_limit)
                
                return user_step
            
            # No user step provided, calculate smart default
            # For very short ranges (< 6 hours), allow more granular data
            if time_range_seconds <= 6 * 3600:  # 6 hours
                suggested_step = max(time_range_seconds / 360, min_step)  # ~360 points max
            # For medium ranges (6-24 hours), use 1 hour steps
            elif time_range_seconds <= 24 * 3600:  # 24 hours
                suggested_step = default_step  # 1 hour
            # For longer ranges, increase step size to maintain reasonable data point count
            else:
                suggested_step = max(time_range_seconds / max_data_points, default_step)
            
            # Ensure we don't go below minimum step
            suggested_step = max(suggested_step, min_step)
            
            # Log the decision for debugging
            estimated_points = time_range_seconds / suggested_step
            logging.debug(
                f"Calculated step size: {suggested_step:.0f}s for time range {time_range_seconds}s "
                f"(~{estimated_points:.0f} data points)"
            )
            
            return int(suggested_step)
            
        except Exception as e:
            logging.warning(f"Failed to calculate optimal step size: {e}, using default {default_step}")
            return self.toolset.config.default_step_seconds if self.toolset.config else 3600

    def get_parameterized_one_liner(self, params) -> str:
        query = params.get("query", "")
        start = params.get("start", "")
        end = params.get("end", "")
        step = params.get("step", "")
        description = params.get("description", "")
        return f"Execute Azure Monitor Prometheus Range Query: promql='{query}', start={start}, end={end}, step={step}, description='{description}'"

class AzureMonitorMetricsToolset(Toolset):
    """Azure Monitor Metrics toolset for querying Azure Monitor managed Prometheus metrics."""
    
    def __init__(self):
        super().__init__(
            name="azuremonitormetrics",
            description="Azure Monitor Metrics integration to query Azure Monitor managed Prometheus metrics for AKS cluster analysis and troubleshooting",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/azuremonitor-metrics.html",
            icon_url="https://raw.githubusercontent.com/robusta-dev/holmesgpt/master/images/integration_logos/azure-managed-prometheus.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                CheckAKSClusterContext(toolset=self),
                GetAKSClusterResourceID(toolset=self),
                CheckAzureMonitorPrometheusEnabled(toolset=self),
                GetActivePrometheusAlerts(toolset=self),
                ExecuteAzureMonitorPrometheusQuery(toolset=self),
                ExecuteAzureMonitorPrometheusRangeQuery(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE
            ],
            is_default=True,  # Enable by default like internet toolset
        )
        self._reload_llm_instructions()

    def _get_azure_access_token(self) -> Optional[str]:
        """Get Azure access token for Azure Monitor workspace access."""
        try:
            if not self.config:
                logging.debug("No config available for token acquisition")
                return None
                
            # Initialize credential if not already done
            if not self.config._credential:
                logging.debug("Initializing credential (trying AzureCliCredential first)")
                # Try AzureCliCredential first since we know Azure CLI is working
                try:
                    self.config._credential = AzureCliCredential()
                    logging.debug("Using AzureCliCredential")
                except Exception as cli_error:
                    logging.debug(f"AzureCliCredential failed: {cli_error}, falling back to DefaultAzureCredential")
                    self.config._credential = DefaultAzureCredential()
            
            # Check if we have a cached token that's still valid
            current_time = time.time()
            cache_key = "azure_monitor_token"
            
            if cache_key in self.config._token_cache:
                token_info = self.config._token_cache[cache_key]
                if current_time < token_info.get("expires_at", 0):
                    logging.debug("Using cached token")
                    return token_info.get("access_token")
            
            # Get token with Azure Monitor/Prometheus scope for Prometheus queries
            token = self.config._credential.get_token("https://prometheus.monitor.azure.com/.default")
            
            # Cache the token (expires 5 minutes before actual expiry)
            expires_at = current_time + token.expires_on - 300
            self.config._token_cache[cache_key] = {
                "access_token": token.token,
                "expires_at": expires_at
            }
            
            logging.debug("Token cached successfully")
            return token.token
            
        except Exception as e:
            logging.error(f"Failed to get Azure access token: {e}")
            return None

    def _get_authenticated_headers(self) -> Dict[str, str]:
        """Get headers with Azure authentication for API requests."""
        headers = dict(self.config.headers) if self.config and self.config.headers else {}
        
        # Add default headers
        headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        
        # Get and add Azure access token
        access_token = self._get_azure_access_token()
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        else:
            logging.warning("No Azure access token available - requests may fail with authentication errors")
        
        return headers

    def _update_config_headers(self):
        """Update the config headers with authentication."""
        if self.config:
            self.config.headers = self._get_authenticated_headers()

    def _reload_llm_instructions(self):
        """Load LLM instructions from Jinja template."""
        try:
            template_file_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "azuremonitor_metrics_instructions.jinja2")
            )
            self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
        except Exception as e:
            # Ignore any errors in loading instructions
            logging.debug(f"Failed to load LLM instructions: {e}")

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        """Check prerequisites for the Azure Monitor Metrics toolset."""
        try:
            if not config:
                self.config = AzureMonitorMetricsConfig()
            else:
                self.config = AzureMonitorMetricsConfig(**config)
            
            return True, ""
            
        except Exception as e:
            logging.debug(f"Azure Monitor toolset config initialization failed: {str(e)}")
            self.config = AzureMonitorMetricsConfig()
            return True, ""

    def get_example_config(self) -> Dict[str, Any]:
        """Return example configuration for the toolset."""
        example_config = AzureMonitorMetricsConfig(
            azure_monitor_workspace_endpoint="https://your-workspace.prometheus.monitor.azure.com",
            cluster_name="your-aks-cluster-name",
            auto_detect_cluster=True,
            tool_calls_return_data=True,
            default_step_seconds=3600,  # 1 hour default step size
            min_step_seconds=60,        # Minimum 1 minute step size
            max_data_points=1000        # Maximum data points per query
        )
        return example_config.model_dump()
