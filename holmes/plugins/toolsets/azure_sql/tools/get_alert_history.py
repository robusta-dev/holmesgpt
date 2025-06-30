import logging
from typing import Any, Dict, List
from datetime import datetime, timezone

from holmes.core.tools import StructuredToolResult, ToolParameter, ToolResultStatus
from holmes.plugins.toolsets.azure_sql.azure_base_toolset import (
    BaseAzureSQLTool,
    BaseAzureSQLToolset,
    AzureSQLDatabaseConfig,
)
from holmes.plugins.toolsets.azure_sql.apis.azure_sql_api import AzureSQLAPIClient
from holmes.plugins.toolsets.azure_sql.apis.alert_monitoring_api import AlertMonitoringAPI


class GetAlertHistory(BaseAzureSQLTool):
    def __init__(self, toolset: "BaseAzureSQLToolset"):
        super().__init__(
            name="get_alert_history",
            description="Retrieves historical Azure Monitor alerts for the SQL database and server. Use this to identify recurring issues, analyze alert patterns, and understand past incidents for troubleshooting.",
            parameters={
                "hours_back": ToolParameter(
                    description="Time window for alert history analysis in hours. Use 24 for daily analysis, 168 for weekly trends (default: 168)",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _build_history_report(
        self, db_config: AzureSQLDatabaseConfig, alerts_data: Dict, hours_back: int
    ) -> str:
        """Build the formatted alert history report from gathered data."""
        report_sections = []

        # Header
        report_sections.append("# Azure SQL Database Alert History Report")
        report_sections.append(f"**Database:** {db_config.database_name}")
        report_sections.append(f"**Server:** {db_config.server_name}")
        report_sections.append(f"**Resource Group:** {db_config.resource_group}")
        report_sections.append(f"**Analysis Period:** Last {hours_back} hours")
        report_sections.append(
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}"
        )
        report_sections.append("")

        # Check for errors
        if "error" in alerts_data:
            report_sections.append(f"⚠️ **Error retrieving alert history:** {alerts_data['error']}")
            return "\n".join(report_sections)

        # Time range information
        time_range = alerts_data.get("time_range", {})
        start_time = time_range.get("start", "Unknown")
        end_time = time_range.get("end", "Unknown")
        
        report_sections.append("## Analysis Period")
        report_sections.append(f"- **Start Time**: {start_time}")
        report_sections.append(f"- **End Time**: {end_time}")
        report_sections.append("")

        # Summary and Analysis
        total_alerts = alerts_data.get("total_count", 0)
        analysis = alerts_data.get("analysis", {})
        
        report_sections.append("## Summary")
        if total_alerts == 0:
            report_sections.append("✅ **No alerts found** in the specified time period")
        else:
            report_sections.append(f"📊 **{total_alerts} alerts found** in the last {hours_back} hours")
            
            # Analysis insights
            if analysis:
                severity_breakdown = analysis.get("severity_breakdown", {})
                scope_breakdown = analysis.get("scope_breakdown", {})
                most_frequent = analysis.get("most_frequent_alerts", [])
                analysis_notes = analysis.get("analysis_notes", [])
                
                if severity_breakdown:
                    report_sections.append("### Severity Distribution:")
                    for severity, count in sorted(severity_breakdown.items()):
                        icon = "🔴" if severity in ["Sev0", "Critical"] else "🟡" if severity in ["Sev1", "Error"] else "🟢"
                        report_sections.append(f"- **{severity}**: {count} alerts {icon}")
                
                if scope_breakdown:
                    report_sections.append("### Resource Scope:")
                    for scope, count in sorted(scope_breakdown.items()):
                        report_sections.append(f"- **{scope.title()}**: {count} alerts")
                
                if most_frequent:
                    report_sections.append("### Most Frequent Alerts:")
                    for alert_name, count in most_frequent[:3]:  # Top 3
                        report_sections.append(f"- **{alert_name}**: {count} occurrences")
                
                if analysis_notes:
                    report_sections.append("### Key Insights:")
                    for note in analysis_notes:
                        report_sections.append(f"- {note}")
        
        report_sections.append("")

        # Recent Alerts (last 10)
        alerts = alerts_data.get("alerts", [])
        if alerts:
            report_sections.append("## Recent Alerts (Last 10)")
            
            for i, alert in enumerate(alerts[:10], 1):
                name = alert.get("name", "Unknown Alert")
                severity = alert.get("severity", "Unknown")
                state = alert.get("state", "Unknown")
                fired_time = alert.get("fired_time", "Unknown")
                resolved_time = alert.get("resolved_time")
                scope = alert.get("scope", "Unknown")
                
                # Format severity with icon
                severity_icon = "🔴" if severity in ["Sev0", "Critical"] else "🟡" if severity in ["Sev1", "Error"] else "🟢"
                
                # Format time more readably
                try:
                    fired_dt = datetime.fromisoformat(fired_time.replace('Z', '+00:00'))
                    fired_display = fired_dt.strftime("%Y-%m-%d %H:%M UTC")
                except:
                    fired_display = fired_time
                
                report_sections.append(f"### {i}. {name}")
                report_sections.append(f"- **Severity**: {severity} {severity_icon}")
                report_sections.append(f"- **State**: {state}")
                report_sections.append(f"- **Scope**: {scope.title()}")
                report_sections.append(f"- **Fired**: {fired_display}")
                if resolved_time:
                    try:
                        resolved_dt = datetime.fromisoformat(resolved_time.replace('Z', '+00:00'))
                        resolved_display = resolved_dt.strftime("%Y-%m-%d %H:%M UTC")
                        report_sections.append(f"- **Resolved**: {resolved_display}")
                    except:
                        report_sections.append(f"- **Resolved**: {resolved_time}")
                report_sections.append("")

        # Resource Information
        report_sections.append("## Resource Information")
        report_sections.append(f"- **Database Resource ID**: {alerts_data.get('database_resource_id', 'N/A')}")
        report_sections.append(f"- **Server Resource ID**: {alerts_data.get('server_resource_id', 'N/A')}")
        
        # Metadata
        method = alerts_data.get("method")
        if method:
            report_sections.append(f"- **Data Source**: {method}")

        return "\n".join(report_sections)

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            hours_back = params.get("hours_back", 168)  # Default to 7 days
            
            db_config = self.toolset.database_config()
            api_client = self.toolset.api_client()

            # Create alert monitoring API client
            alert_api = AlertMonitoringAPI(
                credential=api_client.credential,
                subscription_id=db_config.subscription_id,
            )

            # Get alert history
            alerts_data = alert_api.get_alert_history(
                db_config.resource_group,
                db_config.server_name,
                db_config.database_name,
                hours_back,
            )

            # Build the formatted report
            report_text = self._build_history_report(db_config, alerts_data, hours_back)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=report_text,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to retrieve alert history: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_config = self.toolset.database_config()
        hours_back = params.get("hours_back", 168)
        return f"Fetch {hours_back}h alert history for database {db_config.server_name}/{db_config.database_name}"
