"""
Integration test for Azure SQL GeneratePerformanceReport tool.
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
    GeneratePerformanceReport,
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


def test_generate_performance_report_prerequisites(azure_sql_config):
    """Test that the toolset prerequisites are met."""
    toolset = AzureSQLToolset()
    ready, message = toolset.prerequisites_callable(azure_sql_config)
    assert ready, f"Prerequisites failed: {message}"
    assert not message, f"Unexpected message: {message}"


def test_generate_performance_report_success(azure_sql_toolset):
    """Test successful generation of performance report."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    result = performance_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS, f"Tool failed: {result.error}"
    assert result.data, "Performance report data should not be empty"
    assert not result.error, f"Unexpected error: {result.error}"

    # Verify report structure and content
    report_data = result.data
    assert isinstance(report_data, str), "Report data should be a string"
    assert len(report_data) > 0, "Report should not be empty"

    # Check for required report sections
    assert "# Azure SQL Database Performance Report" in report_data
    assert "## Automatic Tuning Status" in report_data
    assert "## Performance Advisors" in report_data
    assert "## Performance Recommendations" in report_data

    # Check for database information
    db_config = azure_sql_toolset.database_config()
    assert db_config.database_name in report_data
    assert db_config.server_name in report_data

    # Check timestamp format
    assert "Generated:" in report_data


def test_automatic_tuning_section_has_real_data(azure_sql_toolset):
    """Test that automatic tuning section contains real data, not errors."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    result = performance_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Extract automatic tuning section
    tuning_section = report_data.split("## Automatic Tuning Status")[1].split("##")[0]
    assert tuning_section.strip(), "Automatic tuning section should have content"

    # Should NOT have error messages
    assert (
        "Error retrieving auto-tuning data:" not in tuning_section
    ), "Automatic tuning section should not contain API errors"

    # Should have actual state information
    assert (
        "Desired State" in tuning_section or "Actual State" in tuning_section
    ), "Should have tuning state information"

    # Should not have "Unknown" values for states
    assert (
        "Desired State**: Unknown" not in tuning_section
    ), "Should have real desired state value, not 'Unknown'"
    assert (
        "Actual State**: Unknown" not in tuning_section
    ), "Should have real actual state value, not 'Unknown'"


def test_performance_advisors_section_has_data(azure_sql_toolset):
    """Test that performance advisors section contains meaningful data."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    result = performance_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Extract advisors section (look for next ## heading, not ###)
    if "## Performance Advisors" in report_data:
        advisors_part = report_data.split("## Performance Advisors")[1]
        # Find the next ## section (not ###)
        import re

        next_section_match = re.search(r"\n## ", advisors_part)
        if next_section_match:
            advisors_section = advisors_part[: next_section_match.start()]
        else:
            advisors_section = advisors_part
    else:
        advisors_section = ""

    assert advisors_section.strip(), "Performance advisors section should have content"

    # Should NOT have error messages
    assert (
        "Error retrieving advisors:" not in advisors_section
    ), "Performance advisors section should not contain API errors"

    # Should have either advisor data or explicit "no advisors" message
    has_advisors = (
        "Auto Execute" in advisors_section and "Last Checked" in advisors_section
    )
    has_no_advisors_msg = "No performance advisors available" in advisors_section

    assert (
        has_advisors or has_no_advisors_msg
    ), "Should have either advisor data or clear 'no advisors' message"

    if has_advisors:
        # If there are advisors, they should not have "Unknown" values
        assert (
            "Auto Execute**: Unknown" not in advisors_section
        ), "Advisors should have real auto execute status, not 'Unknown'"


def test_performance_recommendations_section_valid(azure_sql_toolset):
    """Test that performance recommendations section is valid."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    result = performance_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Extract recommendations section
    recommendations_section = (
        report_data.split("## Performance Recommendations")[1]
        if "## Performance Recommendations" in report_data
        else ""
    )
    assert (
        recommendations_section.strip()
    ), "Performance recommendations section should have content"

    # Should have either recommendations or explicit message
    has_active_recommendations = (
        "Active Recommendations Found" in recommendations_section
    )
    has_no_active_recommendations = (
        "No active performance recommendations" in recommendations_section
    )
    has_no_recommendations = (
        "No performance recommendations available" in recommendations_section
    )

    assert (
        has_active_recommendations
        or has_no_active_recommendations
        or has_no_recommendations
    ), "Should have clear status about recommendations"


def test_no_api_errors_in_report(azure_sql_toolset):
    """Test that the report contains no API errors."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    result = performance_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Should not contain any error messages indicating API failures
    error_indicators = [
        "Error retrieving auto-tuning data:",
        "Error retrieving advisors:",
        "Failed to get recommendations",
        "Exception:",
        "Error:",
    ]

    for error_indicator in error_indicators:
        assert (
            error_indicator not in report_data
        ), f"Report should not contain API error: '{error_indicator}'"


def test_performance_report_has_substantial_content(azure_sql_toolset):
    """Test that the performance report contains substantial content."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    result = performance_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Count lines to ensure we have substantial content
    lines = [line.strip() for line in report_data.split("\n") if line.strip()]
    assert (
        len(lines) >= 15
    ), f"Report should have at least 15 lines of content, got {len(lines)}"

    # Should have multiple sections with content
    sections = [
        "## Automatic Tuning Status",
        "## Performance Advisors",
        "## Performance Recommendations",
    ]

    for section in sections:
        assert section in report_data, f"Missing required section: {section}"
        # Improved section content extraction
        if section in report_data:
            section_part = report_data.split(section)[1]
            # Find the next ## section (not ###)
            import re

            next_section_match = re.search(r"\n## ", section_part)
            if next_section_match:
                section_content = section_part[: next_section_match.start()]
            else:
                section_content = section_part
            assert (
                len(section_content.strip()) > 0
            ), f"Section '{section}' should have content"


def test_generate_performance_report_one_liner(azure_sql_toolset):
    """Test the one-liner description generation."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    one_liner = performance_report_tool.get_parameterized_one_liner({})

    assert isinstance(one_liner, str), "One liner should be a string"
    assert len(one_liner) > 0, "One liner should not be empty"

    db_config = azure_sql_toolset.database_config()
    assert db_config.server_name in one_liner
    assert db_config.database_name in one_liner
    assert "Generated performance report" in one_liner


def test_performance_data_structure_integrity(azure_sql_toolset):
    """Test that the performance data has proper structure and field names."""
    performance_report_tool = GeneratePerformanceReport(azure_sql_toolset)
    result = performance_report_tool.invoke({})

    assert result.status == ToolResultStatus.SUCCESS
    report_data = result.data

    # Check that we don't have field name issues like we had with health report
    # Allow "Unknown" only in context of "No" messages (like "No active recommendations")
    unknown_lines = [
        line
        for line in report_data.split("\n")
        if "Unknown" in line and "No " not in line
    ]
    assert (
        len(unknown_lines) == 0
    ), f"Should not have 'Unknown' values in: {unknown_lines}"

    # Verify sections have meaningful content structure
    if "Desired State" in report_data:
        # If we have desired state, it should have a real value
        lines_with_desired_state = [
            line for line in report_data.split("\n") if "Desired State" in line
        ]
        for line in lines_with_desired_state:
            assert "Unknown" not in line, f"Desired state should not be Unknown: {line}"

    if "Actual State" in report_data:
        # If we have actual state, it should have a real value
        lines_with_actual_state = [
            line for line in report_data.split("\n") if "Actual State" in line
        ]
        for line in lines_with_actual_state:
            assert "Unknown" not in line, f"Actual state should not be Unknown: {line}"
