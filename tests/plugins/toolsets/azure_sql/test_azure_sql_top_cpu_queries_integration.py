"""
Integration test for Azure SQL GetTopCPUQueries tool.
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
from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import AzureSQLToolset, GetTopCPUQueries

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
        }
    }


@pytest.fixture
def azure_sql_toolset(azure_sql_config):
    """Create and configure Azure SQL toolset."""
    toolset = AzureSQLToolset()
    ready, message = toolset.prerequisites_callable(azure_sql_config)
    if not ready:
        pytest.skip(f"Prerequisites not met: {message}")
    return toolset


def test_get_top_cpu_queries_prerequisites(azure_sql_config):
    """Test that the toolset prerequisites are met."""
    toolset = AzureSQLToolset()
    ready, message = toolset.prerequisites_callable(azure_sql_config)
    assert ready, f"Prerequisites failed: {message}"
    assert not message, f"Unexpected message: {message}"


def test_get_top_cpu_queries_success(azure_sql_toolset):
    """Test successful retrieval of top CPU queries."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    result = cpu_queries_tool.invoke({})
    
    assert result.status == ToolResultStatus.SUCCESS, f"Tool failed: {result.error}"
    assert result.data, "CPU queries report data should not be empty"
    assert not result.error, f"Unexpected error: {result.error}"
    
    # Verify report structure and content
    report_data = result.data
    assert isinstance(report_data, str), "Report data should be a string"
    assert len(report_data) > 0, "Report should not be empty"
    
    # Check for required report sections
    assert "# Top CPU Consuming Queries Report" in report_data
    assert "## Summary" in report_data
    assert "## Query Details" in report_data
    
    # Check for database information
    db_config = azure_sql_toolset.database_config()
    assert db_config.database_name in report_data
    assert db_config.server_name in report_data
    
    # Check default parameters are reflected
    assert "Analysis Period:** Last 2 hours" in report_data
    assert "Top Queries:** 15" in report_data


def test_get_top_cpu_queries_with_custom_parameters(azure_sql_toolset):
    """Test CPU queries with custom parameters."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    result = cpu_queries_tool.invoke({"top_count": 5, "hours_back": 1})
    
    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data
    
    # Should reflect custom parameters
    assert "Analysis Period:** Last 1 hours" in report_data
    assert "Top Queries:** 5" in report_data


def test_get_top_cpu_queries_summary_section(azure_sql_toolset):
    """Test that the summary section contains meaningful data."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    result = cpu_queries_tool.invoke({})
    
    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data
    
    # Extract summary section
    summary_section = report_data.split("## Summary")[1].split("##")[0]
    assert summary_section.strip(), "Summary section should have content"
    
    # Should have summary metrics
    expected_metrics = [
        "Total Queries Analyzed",
        "Total CPU Time", 
        "Total Executions"
    ]
    
    for metric in expected_metrics:
        assert metric in summary_section, f"Should have '{metric}' in summary"
    
    # Should have numeric values in the summary
    import re
    # Look for patterns like "142,609,056 microseconds" or "604" 
    numeric_pattern = r'[\d,]+\s*(?:microseconds|executions)?'
    numeric_matches = re.findall(numeric_pattern, summary_section)
    assert len(numeric_matches) >= 1, f"Should have at least 1 numeric value, got {len(numeric_matches)}"


def test_get_top_cpu_queries_handles_no_data_gracefully(azure_sql_toolset):
    """Test that the tool handles cases with no query data gracefully."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    # Use very short time window that might have no data
    result = cpu_queries_tool.invoke({"hours_back": 0.001})  # Very small timeframe
    
    assert result.status == ToolResultStatus.SUCCESS
    
    # Should still generate a report even if no queries found
    assert result.data
    assert isinstance(result.data, str)
    assert len(result.data) > 0
    
    # Should either have query data or appropriate message
    has_query_data = "### Query #" in result.data
    has_no_data_message = "No queries found for the specified time period" in result.data
    
    assert (has_query_data or has_no_data_message), \
        "Should have either query data or clear 'no data' message"


def test_get_top_cpu_queries_query_details_section(azure_sql_toolset):
    """Test that query details section contains proper structure."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    result = cpu_queries_tool.invoke({"top_count": 3})  # Small number for testing
    
    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data
    
    # Should have query details section
    assert "## Query Details" in report_data
    
    # Check if we have actual query data
    if "### Query #" in report_data:
        # If we have queries, verify they have proper structure
        expected_fields = [
            "Average CPU Time",
            "Total CPU Time", 
            "Max CPU Time",
            "Execution Count",
            "Average Duration",
            "Last Execution",
            "Query Text"
        ]
        
        for field in expected_fields:
            assert field in report_data, f"Query details should include '{field}'"
        
        # Should have SQL code blocks
        assert "```sql" in report_data, "Should include SQL code blocks"
        
        # Should have microsecond units
        assert "μs" in report_data, "Should show microsecond units for timing"


def test_get_top_cpu_queries_sql_access_working(azure_sql_toolset):
    """Test that the underlying SQL query access is working."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    
    # Test with a reasonable timeframe that should have some data
    result = cpu_queries_tool.invoke({"hours_back": 24})
    
    assert result.status == ToolResultStatus.SUCCESS
    
    # The query should execute without SQL permission errors
    report_data = result.data
    
    # Should not have authentication or permission errors
    permission_errors = [
        "Azure AD authentication failed",
        "service principal lacks database permissions",
        "permission was denied",
        "Login failed"
    ]
    
    for error in permission_errors:
        assert error not in report_data, f"Should not have permission error: '{error}'"


def test_get_top_cpu_queries_data_types_correct(azure_sql_toolset):
    """Test that the data types in the report are correct."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    result = cpu_queries_tool.invoke({})
    
    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data
    
    # Should have proper numeric formatting
    import re
    
    # Check for properly formatted numbers with commas
    if "Total CPU Time:" in report_data:
        cpu_time_pattern = r'Total CPU Time:\*\*\s*([\d,]+)\s*microseconds'
        match = re.search(cpu_time_pattern, report_data)
        if match:
            # Should be a valid number (with or without commas)
            cpu_time_str = match.group(1).replace(',', '')
            cpu_time = int(cpu_time_str)
            assert cpu_time >= 0, "CPU time should be non-negative"
    
    # Check for execution count formatting
    if "Total Executions:" in report_data:
        exec_pattern = r'Total Executions:\*\*\s*([\d,]+)'
        match = re.search(exec_pattern, report_data)
        if match:
            exec_str = match.group(1).replace(',', '')
            exec_count = int(exec_str)
            assert exec_count >= 0, "Execution count should be non-negative"


def test_get_top_cpu_queries_one_liner(azure_sql_toolset):
    """Test the one-liner description generation."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    one_liner = cpu_queries_tool.get_parameterized_one_liner({})
    
    assert isinstance(one_liner, str), "One liner should be a string"
    assert len(one_liner) > 0, "One liner should not be empty"
    
    db_config = azure_sql_toolset.database_config()
    assert db_config.server_name in one_liner
    assert db_config.database_name in one_liner
    assert "Retrieved top CPU consuming queries" in one_liner


def test_get_top_cpu_queries_report_structure_integrity(azure_sql_toolset):
    """Test that the report has proper markdown structure."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    result = cpu_queries_tool.invoke({})
    
    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data
    
    # Should start with main header
    assert report_data.startswith("# Top CPU Consuming Queries Report")
    
    # Should have proper markdown headers
    headers = ["#", "##", "###"]
    for header in headers:
        assert header in report_data, f"Should have '{header}' markdown headers"
    
    # Should have proper markdown formatting
    assert "**" in report_data, "Should have bold text formatting"
    
    # If there are queries, should have proper SQL code blocks
    if "```sql" in report_data:
        # Count opening and closing code blocks
        opening_blocks = report_data.count("```sql")
        closing_blocks = report_data.count("```") - opening_blocks
        assert opening_blocks == closing_blocks, "SQL code blocks should be properly closed"


def test_get_top_cpu_queries_performance_reasonable(azure_sql_toolset):
    """Test that the query executes in reasonable time."""
    cpu_queries_tool = GetTopCPUQueries(azure_sql_toolset)
    
    import time
    start_time = time.time()
    result = cpu_queries_tool.invoke({"top_count": 5})  # Small count for speed
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    assert result.status == ToolResultStatus.SUCCESS
    assert execution_time < 30, f"Query should complete within 30 seconds, took {execution_time:.2f}s"