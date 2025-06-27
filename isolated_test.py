#!/usr/bin/env python3

import sys
import traceback

# Add the project root to the Python path
sys.path.insert(0, "/home/nherment/workspace/robusta-dev/holmesgpt")

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import (
    AzureSQLToolset,
    AnalyzeDatabaseStorage,
)


def test_build_storage_report():
    # Create mock data that mirrors what we saw in debug
    storage_data = {
        "summary": {
            "database_name": "nicolas-test",
            "total_data_size_mb": 4560.00,
            "used_data_size_mb": 4509.25,
            "total_log_size_mb": 264.00,
            "used_log_size_mb": 13.32,
            "total_database_size_mb": 4824.00,
            "total_used_size_mb": 4522.57,
            "data_files_count": 1,
            "log_files_count": 1,
        },
        "file_details": [
            {
                "database_name": "nicolas-test",
                "file_type": "FILESTREAM",
                "logical_name": "XTP",
                "physical_name": "3addd6ea-85e2-4bd2-a9c0-63dd92ddb35a.xtp",
                "size_mb": 0.00,
                "used_mb": None,
                "free_mb": None,
                "used_percent": None,
                "max_size": "Unlimited",
                "is_percent_growth": False,
                "growth_setting": "0.000000000000 MB",
                "file_state": "ONLINE",
            }
        ],
        "table_usage": [],
        "growth_trend": {"error": "some error"},
        "metrics": {"error": "some error"},
        "tempdb": {"error": "some error"},
    }

    # Mock database config
    class MockDbConfig:
        database_name = "nicolas-test"
        server_name = "nicolas-test"

    db_config = MockDbConfig()

    # Create storage tool and try to build report
    toolset = AzureSQLToolset()
    storage_tool = AnalyzeDatabaseStorage(toolset)

    try:
        report_text = storage_tool._build_storage_report(
            db_config, storage_data, 24, 10
        )
        print("SUCCESS!")
        print("=" * 60)
        print(report_text)
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    test_build_storage_report()
