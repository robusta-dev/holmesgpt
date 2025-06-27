"""
Integration test for Azure SQL GenerateHealthReport tool.
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
from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import AzureSQLToolset, GenerateHealthReport

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


def test_generate_health_report_prerequisites(azure_sql_config):
    """Test that the toolset prerequisites are met."""
    toolset = AzureSQLToolset()
    ready, message = toolset.prerequisites_callable(azure_sql_config)
    assert ready, f"Prerequisites failed: {message}"
    assert not message, f"Unexpected message: {message}"


def test_generate_health_report_success(azure_sql_toolset):
    """Test successful generation of health report."""
    health_report_tool = GenerateHealthReport(azure_sql_toolset)
    result = health_report_tool.invoke({})
    
    assert result.status == ToolResultStatus.SUCCESS, f"Tool failed: {result.error}"
    assert result.data, "Health report data should not be empty"
    assert not result.error, f"Unexpected error: {result.error}"
    
    # Verify report structure and content
    report_data = result.data
    assert isinstance(report_data, str), "Report data should be a string"
    assert len(report_data) > 0, "Report should not be empty"
    
    # Check for required report sections
    assert "# Azure SQL Database Health Report" in report_data
    assert "## Operations Status" in report_data
    assert "## Resource Usage" in report_data
    
    # Check for database information
    db_config = azure_sql_toolset.database_config()
    assert db_config.database_name in report_data
    assert db_config.server_name in report_data
    
    # Check timestamp format
    assert "Generated:" in report_data
    
    # Verify operations section has content
    operations_section = report_data.split("## Operations Status")[1].split("##")[0]
    assert operations_section.strip(), "Operations section should have content"
    
    # Check that we have either operations data or error message
    assert ("Active Operations:" in operations_section or 
            "No active operations" in operations_section), \
            "Operations section should show status or error"
    
    # Verify resource usage section has content
    usage_section = report_data.split("## Resource Usage")[1] if "## Resource Usage" in report_data else ""
    assert usage_section.strip(), "Resource usage section should have content"
    
    # Check that we have either usage data or error message
    assert (any(unit in usage_section for unit in ["MB", "GB", "KB", "Bytes", "%"]) or 
            "No usage data available" in usage_section), \
            "Resource usage section should show data or error"


def test_generate_health_report_data_not_empty(azure_sql_toolset):
    """Test that the health report contains meaningful data."""
    health_report_tool = GenerateHealthReport(azure_sql_toolset)
    result = health_report_tool.invoke({})
    
    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data
    
    assert report_data
    # Count lines to ensure we have substantial content
    lines = [line.strip() for line in report_data.split('\n') if line.strip()]
    assert len(lines) >= 5, f"Report should have at least 5 lines of content, got {len(lines)}"
    
    # Check for specific data patterns that indicate real data
    # Either we should have actual data or clear error messages
    has_operations_data = "Active Operations:" in report_data
    has_operations_empty = "No active operations" in report_data
    
    assert (has_operations_data or has_operations_empty), \
        "Should have operations data, empty status, or error message"
    
    has_usage_data = any(unit in report_data for unit in ["MB", "GB", "KB", "%"])
    has_usage_empty = "No usage data available" in report_data
    
    assert (has_usage_data or has_usage_empty ), \
        "Should have usage data, empty status, or error message"


def test_generate_health_report_handles_api_errors_gracefully(azure_sql_toolset):
    """Test that the tool handles API errors gracefully."""
    health_report_tool = GenerateHealthReport(azure_sql_toolset)
    
    # This test ensures the tool doesn't crash even if some API calls fail
    result = health_report_tool.invoke({})
    
    # The tool should always return a result, even if some data is missing
    assert result.status in [ToolResultStatus.SUCCESS, ToolResultStatus.ERROR]
    
    if result.status == ToolResultStatus.SUCCESS:
        # If successful, should have a report with either data or error messages
        assert result.data
        assert isinstance(result.data, str)
        assert len(result.data) > 0
    else:
        # If error, should have an error message
        assert result.error
        assert isinstance(result.error, str)
        assert len(result.error) > 0