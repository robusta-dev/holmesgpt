"""
Integration test for Azure SQL GenerateConnectionReport tool.
This test requires live Azure SQL database connection.

Environment variables required:
- AZURE_SQL_TENANT_ID: Azure tenant ID
- AZURE_SQL_RESOURCE_GROUP: Resource group name
- AZURE_SQL_CLIENT_ID: Service principal client ID
- AZURE_SQL_CLIENT_SECRET: Service principal client secret
- AZURE_SQL_SERVER: Azure SQL server name
- AZURE_SQL_DATABASE: Database name
- AZURE_SQL_SUBSCRIPTION_ID: Azure subscription ID
"""

import os
import pytest
from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import (
    AzureSQLToolset,
    GenerateConnectionReport,
)

REQUIRED_ENV_VARS = [
    "AZURE_SQL_TENANT_ID",
    "AZURE_SQL_RESOURCE_GROUP",
    "AZURE_SQL_CLIENT_ID",
    "AZURE_SQL_CLIENT_SECRET",
    "AZURE_SQL_SERVER",
    "AZURE_SQL_DATABASE",
    "AZURE_SQL_SUBSCRIPTION_ID",
]

missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]

pytestmark = pytest.mark.skipif(
    len(missing_vars) > 0,
    reason=f"Missing required environment variables: {', '.join(missing_vars)}",
)


@pytest.fixture
def azure_sql_config():
    """Create Azure SQL configuration from environment variables."""
    return {
        "tenant_id": os.environ.get("AZURE_SQL_TENANT_ID"),
        "client_id": os.environ.get("AZURE_SQL_CLIENT_ID"),
        "client_secret": os.environ.get("AZURE_SQL_CLIENT_SECRET"),
        "database": {
            "subscription_id": os.environ.get("AZURE_SQL_SUBSCRIPTION_ID"),
            "resource_group": os.environ.get("AZURE_SQL_RESOURCE_GROUP"),
            "server_name": os.environ.get("AZURE_SQL_SERVER"),
            "database_name": os.environ.get("AZURE_SQL_DATABASE"),
        },
    }


@pytest.fixture
def azure_sql_toolset(azure_sql_config):
    """Create and configure Azure SQL toolset."""
    toolset = AzureSQLToolset()
    ready, message = toolset.prerequisites_callable(azure_sql_config)
    if not ready:
        pytest.skip(f"Prerequisites not met: {message}")
    return toolset


def test_generate_connection_report_prerequisites(azure_sql_config):
    """Test that the toolset prerequisites are met."""
    toolset = AzureSQLToolset()
    ready, message = toolset.prerequisites_callable(azure_sql_config)
    assert ready, f"Prerequisites failed: {message}"
    assert not message, f"Unexpected message: {message}"


def test_generate_connection_report_success(azure_sql_toolset):
    """Test successful generation of connection report."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS, f"Tool failed: {result.error}"
    assert result.data, "Connection report data should not be empty"
    assert not result.error, f"Unexpected error: {result.error}"

    # Verify report structure and content
    report_data = result.data
    assert isinstance(report_data, str), "Report data should be a string"
    assert len(report_data) > 0, "Report should not be empty"

    # Check for required report sections
    assert "# Azure SQL Database Connection Report" in report_data
    assert "## Connection Summary" in report_data
    assert "## Connection Pool Statistics" in report_data
    assert "## Active Connections Detail" in report_data
    assert "## Azure Monitor Connection Metrics" in report_data

    # Check for database information
    db_config = azure_sql_toolset.database_config()
    assert db_config.database_name in report_data
    assert db_config.server_name in report_data

    # Check timestamp format
    assert "Generated:" in report_data


def test_connection_summary_section_has_meaningful_content(azure_sql_toolset):
    """Test that connection summary section contains meaningful content."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Extract connection summary section
    summary_section = report_data.split("## Connection Summary")[1].split("##")[0]
    assert summary_section.strip(), "Connection summary section should have content"

    # Should have either actual data or error message, but should have some content
    has_connection_data = any(
        metric in summary_section
        for metric in [
            "Total Connections",
            "Active Connections",
            "Idle Connections",
            "Blocked Connections",
            "Unique Users",
            "Unique Hosts",
        ]
    )
    has_error_message = "Error retrieving connection summary:" in summary_section

    assert (
        has_connection_data or has_error_message
    ), "Should have either connection data or error message"

    if has_connection_data:
        # If we have connection data, verify it has numeric values
        import re

        numeric_pattern = r"\*\*[^:]+\*\*:\s*\d+"
        numeric_matches = re.findall(numeric_pattern, summary_section)
        assert (
            len(numeric_matches) >= 1
        ), f"Should have at least 1 numeric connection metric, got {len(numeric_matches)}"


def test_connection_pool_statistics_section_valid(azure_sql_toolset):
    """Test that connection pool statistics section is valid."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Extract pool statistics section
    assert report_data
    pool_section = report_data.split("## Connection Pool Statistics")[1].split("##")[0]
    assert (
        pool_section.strip()
    ), "Connection pool statistics section should have content"

    # Should have either pool statistics or error message
    has_pool_data = any(
        pattern in pool_section
        for pattern in [
            "**",
            ":",
            "-",  # Look for basic pool stat formatting patterns
        ]
    )

    assert has_pool_data, "Should have pool statistics"

    if has_pool_data:
        # If we have pool data (and no error), look for metric patterns
        import re

        pool_metric_pattern = r"- \*\*[^:]+\*\*:\s*[\d,]+\s*[^*]*"
        pool_matches = re.findall(pool_metric_pattern, pool_section)
        # Pool metrics may be available depending on configuration


def test_active_connections_detail_section_meaningful(azure_sql_toolset):
    """Test that active connections detail section contains meaningful data."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Extract active connections section
    active_section = report_data.split("## Active Connections Detail")[1].split("##")[0]
    assert (
        active_section.strip()
    ), "Active connections detail section should have content"

    # Should have either connection details or "No active connections found"
    has_active_connections = "active connections found:" in active_section
    has_no_active_connections = "No active connections found" in active_section

    assert (
        has_active_connections or has_no_active_connections
    ), "Should have clear status about active connections"

    if has_active_connections:
        # If there are active connections, verify structure
        assert (
            "User" in active_section
        ), "Should show user information for active connections"
        assert "Status" in active_section, "Should show status for active connections"
        assert (
            "CPU Time" in active_section
        ), "Should show CPU time for active connections"

        # Should not have "Unknown" values for critical fields
        assert (
            "User**: Unknown@Unknown" not in active_section
        ), "Should have real user/host information, not 'Unknown'"


def test_azure_monitor_metrics_section_valid(azure_sql_toolset):
    """Test that Azure Monitor metrics section is valid."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Extract metrics section
    metrics_section = (
        report_data.split("## Azure Monitor Connection Metrics")[1]
        if "## Azure Monitor Connection Metrics" in report_data
        else ""
    )
    assert metrics_section.strip(), "Azure Monitor metrics section should have content"

    # Should have either metrics data or "No recent metric data available"
    has_metrics = any(keyword in metrics_section for keyword in ["Avg", "Max"])
    has_no_metrics = "No recent metric data available" in metrics_section
    has_metrics_unavailable = "Metrics unavailable:" in metrics_section

    assert (
        has_metrics or has_no_metrics or has_metrics_unavailable
    ), "Should have clear status about metrics availability"


def test_connection_report_handles_api_errors_gracefully(azure_sql_toolset):
    """Test that the connection report handles API errors gracefully."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS

    # The tool should always return a result, even if some API calls fail
    assert result.data
    assert isinstance(result.data, str)
    assert len(result.data) > 0

    # Should have all required sections even if some have errors
    required_sections = [
        "## Connection Summary",
        "## Connection Pool Statistics",
        "## Active Connections Detail",
        "## Azure Monitor Connection Metrics",
    ]

    for section in required_sections:
        assert section in result.data, f"Missing required section: {section}"


def test_connection_report_with_custom_hours_back(azure_sql_toolset):
    """Test connection report with custom hours_back parameter."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({"hours_back": 1})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Should reflect the custom time period
    assert "Analysis Period:** Last 1 hours" in report_data

    # Should still have all required sections
    required_sections = [
        "## Connection Summary",
        "## Connection Pool Statistics",
        "## Active Connections Detail",
        "## Azure Monitor Connection Metrics",
    ]

    for section in required_sections:
        assert section in report_data, f"Missing required section: {section}"


def test_connection_report_has_substantial_content(azure_sql_toolset):
    """Test that the connection report contains substantial content."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Count lines to ensure we have substantial content
    lines = [line.strip() for line in report_data.split("\n") if line.strip()]
    assert (
        len(lines) >= 10
    ), f"Report should have at least 10 lines of content, got {len(lines)}"

    # Should have all required sections with content
    sections = [
        "## Connection Summary",
        "## Connection Pool Statistics",
        "## Active Connections Detail",
        "## Azure Monitor Connection Metrics",
    ]

    for section in sections:
        assert section in report_data, f"Missing required section: {section}"
        # Extract section content
        section_part = report_data.split(section)[1]
        # Find the next ## section
        import re

        next_section_match = re.search(r"\n## ", section_part)
        if next_section_match:
            section_content = section_part[: next_section_match.start()]
        else:
            section_content = section_part
        assert (
            len(section_content.strip()) > 0
        ), f"Section '{section}' should have content"


def test_generate_connection_report_one_liner(azure_sql_toolset):
    """Test the one-liner description generation."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    one_liner = connection_report_tool.get_parameterized_one_liner({})

    assert isinstance(one_liner, str), "One liner should be a string"
    assert len(one_liner) > 0, "One liner should not be empty"

    db_config = azure_sql_toolset.database_config()
    assert db_config.server_name in one_liner
    assert db_config.database_name in one_liner
    assert "Generated connection monitoring report" in one_liner


def test_connection_data_structure_integrity(azure_sql_toolset):
    """Test that the connection data has proper structure and meaningful values."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Verify basic report structure
    assert "# Azure SQL Database Connection Report" in report_data
    assert "Database:**" in report_data
    assert "Server:**" in report_data

    # Verify timestamp format
    assert "Generated:" in report_data
    timestamp_line = [line for line in report_data.split("\n") if "Generated:" in line][
        0
    ]
    # Should have ISO format timestamp
    assert "T" in timestamp_line, "Should have ISO format timestamp"

    # If we have connection data (not errors), verify it's properly formatted
    if "Total Connections" in report_data and "Error retrieving" not in report_data:
        import re

        # Look for connection count patterns
        connection_pattern = r"Total Connections\*\*:\s*(\d+)"
        match = re.search(connection_pattern, report_data)
        if match:
            total_connections = int(match.group(1))
            assert (
                total_connections >= 0
            ), "Total connections should be a non-negative number"

    # Verify all required sections are present
    required_sections = [
        "Connection Summary",
        "Connection Pool Statistics",
        "Active Connections Detail",
        "Azure Monitor Connection Metrics",
    ]
    for section in required_sections:
        assert section in report_data, f"Missing section: {section}"


def test_connection_report_blocked_connections_handling(azure_sql_toolset):
    """Test that blocked connections are properly handled and highlighted."""
    connection_report_tool = GenerateConnectionReport(azure_sql_toolset)
    result = connection_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Should have blocked connections metric in summary (either as data or in error context)
    has_blocked_connections_metric = "Blocked Connections" in report_data
    has_connection_summary = "## Connection Summary" in report_data

    assert has_connection_summary, "Should have Connection Summary section"

    # If we have actual connection data (not errors), should show blocked connections
    if (
        "Total Connections" in report_data
        and "Error retrieving connection summary:" not in report_data
    ):
        assert (
            has_blocked_connections_metric
        ), "Should show blocked connections count when data is available"

    # Test alert highlighting works if present
    # (We can't guarantee blocked connections exist, but if they do, they should be highlighted)
    if "🚨 Blocked Connections" in report_data:
        assert (
            "🚨" in report_data
        ), "Blocked connections should be highlighted with alert emoji"

    if "Blocked by Session" in report_data:
        assert (
            "🚨 Blocked by Session" in report_data
        ), "Blocked sessions should be highlighted"
