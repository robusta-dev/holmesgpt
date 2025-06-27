import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

import yaml
from pydantic import BaseModel, ConfigDict
from azure.identity import DefaultAzureCredential, ClientSecretCredential

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
from holmes.plugins.toolsets.azure_sql.azure_sql_api import AzureSQLAPIClient
from holmes.plugins.toolsets.azure_sql.connection_monitoring_api import ConnectionMonitoringAPI
from holmes.plugins.toolsets.azure_sql.storage_analysis_api import StorageAnalysisAPI


class AzureSQLDatabaseConfig(BaseModel):
    subscription_id: str
    resource_group: str
    server_name: str
    database_name: str


class AzureSQLConfig(BaseModel):
    database: AzureSQLDatabaseConfig
    tenant_id: str
    client_id: str
    client_secret: str



def _format_timing(microseconds: float) -> str:
    """Format timing values with appropriate units (seconds, milliseconds, microseconds)."""
    if microseconds >= 1_000_000:  # >= 1 second
        return f"{microseconds / 1_000_000:.2f} s"
    elif microseconds >= 1_000:  # >= 1 millisecond
        return f"{microseconds / 1_000:.2f} ms"
    else:  # < 1 millisecond
        return f"{microseconds:.0f} μs"


class BaseAzureSQLTool(Tool):
    toolset: "AzureSQLToolset"


class GenerateHealthReport(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="generate_health_report",
            description="Generates a comprehensive health report for an Azure SQL database including operations, usage, and overall status",
            parameters={},
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
                    name = usage.get("display_name", usage.get("displayName", "Unknown Metric"))
                    current = usage.get("current_value", usage.get("currentValue", 0))
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
            db_config = self.toolset.database_config()
            client = self.toolset.api_client()
            
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
        db_config = self.toolset.database_config()
        return f"Generated health report for database {db_config.server_name}/{db_config.database_name}"

class GeneratePerformanceReport(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="generate_performance_report",
            description="Generates a comprehensive performance report including advisors, recommendations, and automatic tuning status",
            parameters={},
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
            # Handle both camelCase and snake_case field names
            desired_state = auto_tuning.get("desired_state", auto_tuning.get("desiredState", "Unknown"))
            actual_state = auto_tuning.get("actual_state", auto_tuning.get("actualState", "Unknown"))
            
            status_icon = "✅" if desired_state == actual_state else "⚠️"
            report_sections.append(f"- **Desired State**: {desired_state}")
            report_sections.append(f"- **Actual State**: {actual_state} {status_icon}")
            
            options = auto_tuning.get("options", {})
            for option_name, option_data in options.items():
                desired = option_data.get("desired_state", option_data.get("desiredState", "Unknown"))
                actual = option_data.get("actual_state", option_data.get("actualState", "Unknown"))
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
                    # Handle both camelCase and snake_case field names
                    auto_execute = advisor.get("auto_execute_status", advisor.get("autoExecuteStatus", "Unknown"))
                    last_checked = advisor.get("last_checked", advisor.get("lastChecked", "Never"))
                    
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
            db_config = self.toolset.database_config()
            client = self.toolset.api_client()
            
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
        db_config = self.toolset.database_config()
        return f"Generated performance report for database {db_config.server_name}/{db_config.database_name}"

class GetTopCPUQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="get_top_cpu_queries",
            description="Gets the top CPU consuming queries from Query Store for performance analysis",
            parameters={
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
        report_sections.append(f"- **Total CPU Time:** {_format_timing(total_cpu_time)}")
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
            report_sections.append(f"- **Average CPU Time:** {_format_timing(avg_cpu)}")
            report_sections.append(f"- **Total CPU Time:** {_format_timing(total_cpu)}")
            report_sections.append(f"- **Max CPU Time:** {_format_timing(max_cpu)}")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(f"- **Average Duration:** {_format_timing(avg_duration)}")
            report_sections.append(f"- **Last Execution:** {last_execution}")
            report_sections.append("- **Query Text:**")
            report_sections.append("```sql")
            report_sections.append(query_text)
            report_sections.append("```")
            report_sections.append("")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            top_count = params.get("top_count", 15)
            hours_back = params.get("hours_back", 2)
            
            db_config = self.toolset.database_config()
            client = self.toolset.api_client()
            
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
        db_config = self.toolset.database_config()
        return f"Retrieved top CPU consuming queries for database {db_config.server_name}/{db_config.database_name}"


class GetSlowQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="get_slow_queries",
            description="Gets the slowest/longest-running queries from Query Store for performance analysis",
            parameters={
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
        report_sections.append(f"- **Total Duration:** {_format_timing(total_duration)}")
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
            report_sections.append(f"- **Average Duration:** {_format_timing(avg_duration)}")
            report_sections.append(f"- **Total Duration:** {_format_timing(total_duration)}")
            report_sections.append(f"- **Max Duration:** {_format_timing(max_duration)}")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(f"- **Average CPU Time:** {_format_timing(avg_cpu)}")
            report_sections.append(f"- **Last Execution:** {last_execution}")
            report_sections.append("- **Query Text:**")
            report_sections.append("```sql")
            report_sections.append(query_text)
            report_sections.append("```")
            report_sections.append("")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            top_count = params.get("top_count", 15)
            hours_back = params.get("hours_back", 2)
            
            db_config = self.toolset.database_config()
            client = self.toolset.api_client()
            
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
        db_config = self.toolset.database_config()
        return f"Retrieved slowest queries for database {db_config.server_name}/{db_config.database_name}"


class GetTopDataIOQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="get_top_data_io_queries",
            description="Gets the top data I/O consuming queries from Query Store for storage performance analysis",
            parameters={
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

    def _format_data_io_queries_report(self, queries: List[Dict], db_config: AzureSQLDatabaseConfig, 
                                     top_count: int, hours_back: int) -> str:
        """Format the data I/O queries data into a readable report."""
        report_sections = []
        
        # Header
        report_sections.append("# Top Data I/O Consuming Queries Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Analysis Period:** Last {hours_back} hours")
        report_sections.append(f"**Top Queries:** {top_count}")
        report_sections.append("")
        
        if not queries:
            report_sections.append("No queries found for the specified time period.")
            return "\n".join(report_sections)
        
        # Summary
        total_reads = sum(float(q.get('total_logical_reads', 0)) for q in queries)
        total_writes = sum(float(q.get('total_logical_writes', 0)) for q in queries)
        total_executions = sum(int(q.get('execution_count', 0)) for q in queries)
        
        report_sections.append("## Summary")
        report_sections.append(f"- **Total Queries Analyzed:** {len(queries)}")
        report_sections.append(f"- **Total Logical Reads:** {total_reads:,.0f} pages")
        report_sections.append(f"- **Total Logical Writes:** {total_writes:,.0f} pages")
        report_sections.append(f"- **Total Executions:** {total_executions:,}")
        report_sections.append("")
        
        # Query Details
        report_sections.append("## Query Details")
        
        for i, query in enumerate(queries[:top_count], 1):
            avg_reads = float(query.get('avg_logical_reads', 0))
            avg_writes = float(query.get('avg_logical_writes', 0))
            execution_count = int(query.get('execution_count', 0))
            total_reads = float(query.get('total_logical_reads', 0))
            total_writes = float(query.get('total_logical_writes', 0))
            max_reads = float(query.get('max_logical_reads', 0))
            max_writes = float(query.get('max_logical_writes', 0))
            avg_cpu = float(query.get('avg_cpu_time', 0))
            avg_duration = float(query.get('avg_duration', 0))
            query_text = query.get('query_sql_text', 'N/A')
            last_execution = query.get('last_execution_time', 'N/A')
            
            # Truncate long queries
            if len(query_text) > 200:
                query_text = query_text[:200] + "..."
            
            report_sections.append(f"### Query #{i}")
            report_sections.append(f"- **Average Logical Reads:** {avg_reads:,.0f} pages")
            report_sections.append(f"- **Total Logical Reads:** {total_reads:,.0f} pages")
            report_sections.append(f"- **Max Logical Reads:** {max_reads:,.0f} pages")
            report_sections.append(f"- **Average Logical Writes:** {avg_writes:,.0f} pages")
            report_sections.append(f"- **Total Logical Writes:** {total_writes:,.0f} pages")
            report_sections.append(f"- **Max Logical Writes:** {max_writes:,.0f} pages")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(f"- **Average CPU Time:** {_format_timing(avg_cpu)}")
            report_sections.append(f"- **Average Duration:** {_format_timing(avg_duration)}")
            report_sections.append(f"- **Last Execution:** {last_execution}")
            report_sections.append("- **Query Text:**")
            report_sections.append("```sql")
            report_sections.append(query_text)
            report_sections.append("```")
            report_sections.append("")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            top_count = params.get("top_count", 15)
            hours_back = params.get("hours_back", 2)
            
            db_config = self.toolset.database_config()
            client = self.toolset.api_client()
            
            # Get top data I/O queries
            queries = client.get_top_data_io_queries(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name,
                top_count, hours_back
            )
            
            # Format the report
            report_text = self._format_data_io_queries_report(queries, db_config, top_count, hours_back)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to get top data I/O queries: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_config = self.toolset.database_config()
        return f"Retrieved top data I/O consuming queries for database {db_config.server_name}/{db_config.database_name}"


class GetTopLogIOQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="get_top_log_io_queries",
            description="Gets the top log I/O consuming queries from Query Store for transaction log performance analysis",
            parameters={
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

    def _format_log_io_queries_report(self, queries: List[Dict], db_config: AzureSQLDatabaseConfig, 
                                    top_count: int, hours_back: int) -> str:
        """Format the log I/O queries data into a readable report."""
        report_sections = []
        
        # Header
        report_sections.append("# Top Log I/O Consuming Queries Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Analysis Period:** Last {hours_back} hours")
        report_sections.append(f"**Top Queries:** {top_count}")
        report_sections.append("")
        
        if not queries:
            report_sections.append("No queries found for the specified time period.")
            return "\n".join(report_sections)
        
        # Summary
        total_log_writes = sum(float(q.get('total_log_bytes_used', 0)) for q in queries)
        total_executions = sum(int(q.get('execution_count', 0)) for q in queries)
        
        report_sections.append("## Summary")
        report_sections.append(f"- **Total Queries Analyzed:** {len(queries)}")
        report_sections.append(f"- **Total Log Bytes Used:** {total_log_writes:,.0f} bytes")
        report_sections.append(f"- **Total Executions:** {total_executions:,}")
        report_sections.append("")
        
        # Query Details
        report_sections.append("## Query Details")
        
        for i, query in enumerate(queries[:top_count], 1):
            avg_log_bytes = float(query.get('avg_log_bytes_used', 0))
            execution_count = int(query.get('execution_count', 0))
            total_log_bytes = float(query.get('total_log_bytes_used', 0))
            max_log_bytes = float(query.get('max_log_bytes_used', 0))
            avg_cpu = float(query.get('avg_cpu_time', 0))
            avg_duration = float(query.get('avg_duration', 0))
            query_text = query.get('query_sql_text', 'N/A')
            last_execution = query.get('last_execution_time', 'N/A')
            
            # Truncate long queries
            if len(query_text) > 200:
                query_text = query_text[:200] + "..."
            
            report_sections.append(f"### Query #{i}")
            report_sections.append(f"- **Average Log Bytes Used:** {avg_log_bytes:,.0f} bytes")
            report_sections.append(f"- **Total Log Bytes Used:** {total_log_bytes:,.0f} bytes")
            report_sections.append(f"- **Max Log Bytes Used:** {max_log_bytes:,.0f} bytes")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(f"- **Average CPU Time:** {_format_timing(avg_cpu)}")
            report_sections.append(f"- **Average Duration:** {_format_timing(avg_duration)}")
            report_sections.append(f"- **Last Execution:** {last_execution}")
            report_sections.append("- **Query Text:**")
            report_sections.append("```sql")
            report_sections.append(query_text)
            report_sections.append("```")
            report_sections.append("")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            top_count = params.get("top_count", 15)
            hours_back = params.get("hours_back", 2)
            
            db_config = self.toolset.database_config()
            client = self.toolset.api_client()
            
            # Get top log I/O queries
            queries = client.get_top_log_io_queries(
                db_config.subscription_id, db_config.resource_group,
                db_config.server_name, db_config.database_name,
                top_count, hours_back
            )
            
            # Format the report
            report_text = self._format_log_io_queries_report(queries, db_config, top_count, hours_back)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to get top log I/O queries: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_config = self.toolset.database_config()
        return f"Retrieved top log I/O consuming queries for database {db_config.server_name}/{db_config.database_name}"


class GenerateConnectionReport(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="generate_connection_report",
            description="Generates a comprehensive connection monitoring report including active connections, connection metrics, and connection pool statistics",
            parameters={
                "hours_back": ToolParameter(
                    description="Number of hours back to analyze (default: 2)",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _build_connection_report(self, db_config: AzureSQLDatabaseConfig, 
                               connection_data: Dict, hours_back: int) -> str:
        """Build the formatted connection report from gathered data."""
        report_sections = []
        
        # Header
        report_sections.append("# Azure SQL Database Connection Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Analysis Period:** Last {hours_back} hours")
        report_sections.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
        report_sections.append("")
        
        # Connection Summary
        report_sections.append("## Connection Summary")
        summary = connection_data.get("summary", {})
        if "error" in summary:
            report_sections.append(f"⚠️ **Error retrieving connection summary:** {summary['error']}")
        else:
            total_conn = summary.get("total_connections", 0)
            active_conn = summary.get("active_connections", 0)
            idle_conn = summary.get("idle_connections", 0)
            blocked_conn = summary.get("blocked_connections", 0)
            
            report_sections.append(f"- **Total Connections**: {total_conn}")
            report_sections.append(f"- **Active Connections**: {active_conn}")
            report_sections.append(f"- **Idle Connections**: {idle_conn}")
            if blocked_conn > 0:
                report_sections.append(f"- **🚨 Blocked Connections**: {blocked_conn}")
            else:
                report_sections.append(f"- **Blocked Connections**: {blocked_conn}")
            report_sections.append(f"- **Unique Users**: {summary.get('unique_users', 0)}")
            report_sections.append(f"- **Unique Hosts**: {summary.get('unique_hosts', 0)}")
        report_sections.append("")
        
        # Connection Pool Statistics
        report_sections.append("## Connection Pool Statistics")
        pool_stats = connection_data.get("pool_stats", {})
        if "error" in pool_stats:
            report_sections.append(f"⚠️ **Error retrieving pool stats:** {pool_stats['error']}")
        else:
            for metric_name, metric_data in pool_stats.items():
                if isinstance(metric_data, dict) and "value" in metric_data:
                    value = metric_data["value"]
                    unit = metric_data.get("unit", "")
                    report_sections.append(f"- **{metric_name}**: {value:,} {unit}")
        report_sections.append("")
        
        # Active Connections Detail
        report_sections.append("## Active Connections Detail")
        active_connections = connection_data.get("active_connections", [])
        if active_connections:
            active_count = len([conn for conn in active_connections if conn.get("connection_status") == "Active"])
            report_sections.append(f"**{active_count} active connections found:**")
            report_sections.append("")
            
            for i, conn in enumerate(active_connections[:10], 1):  # Show top 10
                if conn.get("connection_status") == "Active":
                    login_name = conn.get("login_name", "Unknown")
                    host_name = conn.get("host_name", "Unknown")
                    status = conn.get("status", "Unknown")
                    cpu_time = conn.get("cpu_time", 0)
                    wait_type = conn.get("wait_type", "")
                    blocking_session = conn.get("blocking_session_id", 0)
                    
                    report_sections.append(f"### Connection #{i}")
                    report_sections.append(f"- **User**: {login_name}@{host_name}")
                    report_sections.append(f"- **Status**: {status}")
                    report_sections.append(f"- **CPU Time**: {cpu_time:,} ms")
                    if wait_type:
                        report_sections.append(f"- **Wait Type**: {wait_type}")
                    if blocking_session and blocking_session > 0:
                        report_sections.append(f"- **🚨 Blocked by Session**: {blocking_session}")
                    report_sections.append("")
        else:
            report_sections.append("No active connections found")
        
        # Azure Monitor Metrics (if available)
        report_sections.append("## Azure Monitor Connection Metrics")
        metrics = connection_data.get("metrics", {})
        if "error" in metrics:
            report_sections.append(f"⚠️ **Metrics unavailable:** {metrics['error']}")
        else:
            for metric_name, metric_data in metrics.items():
                if metric_data:
                    recent_values = metric_data[-5:]  # Last 5 data points
                    if recent_values:
                        avg_value = sum(point.get("average", 0) or 0 for point in recent_values) / len(recent_values)
                        max_value = max(point.get("maximum", 0) or 0 for point in recent_values)
                        report_sections.append(f"- **{metric_name}**: Avg {avg_value:.1f}, Max {max_value:.1f}")
            
            if not any(metrics.values()):
                report_sections.append("No recent metric data available")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            hours_back = params.get("hours_back", 2)
            
            db_config = self.toolset.database_config()
            
            # Create connection monitoring API client
            api_client = self.toolset.api_client()
            connection_api = ConnectionMonitoringAPI(
                credential=api_client.credential,
                subscription_id=db_config.subscription_id,
                sql_username=api_client.sql_username,
                sql_password=api_client.sql_password
            )
            
            # Gather connection data
            connection_data = {}
            
            # Get connection summary
            connection_data["summary"] = connection_api.get_connection_summary(
                db_config.server_name, db_config.database_name
            )
            
            # Get active connections
            connection_data["active_connections"] = connection_api.get_active_connections(
                db_config.server_name, db_config.database_name
            )
            
            # Get connection pool stats
            connection_data["pool_stats"] = connection_api.get_connection_pool_stats(
                db_config.server_name, db_config.database_name
            )
            
            # Get Azure Monitor metrics
            connection_data["metrics"] = connection_api.get_connection_metrics(
                db_config.resource_group, db_config.server_name, 
                db_config.database_name, hours_back
            )
            
            # Build the formatted report
            report_text = self._build_connection_report(db_config, connection_data, hours_back)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to generate connection report: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_config = self.toolset.database_config()
        return f"Generated connection monitoring report for database {db_config.server_name}/{db_config.database_name}"


class GenerateStorageReport(BaseAzureSQLTool):
    def __init__(self, toolset: "AzureSQLToolset"):
        super().__init__(
            name="generate_storage_report",
            description="Generates a comprehensive storage analysis report including disk usage, growth trends, and table space utilization",
            parameters={
                "hours_back": ToolParameter(
                    description="Number of hours back to analyze for metrics (default: 24)",
                    type="integer",
                    required=False,
                ),
                "top_tables": ToolParameter(
                    description="Number of top tables to analyze for space usage (default: 20)",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _build_storage_report(self, db_config: AzureSQLDatabaseConfig, 
                            storage_data: Dict, hours_back: int, top_tables: int) -> str:
        """Build the formatted storage report from gathered data."""
        report_sections = []
        
        # Header
        report_sections.append("# Azure SQL Database Storage Analysis Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Analysis Period:** Last {hours_back} hours")
        report_sections.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
        report_sections.append("")
        
        # Storage Summary
        report_sections.append("## Storage Summary")
        summary = storage_data.get("summary", {})
        if "error" in summary:
            report_sections.append(f"⚠️ **Error retrieving storage summary:** {summary['error']}")
        else:
            total_size = summary.get("total_database_size_mb", 0)
            used_size = summary.get("total_used_size_mb", 0)
            data_size = summary.get("total_data_size_mb", 0)
            log_size = summary.get("total_log_size_mb", 0)
            
            if total_size:
                used_percent = (used_size / total_size) * 100
                free_size = total_size - used_size
                
                report_sections.append(f"- **Total Database Size**: {total_size:,.1f} MB")
                report_sections.append(f"- **Used Space**: {used_size:,.1f} MB ({used_percent:.1f}%)")
                report_sections.append(f"- **Free Space**: {free_size:,.1f} MB")
                report_sections.append(f"- **Data Files**: {data_size:,.1f} MB")
                report_sections.append(f"- **Log Files**: {log_size:,.1f} MB")
                report_sections.append(f"- **Data Files Count**: {summary.get('data_files_count', 0)}")
                report_sections.append(f"- **Log Files Count**: {summary.get('log_files_count', 0)}")
            else:
                report_sections.append("No storage summary data available")
        report_sections.append("")
        
        # File Details
        report_sections.append("## Database Files Details")
        file_details = storage_data.get("file_details", [])
        if isinstance(file_details, dict) and "error" in file_details:
            report_sections.append(f"⚠️ **Error retrieving file details:** {file_details['error']}")
        elif file_details:
            for file_info in file_details:
                file_type = file_info.get("file_type", "Unknown")
                logical_name = file_info.get("logical_name", "Unknown")
                size_mb = file_info.get("size_mb", 0)
                used_mb = file_info.get("used_mb", 0)
                used_percent = file_info.get("used_percent", 0)
                max_size = file_info.get("max_size", "Unknown")
                growth = file_info.get("growth_setting", "Unknown")
                
                status_icon = "🔴" if used_percent > 90 else "🟡" if used_percent > 75 else "🟢"
                
                report_sections.append(f"### {file_type} File: {logical_name}")
                report_sections.append(f"- **Size**: {size_mb:,.1f} MB")
                report_sections.append(f"- **Used**: {used_mb:,.1f} MB ({used_percent:.1f}%) {status_icon}")
                report_sections.append(f"- **Max Size**: {max_size}")
                report_sections.append(f"- **Growth**: {growth}")
                report_sections.append("")
        else:
            report_sections.append("No file details available")
        
        # Growth Trend Analysis
        report_sections.append("## Storage Growth Analysis")
        growth_data = storage_data.get("growth_trend", {})
        if "error" in growth_data:
            report_sections.append(f"⚠️ **Growth analysis unavailable:** {growth_data['error']}")
        elif growth_data.get("growth_analysis"):
            analysis = growth_data["growth_analysis"]
            total_growth = analysis.get("total_growth_mb", 0)
            growth_percent = analysis.get("growth_percent", 0)
            days_analyzed = analysis.get("days_analyzed", 0)
            daily_growth = analysis.get("avg_daily_growth_mb", 0)
            
            growth_icon = "🔴" if daily_growth > 100 else "🟡" if daily_growth > 50 else "🟢"
            
            report_sections.append(f"- **Analysis Period**: {days_analyzed} days")
            report_sections.append(f"- **Total Growth**: {total_growth:,.1f} MB ({growth_percent:.1f}%)")
            report_sections.append(f"- **Daily Average Growth**: {daily_growth:,.1f} MB {growth_icon}")
            
            # Growth projection
            if daily_growth > 0:
                days_to_double = (summary.get("total_database_size_mb", 0) / daily_growth) if daily_growth > 0 else 0
                report_sections.append(f"- **Projected to Double**: {days_to_double:,.0f} days")
        else:
            report_sections.append("Growth analysis requires backup history (not available)")
        report_sections.append("")
        
        # Top Tables by Space Usage
        report_sections.append(f"## Top {top_tables} Tables by Space Usage")
        table_usage = storage_data.get("table_usage", [])
        if table_usage:
            report_sections.append("")
            for i, table in enumerate(table_usage[:top_tables], 1):
                schema_name = table.get("schema_name", "unknown")
                table_name = table.get("table_name", "unknown")
                total_space = table.get("total_space_mb", 0)
                row_count = table.get("row_count", 0)
                index_type = table.get("index_type", "unknown")
                
                report_sections.append(f"### {i}. {schema_name}.{table_name}")
                report_sections.append(f"- **Total Space**: {total_space:,.1f} MB")
                report_sections.append(f"- **Row Count**: {row_count:,}")
                report_sections.append(f"- **Index Type**: {index_type}")
                report_sections.append("")
        else:
            report_sections.append("No table usage data available")
        
        # Azure Monitor Storage Metrics
        report_sections.append("## Azure Monitor Storage Metrics")
        metrics = storage_data.get("metrics", {})
        if "error" in metrics:
            report_sections.append(f"⚠️ **Metrics unavailable:** {metrics['error']}")
        else:
            metric_found = False
            for metric_name, metric_data in metrics.items():
                if metric_data:
                    metric_found = True
                    recent_values = metric_data[-5:]  # Last 5 data points
                    if recent_values:
                        avg_value = sum(point.get("average", 0) or 0 for point in recent_values) / len(recent_values)
                        max_value = max(point.get("maximum", 0) or 0 for point in recent_values)
                        
                        # Format based on metric type
                        if "percent" in metric_name:
                            report_sections.append(f"- **{metric_name}**: Avg {avg_value:.1f}%, Max {max_value:.1f}%")
                        else:
                            report_sections.append(f"- **{metric_name}**: Avg {avg_value:,.1f}, Max {max_value:,.1f}")
            
            if not metric_found:
                report_sections.append("No recent storage metric data available")
        
        # TempDB Usage
        tempdb_data = storage_data.get("tempdb", {})
        if tempdb_data and "error" not in tempdb_data:
            report_sections.append("")
            report_sections.append("## TempDB Usage")
            for metric_type, data in tempdb_data.items():
                if isinstance(data, dict):
                    used_percent = data.get("used_percent", 0)
                    status_icon = "🔴" if used_percent > 90 else "🟡" if used_percent > 75 else "🟢"
                    report_sections.append(f"- **{metric_type}**: {data.get('used_size_mb', 0):,.1f} MB / {data.get('total_size_mb', 0):,.1f} MB ({used_percent:.1f}%) {status_icon}")
        
        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            hours_back = params.get("hours_back", 24)
            top_tables = params.get("top_tables", 20)
            
            db_config = self.toolset.database_config()
            
            # Create storage analysis API client
            api_client = self.toolset.api_client()
            storage_api = StorageAnalysisAPI(
                credential=api_client.credential,
                subscription_id=db_config.subscription_id,
                sql_username=api_client.sql_username,
                sql_password=api_client.sql_password
            )
            
            # Gather storage data
            storage_data = {}
            
            # Get storage summary
            storage_data["summary"] = storage_api.get_storage_summary(
                db_config.server_name, db_config.database_name
            )
            
            # Get file details
            storage_data["file_details"] = storage_api.get_database_size_details(
                db_config.server_name, db_config.database_name
            )
            
            # Get table space usage
            storage_data["table_usage"] = storage_api.get_table_space_usage(
                db_config.server_name, db_config.database_name, top_tables
            )
            
            # Get growth trend
            storage_data["growth_trend"] = storage_api.get_storage_growth_trend(
                db_config.server_name, db_config.database_name
            )
            
            # Get Azure Monitor storage metrics
            storage_data["metrics"] = storage_api.get_storage_metrics(
                db_config.resource_group, db_config.server_name, 
                db_config.database_name, hours_back
            )
            
            # Get TempDB usage
            storage_data["tempdb"] = storage_api.get_tempdb_usage(
                db_config.server_name, db_config.database_name
            )
            
            # Build the formatted report
            report_text = self._build_storage_report(db_config, storage_data, hours_back, top_tables)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to generate storage report: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_config = self.toolset.database_config()
        return f"Generated storage analysis report for database {db_config.server_name}/{db_config.database_name}"



class AzureSQLToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _api_client: Optional[AzureSQLAPIClient] = None
    _database_config: Optional[AzureSQLDatabaseConfig] = None

    def __init__(self):
        super().__init__(
            name="azure/sql",
            description="Monitors Azure SQL Database performance, health, and security using Azure REST APIs",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/azure-sql.html",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Azure_SQL_Database_logo.svg/1200px-Azure_SQL_Database_logo.svg.png",
            tags=[ToolsetTag.CORE],
            tools=[
                GenerateHealthReport(self),
                GeneratePerformanceReport(self),
                GenerateConnectionReport(self),
                GenerateStorageReport(self),
                GetTopCPUQueries(self),
                GetSlowQueries(self),
                GetTopDataIOQueries(self),
                GetTopLogIOQueries(self),
            ],
        )

    def api_client(self):
        if not self._api_client:
            raise Exception("Toolset is missing api_client. This is likely a code issue and not a configuration issue")
        else:
            return self._api_client

    def database_config(self):
        if not self._database_config:
            raise Exception("Toolset is missing database_config. This is likely a code issue and not a configuration issue")
        else:
            return self._database_config

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
                
                # Test the credential by attempting to get tokens for both required scopes
                mgmt_token = credential.get_token("https://management.azure.com/.default")
                if not mgmt_token.token:
                    raise Exception("Failed to obtain Azure management token")
                
                # Test SQL database token as well
                sql_token = credential.get_token("https://database.windows.net/.default")
                if not sql_token.token:
                    raise Exception("Failed to obtain Azure SQL database token")
                    
            except Exception as e:
                message = f"Failed to set up Azure authentication: {str(e)}"
                logging.error(message)
                errors.append(message)
                return False, message
            
            # Store single database configuration and create API client
            self._database_config = azure_sql_config.database
            self._api_client = AzureSQLAPIClient(credential, azure_sql_config.database.subscription_id)
            logging.info(f"Configured Azure SQL database: {azure_sql_config.database.server_name}/{azure_sql_config.database.database_name}")

            return len(errors) == 0, "\n".join(errors)
        except Exception as e:
            logging.exception("Failed to set up Azure SQL toolset")
            return False, str(e)

    def get_example_config(self) -> Dict[str, Any]:
        example_config = AzureSQLConfig(
            tenant_id="{{ env.AZURE_TENANT_ID }}",
            client_id="{{ env.AZURE_CLIENT_ID }}",
            client_secret="{{ env.AZURE_CLIENT_SECRET }}",
            database=AzureSQLDatabaseConfig(
                subscription_id="12345678-1234-1234-1234-123456789012",
                resource_group="my-resource-group",
                server_name="myserver",
                database_name="mydatabase",
            )
        )
        return example_config.model_dump()


