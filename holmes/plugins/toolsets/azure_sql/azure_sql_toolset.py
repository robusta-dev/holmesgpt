import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone

import yaml
from pydantic import BaseModel, ConfigDict
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.credentials import TokenCredential

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import TOOLSET_CONFIG_MISSING_ERROR
from holmes.plugins.toolsets.utils import get_param_or_raise
from holmes.plugins.toolsets.azure_sql.azure_sql_api import AzureSQLAPIClient


class AzureSQLDatabaseConfig(BaseModel):
    name: str
    subscription_id: str
    resource_group: str
    server_name: str
    database_name: str


class AzureSQLConfig(BaseModel):
    azure_sql_databases: List[AzureSQLDatabaseConfig]
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None



class BaseAzureSQLTool(Tool):
    toolset: "AzureSQLToolset"

    def get_database_config(self, database_name: str) -> AzureSQLDatabaseConfig:
        """
        Retrieves the database configuration based on the database name.
        """
        if database_name not in self.toolset.database_configs:
            raise Exception(f"Database configuration not found: {database_name}")
        return self.toolset.database_configs[database_name]


class GenerateHealthReport(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="generate_health_report",
            description="Generates a comprehensive health report for an Azure SQL database including operations, usage, and overall status",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the Azure SQL database to investigate",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _gather_health_data(self, db_config: AzureSQLDatabaseConfig, client: AzureSQLAPIClient) -> Dict:
        """Gather health-related data from Azure SQL API."""
        health_data = {
            "database_info": {
                "name": db_config.database_name,
                "server": db_config.server_name,
                "resource_group": db_config.resource_group,
                "subscription_id": db_config.subscription_id
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            operations = client.get_database_operations(
                db_config.subscription_id, db_config.resource_group, 
                db_config.server_name, db_config.database_name
            )
            health_data["operations"] = operations.get("value", [])
        except Exception as e:
            health_data["operations_error"] = str(e)
        
        try:
            usages = client.get_database_usages(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name
            )
            health_data["resource_usage"] = usages.get("value", [])
        except Exception as e:
            health_data["usage_error"] = str(e)
        
        return health_data

    def _build_health_report(self, health_data: Dict, db_config: AzureSQLDatabaseConfig) -> str:
        """Build the formatted health report from gathered data."""
        report_sections = []
        
        # Database Overview Section
        report_sections.append("# Azure SQL Database Health Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Generated:** {health_data['timestamp']}")
        report_sections.append("")
        
        # Operations Status Section
        report_sections.append("## Operations Status")
        if "operations_error" in health_data:
            report_sections.append(f"⚠️ **Error retrieving operations:** {health_data['operations_error']}")
        else:
            operations = health_data.get("operations", [])
            if operations:
                report_sections.append(f"**Active Operations:** {len(operations)}")
                for op in operations[:5]:  # Show first 5 operations
                    status = op.get("properties", {}).get("state", "Unknown")
                    op_type = op.get("properties", {}).get("operation", "Unknown")
                    start_time = op.get("properties", {}).get("startTime", "Unknown")
                    report_sections.append(f"- **{op_type}**: {status} (Started: {start_time})")
            else:
                report_sections.append("✅ **No active operations**")
        report_sections.append("")
        
        # Resource Usage Section
        report_sections.append("## Resource Usage")
        if "usage_error" in health_data:
            report_sections.append(f"⚠️ **Error retrieving usage data:** {health_data['usage_error']}")
        else:
            usages = health_data.get("resource_usage", [])
            if usages:
                for usage in usages:
                    name = usage.get("displayName", "Unknown Metric")
                    current = usage.get("currentValue", 0)
                    limit = usage.get("limit", 0)
                    unit = usage.get("unit", "")
                    
                    if limit > 0:
                        percentage = (current / limit) * 100
                        status_icon = "🔴" if percentage > 90 else "🟡" if percentage > 70 else "🟢"
                        report_sections.append(f"- **{name}**: {status_icon} {current:,} / {limit:,} {unit} ({percentage:.1f}%)")
                    else:
                        report_sections.append(f"- **{name}**: {current:,} {unit}")
            else:
                report_sections.append("No usage data available")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            database_name = get_param_or_raise(params, "database_name")
            db_config = self.get_database_config(database_name)
            client = self.toolset.api_clients[db_config.subscription_id]
            
            # Gather health-related data
            health_data = self._gather_health_data(db_config, client)
            
            # Build the formatted report
            report_text = self._build_health_report(health_data, db_config)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to generate health report: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Generated health report for database {params['database_name']}"


class GeneratePerformanceReport(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="generate_performance_report",
            description="Generates a comprehensive performance report including advisors, recommendations, and automatic tuning status",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the Azure SQL database to investigate",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _gather_performance_data(self, db_config: AzureSQLDatabaseConfig, client: AzureSQLAPIClient) -> Dict:
        """Gather performance-related data from Azure SQL API."""
        performance_data = {
            "database_info": {
                "name": db_config.database_name,
                "server": db_config.server_name,
                "resource_group": db_config.resource_group
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            advisors = client.get_database_advisors(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name
            )
            performance_data["advisors"] = advisors.get("value", [])
        except Exception as e:
            performance_data["advisors_error"] = str(e)
        
        try:
            auto_tuning = client.get_database_automatic_tuning(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name
            )
            performance_data["automatic_tuning"] = auto_tuning
        except Exception as e:
            performance_data["auto_tuning_error"] = str(e)
        
        # Get recommendations for each advisor
        performance_data["recommendations"] = []
        if "advisors" in performance_data:
            for advisor in performance_data["advisors"]:
                advisor_name = advisor.get("name", "")
                try:
                    recommendations = client.get_database_recommended_actions(
                        db_config.subscription_id, db_config.resource_group,
                        db_config.server_name, db_config.database_name, advisor_name
                    )
                    performance_data["recommendations"].extend(recommendations.get("value", []))
                except Exception as e:
                    logging.warning(f"Failed to get recommendations for advisor {advisor_name}: {e}")
        
        return performance_data

    def _build_performance_report(self, performance_data: Dict, db_config: AzureSQLDatabaseConfig) -> str:
        """Build the formatted performance report from gathered data."""
        report_sections = []
        
        # Performance Report Header
        report_sections.append("# Azure SQL Database Performance Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Generated:** {performance_data['timestamp']}")
        report_sections.append("")
        
        # Automatic Tuning Section
        report_sections.append("## Automatic Tuning Status")
        if "auto_tuning_error" in performance_data:
            report_sections.append(f"⚠️ **Error retrieving auto-tuning data:** {performance_data['auto_tuning_error']}")
        else:
            auto_tuning = performance_data.get("automatic_tuning", {})
            properties = auto_tuning.get("properties", {})
            desired_state = properties.get("desiredState", "Unknown")
            actual_state = properties.get("actualState", "Unknown")
            
            status_icon = "✅" if desired_state == actual_state else "⚠️"
            report_sections.append(f"- **Desired State**: {desired_state}")
            report_sections.append(f"- **Actual State**: {actual_state} {status_icon}")
            
            options = properties.get("options", {})
            for option_name, option_data in options.items():
                desired = option_data.get("desiredState", "Unknown")
                actual = option_data.get("actualState", "Unknown")
                option_icon = "✅" if desired == actual else "⚠️"
                report_sections.append(f"  - **{option_name}**: {actual} {option_icon}")
        report_sections.append("")
        
        # Performance Advisors Section
        report_sections.append("## Performance Advisors")
        if "advisors_error" in performance_data:
            report_sections.append(f"⚠️ **Error retrieving advisors:** {performance_data['advisors_error']}")
        else:
            advisors = performance_data.get("advisors", [])
            if advisors:
                for advisor in advisors:
                    name = advisor.get("name", "Unknown")
                    properties = advisor.get("properties", {})
                    auto_execute = properties.get("autoExecuteStatus", "Unknown")
                    last_checked = properties.get("lastChecked", "Never")
                    
                    report_sections.append(f"### {name}")
                    report_sections.append(f"- **Auto Execute**: {auto_execute}")
                    report_sections.append(f"- **Last Checked**: {last_checked}")
            else:
                report_sections.append("No performance advisors available")
        report_sections.append("")
        
        # Recommendations Section
        report_sections.append("## Performance Recommendations")
        recommendations = performance_data.get("recommendations", [])
        if recommendations:
            active_recommendations = [r for r in recommendations if r.get("properties", {}).get("state", {}).get("currentValue") in ["Active", "Pending"]]
            
            if active_recommendations:
                report_sections.append(f"🚨 **{len(active_recommendations)} Active Recommendations Found**")
                for rec in active_recommendations[:5]:  # Show first 5 recommendations
                    properties = rec.get("properties", {})
                    details = properties.get("details", {})
                    
                    rec_type = details.get("indexType", "Performance")
                    impact = details.get("impactDetails", [{}])[0].get("name", "Unknown")
                    state = properties.get("state", {}).get("currentValue", "Unknown")
                    
                    report_sections.append(f"- **{rec_type} Recommendation**: {impact} impact ({state})")
                    
                    if "indexColumns" in details:
                        columns = ", ".join(details["indexColumns"])
                        report_sections.append(f"  - **Columns**: {columns}")
            else:
                report_sections.append("✅ **No active performance recommendations**")
        else:
            report_sections.append("No performance recommendations available")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            database_name = get_param_or_raise(params, "database_name")
            db_config = self.get_database_config(database_name)
            client = self.toolset.api_clients[db_config.subscription_id]
            
            # Gather performance-related data
            performance_data = self._gather_performance_data(db_config, client)
            
            # Build the formatted report
            report_text = self._build_performance_report(performance_data, db_config)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to generate performance report: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Generated performance report for database {params['database_name']}"


class GenerateSecurityReport(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="generate_security_report",
            description="Generates a comprehensive security report including vulnerability assessments, security alerts, and threat detection status",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the Azure SQL database to investigate",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _gather_security_data(self, db_config: AzureSQLDatabaseConfig, client: AzureSQLAPIClient) -> Dict:
        """Gather security-related data from Azure SQL API."""
        security_data = {
            "database_info": {
                "name": db_config.database_name,
                "server": db_config.server_name,
                "resource_group": db_config.resource_group
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            vulnerability_assessments = client.get_database_vulnerability_assessments(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name
            )
            security_data["vulnerability_assessments"] = vulnerability_assessments.get("value", [])
        except Exception as e:
            security_data["vulnerability_error"] = str(e)
        
        try:
            security_alerts = client.get_database_security_alert_policies(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name
            )
            security_data["security_alert_policies"] = security_alerts.get("value", [])
        except Exception as e:
            security_data["security_alerts_error"] = str(e)
        
        return security_data

    def _build_security_report(self, security_data: Dict, db_config: AzureSQLDatabaseConfig) -> str:
        """Build the formatted security report from gathered data."""
        report_sections = []
        
        # Security Report Header
        report_sections.append("# Azure SQL Database Security Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Generated:** {security_data['timestamp']}")
        report_sections.append("")
        
        # Security Alert Policies Section
        report_sections.append("## Security Alert Policies")
        if "security_alerts_error" in security_data:
            report_sections.append(f"⚠️ **Error retrieving security alerts:** {security_data['security_alerts_error']}")
        else:
            alert_policies = security_data.get("security_alert_policies", [])
            if alert_policies:
                for policy in alert_policies:
                    properties = policy.get("properties", {})
                    state = properties.get("state", "Unknown")
                    policy_name = policy.get("name", "Default")
                    
                    status_icon = "✅" if state == "Enabled" else "⚠️" if state == "Disabled" else "❓"
                    report_sections.append(f"- **{policy_name} Policy**: {state} {status_icon}")
                    
                    # Show enabled detection types
                    disabled_alerts = properties.get("disabledAlerts", [])
                    email_addresses = properties.get("emailAddresses", [])
                    
                    if state == "Enabled":
                        if email_addresses:
                            report_sections.append(f"  - **Email Recipients**: {', '.join(email_addresses)}")
                        if disabled_alerts:
                            report_sections.append(f"  - **Disabled Alert Types**: {', '.join(disabled_alerts)}")
                        else:
                            report_sections.append("  - **All Alert Types**: Enabled")
            else:
                report_sections.append("⚠️ **No security alert policies configured**")
        report_sections.append("")
        
        # Vulnerability Assessments Section
        report_sections.append("## Vulnerability Assessments")
        if "vulnerability_error" in security_data:
            report_sections.append(f"⚠️ **Error retrieving vulnerability assessments:** {security_data['vulnerability_error']}")
        else:
            vulnerability_assessments = security_data.get("vulnerability_assessments", [])
            if vulnerability_assessments:
                for assessment in vulnerability_assessments:
                    properties = assessment.get("properties", {})
                    scan_trigger_type = properties.get("scanTriggerType", "Unknown")
                    
                    report_sections.append(f"- **Vulnerability Assessment**: Configured")
                    report_sections.append(f"  - **Scan Trigger**: {scan_trigger_type}")
                    
                    # Check if recurring scans are enabled
                    recurring_scans = properties.get("recurringScans", {})
                    if recurring_scans:
                        is_enabled = recurring_scans.get("isEnabled", False)
                        email_subscription_admins = recurring_scans.get("emailSubscriptionAdmins", False)
                        emails = recurring_scans.get("emails", [])
                        
                        scan_icon = "✅" if is_enabled else "⚠️"
                        report_sections.append(f"  - **Recurring Scans**: {'Enabled' if is_enabled else 'Disabled'} {scan_icon}")
                        
                        if is_enabled:
                            if email_subscription_admins or emails:
                                report_sections.append("  - **Email Notifications**: Configured")
                            else:
                                report_sections.append("  - **Email Notifications**: ⚠️ Not configured")
            else:
                report_sections.append("⚠️ **No vulnerability assessments configured**")
                report_sections.append("  - Consider enabling vulnerability assessments for security monitoring")
        report_sections.append("")
        
        # Security Recommendations Section
        report_sections.append("## Security Recommendations")
        recommendations = []
        
        # Check if security monitoring is properly configured
        alert_policies = security_data.get("security_alert_policies", [])
        vulnerability_assessments = security_data.get("vulnerability_assessments", [])
        
        if not alert_policies or not any(p.get("properties", {}).get("state") == "Enabled" for p in alert_policies):
            recommendations.append("⚠️ Enable security alert policies for threat detection")
        
        if not vulnerability_assessments:
            recommendations.append("⚠️ Configure vulnerability assessments for security scanning")
        
        if not recommendations:
            report_sections.append("✅ **Security configuration appears to be properly set up**")
        else:
            for rec in recommendations:
                report_sections.append(f"- {rec}")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            database_name = get_param_or_raise(params, "database_name")
            db_config = self.get_database_config(database_name)
            client = self.toolset.api_clients[db_config.subscription_id]
            
            # Gather security-related data
            security_data = self._gather_security_data(db_config, client)
            
            # Build the formatted report
            report_text = self._build_security_report(security_data, db_config)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to generate security report: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Generated security report for database {params['database_name']}"


class GetTopCPUQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="get_top_cpu_queries",
            description="Gets the top CPU consuming queries from Query Store for performance analysis",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the Azure SQL database to investigate",
                    type="string",
                    required=True,
                ),
                "top_count": ToolParameter(
                    description="Number of top queries to return (default: 15)",
                    type="integer",
                    required=False,
                ),
                "hours_back": ToolParameter(
                    description="Number of hours back to analyze (default: 2)",
                    type="integer", 
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _format_cpu_queries_report(self, queries: List[Dict], db_config: AzureSQLDatabaseConfig, 
                                 top_count: int, hours_back: int) -> str:
        """Format the CPU queries data into a readable report."""
        report_sections = []
        
        # Header
        report_sections.append("# Top CPU Consuming Queries Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Analysis Period:** Last {hours_back} hours")
        report_sections.append(f"**Top Queries:** {top_count}")
        report_sections.append("")
        
        if not queries:
            report_sections.append("No queries found for the specified time period.")
            return "\n".join(report_sections)
        
        # Summary
        total_cpu_time = sum(float(q.get('total_cpu_time', 0)) for q in queries)
        total_executions = sum(int(q.get('execution_count', 0)) for q in queries)
        
        report_sections.append("## Summary")
        report_sections.append(f"- **Total Queries Analyzed:** {len(queries)}")
        report_sections.append(f"- **Total CPU Time:** {total_cpu_time:,.0f} microseconds")
        report_sections.append(f"- **Total Executions:** {total_executions:,}")
        report_sections.append("")
        
        # Query Details
        report_sections.append("## Query Details")
        
        for i, query in enumerate(queries[:top_count], 1):
            avg_cpu = float(query.get('avg_cpu_time', 0))
            execution_count = int(query.get('execution_count', 0))
            total_cpu = float(query.get('total_cpu_time', 0))
            max_cpu = float(query.get('max_cpu_time', 0))
            avg_duration = float(query.get('avg_duration', 0))
            query_text = query.get('query_sql_text', 'N/A')
            last_execution = query.get('last_execution_time', 'N/A')
            
            # Truncate long queries
            if len(query_text) > 200:
                query_text = query_text[:200] + "..."
            
            report_sections.append(f"### Query #{i}")
            report_sections.append(f"- **Average CPU Time:** {avg_cpu:,.0f} μs")
            report_sections.append(f"- **Total CPU Time:** {total_cpu:,.0f} μs")
            report_sections.append(f"- **Max CPU Time:** {max_cpu:,.0f} μs")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(f"- **Average Duration:** {avg_duration:,.0f} μs")
            report_sections.append(f"- **Last Execution:** {last_execution}")
            report_sections.append(f"- **Query Text:**")
            report_sections.append(f"```sql")
            report_sections.append(query_text)
            report_sections.append("```")
            report_sections.append("")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            database_name = get_param_or_raise(params, "database_name")
            top_count = params.get("top_count", 15)
            hours_back = params.get("hours_back", 2)
            
            db_config = self.get_database_config(database_name)
            client = self.toolset.api_clients[db_config.subscription_id]
            
            # Get top CPU queries
            queries = client.get_top_cpu_queries(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name,
                top_count, hours_back
            )
            
            # Format the report
            report_text = self._format_cpu_queries_report(queries, db_config, top_count, hours_back)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to get top CPU queries: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Retrieved top CPU consuming queries for database {params['database_name']}"


class GetSlowQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="get_slow_queries",
            description="Gets the slowest/longest-running queries from Query Store for performance analysis",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the Azure SQL database to investigate",
                    type="string",
                    required=True,
                ),
                "top_count": ToolParameter(
                    description="Number of top queries to return (default: 15)",
                    type="integer",
                    required=False,
                ),
                "hours_back": ToolParameter(
                    description="Number of hours back to analyze (default: 2)",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _format_slow_queries_report(self, queries: List[Dict], db_config: AzureSQLDatabaseConfig,
                                  top_count: int, hours_back: int) -> str:
        """Format the slow queries data into a readable report."""
        report_sections = []
        
        # Header
        report_sections.append("# Slowest/Longest-Running Queries Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Analysis Period:** Last {hours_back} hours")
        report_sections.append(f"**Top Queries:** {top_count}")
        report_sections.append("")
        
        if not queries:
            report_sections.append("No queries found for the specified time period.")
            return "\n".join(report_sections)
        
        # Summary
        total_duration = sum(float(q.get('total_duration', 0)) for q in queries)
        total_executions = sum(int(q.get('execution_count', 0)) for q in queries)
        
        report_sections.append("## Summary")
        report_sections.append(f"- **Total Queries Analyzed:** {len(queries)}")
        report_sections.append(f"- **Total Duration:** {total_duration:,.0f} microseconds")
        report_sections.append(f"- **Total Executions:** {total_executions:,}")
        report_sections.append("")
        
        # Query Details
        report_sections.append("## Query Details")
        
        for i, query in enumerate(queries[:top_count], 1):
            avg_duration = float(query.get('avg_duration', 0))
            execution_count = int(query.get('execution_count', 0))
            total_duration = float(query.get('total_duration', 0))
            max_duration = float(query.get('max_duration', 0))
            avg_cpu = float(query.get('avg_cpu_time', 0))
            query_text = query.get('query_sql_text', 'N/A')
            last_execution = query.get('last_execution_time', 'N/A')
            
            # Truncate long queries
            if len(query_text) > 200:
                query_text = query_text[:200] + "..."
            
            report_sections.append(f"### Query #{i}")
            report_sections.append(f"- **Average Duration:** {avg_duration:,.0f} μs")
            report_sections.append(f"- **Total Duration:** {total_duration:,.0f} μs")
            report_sections.append(f"- **Max Duration:** {max_duration:,.0f} μs")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(f"- **Average CPU Time:** {avg_cpu:,.0f} μs")
            report_sections.append(f"- **Last Execution:** {last_execution}")
            report_sections.append(f"- **Query Text:**")
            report_sections.append(f"```sql")
            report_sections.append(query_text)
            report_sections.append("```")
            report_sections.append("")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            database_name = get_param_or_raise(params, "database_name")
            top_count = params.get("top_count", 15)
            hours_back = params.get("hours_back", 2)
            
            db_config = self.get_database_config(database_name)
            client = self.toolset.api_clients[db_config.subscription_id]
            
            # Get slow queries
            queries = client.get_slow_queries(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name,
                top_count, hours_back
            )
            
            # Format the report
            report_text = self._format_slow_queries_report(queries, db_config, top_count, hours_back)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to get slow queries: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Retrieved slowest queries for database {params['database_name']}"


class ListAzureSQLDatabases(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="list_azure_sql_databases",
            description="Lists all available Azure SQL databases configured in HolmesGPT",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        database_names = list(self.toolset.database_configs.keys())
        database_details = []
        
        for name, config in self.toolset.database_configs.items():
            database_details.append({
                "name": name,
                "database": config.database_name,
                "server": config.server_name,
                "resource_group": config.resource_group,
                "subscription_id": config.subscription_id
            })
        
        report = "# Available Azure SQL Databases\n\n"
        for db in database_details:
            report += f"## {db['name']}\n"
            report += f"- **Database**: {db['database']}\n"
            report += f"- **Server**: {db['server']}\n"
            report += f"- **Resource Group**: {db['resource_group']}\n"
            report += f"- **Subscription**: {db['subscription_id']}\n\n"
        
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=report,
            params=params,
        )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Listed all available Azure SQL databases"


class AzureSQLToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    api_clients: Dict[str, AzureSQLAPIClient] = {}
    database_configs: Dict[str, AzureSQLDatabaseConfig] = {}

    def __init__(self):
        super().__init__(
            name="azure-sql",
            description="Monitors Azure SQL Database performance, health, and security using Azure REST APIs",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/azure-sql.html",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Azure_SQL_Database_logo.svg/1200px-Azure_SQL_Database_logo.svg.png",
            tags=[ToolsetTag.CORE],
            tools=[
                ListAzureSQLDatabases(self),
                GenerateHealthReport(self),
                GeneratePerformanceReport(self),
                GenerateSecurityReport(self),
                GetTopCPUQueries(self),
                GetSlowQueries(self),
            ],
        )

    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR
        
        errors = []
        try:
            azure_sql_config = AzureSQLConfig(**config)

            # Set up Azure credentials
            try:
                if azure_sql_config.tenant_id and azure_sql_config.client_id and azure_sql_config.client_secret:
                    credential = ClientSecretCredential(
                        tenant_id=azure_sql_config.tenant_id,
                        client_id=azure_sql_config.client_id,
                        client_secret=azure_sql_config.client_secret
                    )
                    logging.info("Using ClientSecretCredential for Azure authentication")
                else:
                    credential = DefaultAzureCredential()
                    logging.info("Using DefaultAzureCredential for Azure authentication")
                
                # Test the credential by attempting to get a token
                test_token = credential.get_token("https://management.azure.com/.default")
                if not test_token.token:
                    raise Exception("Failed to obtain Azure access token")
                    
            except Exception as e:
                message = f"Failed to set up Azure authentication: {str(e)}"
                logging.error(message)
                errors.append(message)
                return False, message
            
            # Store database configurations and create API clients per subscription
            subscription_ids = set()
            for db_config in azure_sql_config.azure_sql_databases:
                self.database_configs[db_config.name] = db_config
                subscription_ids.add(db_config.subscription_id)
                logging.info(f"Configured Azure SQL database: {db_config.name}")
            
            # Create API clients for each unique subscription
            for subscription_id in subscription_ids:
                self.api_clients[subscription_id] = AzureSQLAPIClient(credential, subscription_id)
                logging.info(f"Created API client for subscription: {subscription_id}")

            return len(self.database_configs) > 0, "\n".join(errors)
        except Exception as e:
            logging.exception("Failed to set up Azure SQL toolset")
            return False, str(e)

    def get_example_config(self) -> Dict[str, Any]:
        example_config = AzureSQLConfig(
            tenant_id="{{ env.AZURE_TENANT_ID }}",
            client_id="{{ env.AZURE_CLIENT_ID }}",
            client_secret="{{ env.AZURE_CLIENT_SECRET }}",
            azure_sql_databases=[
                AzureSQLDatabaseConfig(
                    name="production-db",
                    subscription_id="12345678-1234-1234-1234-123456789012",
                    resource_group="my-resource-group",
                    server_name="myserver",
                    database_name="mydatabase",
                ),
                AzureSQLDatabaseConfig(
                    name="staging-db",
                    subscription_id="12345678-1234-1234-1234-123456789012",
                    resource_group="my-staging-rg",
                    server_name="mystaging-server",
                    database_name="staging-db",
                ),
            ]
        )
        return example_config.model_dump()


