import logging
from typing import Dict, List, Tuple

from holmes.core.tools import StructuredToolResult, ToolParameter, ToolResultStatus
from holmes.plugins.toolsets.azure_sql.azure_base_toolset import (
    BaseAzureSQLTool,
    BaseAzureSQLToolset,
    AzureSQLDatabaseConfig,
)
from holmes.plugins.toolsets.azure_sql.apis.azure_sql_api import AzureSQLAPIClient
from holmes.plugins.toolsets.azure_sql.utils import format_timing


class GetTopCPUQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "BaseAzureSQLToolset"):
        super().__init__(
            name="get_top_cpu_queries",
            description="Identifies the top CPU-consuming queries from Query Store. Use this to find queries causing high CPU utilization and performance bottlenecks.",
            parameters={
                "top_count": ToolParameter(
                    description="Number of top queries to return. Use 15 for detailed analysis, 5-10 for quick overview (default: 15)",
                    type="integer",
                    required=False,
                ),
                "hours_back": ToolParameter(
                    description="Time window for analysis in hours. Use 2 for recent issues, 24+ for trend analysis (default: 2)",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _format_cpu_queries_report(
        self,
        queries: List[Dict],
        db_config: AzureSQLDatabaseConfig,
        top_count: int,
        hours_back: int,
    ) -> str:
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
        total_cpu_time = sum(float(q.get("total_cpu_time", 0)) for q in queries)
        total_executions = sum(int(q.get("execution_count", 0)) for q in queries)

        report_sections.append("## Summary")
        report_sections.append(f"- **Total Queries Analyzed:** {len(queries)}")
        report_sections.append(f"- **Total CPU Time:** {format_timing(total_cpu_time)}")
        report_sections.append(f"- **Total Executions:** {total_executions:,}")
        report_sections.append("")

        # Query Details
        report_sections.append("## Query Details")

        for i, query in enumerate(queries[:top_count], 1):
            avg_cpu = float(query.get("avg_cpu_time", 0))
            execution_count = int(query.get("execution_count", 0))
            total_cpu = float(query.get("total_cpu_time", 0))
            max_cpu = float(query.get("max_cpu_time", 0))
            avg_duration = float(query.get("avg_duration", 0))
            query_text = query.get("query_sql_text", "N/A")
            last_execution = query.get("last_execution_time", "N/A")

            # Truncate long queries
            if len(query_text) > 200:
                query_text = query_text[:200] + "..."

            report_sections.append(f"### Query #{i}")
            report_sections.append(f"- **Average CPU Time:** {format_timing(avg_cpu)}")
            report_sections.append(f"- **Total CPU Time:** {format_timing(total_cpu)}")
            report_sections.append(f"- **Max CPU Time:** {format_timing(max_cpu)}")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(
                f"- **Average Duration:** {format_timing(avg_duration)}"
            )
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
                db_config.subscription_id,
                db_config.resource_group,
                db_config.server_name,
                db_config.database_name,
                top_count,
                hours_back,
            )

            # Format the report
            report_text = self._format_cpu_queries_report(
                queries, db_config, top_count, hours_back
            )

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
        return f"Fetch top CPU consuming queries for database {db_config.server_name}/{db_config.database_name}"

    @staticmethod
    def validate_config(
        api_client: AzureSQLAPIClient, database_config: AzureSQLDatabaseConfig
    ) -> Tuple[bool, str]:
        errors = []

        try:
            # Test direct database connection for Query Store access
            test_query = (
                "SELECT TOP 1 query_id FROM sys.query_store_query WHERE query_id > 0"
            )
            api_client.execute_query(
                database_config.server_name, database_config.database_name, test_query
            )
        except Exception as e:
            error_msg = str(e)
            if (
                "login failed" in error_msg.lower()
                or "authentication" in error_msg.lower()
            ):
                errors.append(f"Database authentication failed: {error_msg}")
            elif "permission" in error_msg.lower() or "denied" in error_msg.lower():
                errors.append(f"Query Store access denied: {error_msg}")
            elif "query store" in error_msg.lower():
                errors.append(f"Query Store not available or disabled: {error_msg}")
            else:
                errors.append(f"Database connection failed: {error_msg}")

        if errors:
            return False, "\n".join(errors)
        return True, ""
