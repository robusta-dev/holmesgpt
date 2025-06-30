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


def _format_timing(microseconds: float) -> str:
    """Format timing values with appropriate units (seconds, milliseconds, microseconds)."""
    if microseconds >= 1_000_000:  # >= 1 second
        return f"{microseconds / 1_000_000:.2f} s"
    elif microseconds >= 1_000:  # >= 1 millisecond
        return f"{microseconds / 1_000:.2f} ms"
    else:  # < 1 millisecond
        return f"{microseconds:.0f} μs"


class GetTopDataIOQueries(BaseAzureSQLTool):
    def __init__(self, toolset: "BaseAzureSQLToolset"):
        super().__init__(
            name="get_top_data_io_queries",
            description="Identifies queries consuming the most data I/O (logical reads/writes) from Query Store. Use this to find queries causing storage I/O bottlenecks and disk performance issues.",
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

    def _format_data_io_queries_report(
        self,
        queries: List[Dict],
        db_config: AzureSQLDatabaseConfig,
        top_count: int,
        hours_back: int,
    ) -> str:
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
        total_reads = sum(float(q.get("total_logical_reads", 0)) for q in queries)
        total_writes = sum(float(q.get("total_logical_writes", 0)) for q in queries)
        total_executions = sum(int(q.get("execution_count", 0)) for q in queries)

        report_sections.append("## Summary")
        report_sections.append(f"- **Total Queries Analyzed:** {len(queries)}")
        report_sections.append(f"- **Total Logical Reads:** {total_reads:,.0f} pages")
        report_sections.append(f"- **Total Logical Writes:** {total_writes:,.0f} pages")
        report_sections.append(f"- **Total Executions:** {total_executions:,}")
        report_sections.append("")

        # Query Details
        report_sections.append("## Query Details")

        for i, query in enumerate(queries[:top_count], 1):
            avg_reads = float(query.get("avg_logical_reads", 0))
            avg_writes = float(query.get("avg_logical_writes", 0))
            execution_count = int(query.get("execution_count", 0))
            total_reads = float(query.get("total_logical_reads", 0))
            total_writes = float(query.get("total_logical_writes", 0))
            max_reads = float(query.get("max_logical_reads", 0))
            max_writes = float(query.get("max_logical_writes", 0))
            avg_cpu = float(query.get("avg_cpu_time", 0))
            avg_duration = float(query.get("avg_duration", 0))
            query_text = query.get("query_sql_text", "N/A")
            last_execution = query.get("last_execution_time", "N/A")

            # Truncate long queries
            if len(query_text) > 200:
                query_text = query_text[:200] + "..."

            report_sections.append(f"### Query #{i}")
            report_sections.append(
                f"- **Average Logical Reads:** {avg_reads:,.0f} pages"
            )
            report_sections.append(
                f"- **Total Logical Reads:** {total_reads:,.0f} pages"
            )
            report_sections.append(f"- **Max Logical Reads:** {max_reads:,.0f} pages")
            report_sections.append(
                f"- **Average Logical Writes:** {avg_writes:,.0f} pages"
            )
            report_sections.append(
                f"- **Total Logical Writes:** {total_writes:,.0f} pages"
            )
            report_sections.append(f"- **Max Logical Writes:** {max_writes:,.0f} pages")
            report_sections.append(f"- **Execution Count:** {execution_count:,}")
            report_sections.append(f"- **Average CPU Time:** {_format_timing(avg_cpu)}")
            report_sections.append(
                f"- **Average Duration:** {_format_timing(avg_duration)}"
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

            # Get top data I/O queries
            queries = client.get_top_data_io_queries(
                db_config.subscription_id,
                db_config.resource_group,
                db_config.server_name,
                db_config.database_name,
                top_count,
                hours_back,
            )

            # Format the report
            report_text = self._format_data_io_queries_report(
                queries, db_config, top_count, hours_back
            )

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
        return f"Fetch top data I/O consuming queries for database {db_config.server_name}/{db_config.database_name}"
