#!/usr/bin/env python3

import os
import sys
import logging

# Add the project root to the Python path
sys.path.insert(0, "/home/nherment/workspace/robusta-dev/holmesgpt")

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import (
    AzureSQLToolset,
    AnalyzeDatabaseStorage,
)


def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create the toolset
    toolset = AzureSQLToolset()

    # Mock config - this should come from your environment variables
    config = {
        "database": {
            "subscription_id": os.getenv("AZURE_SQL_SUBSCRIPTION_ID", ""),
            "resource_group": os.getenv("AZURE_SQL_RESOURCE_GROUP", ""),
            "server_name": os.getenv("AZURE_SQL_SERVER", ""),
            "database_name": os.getenv("AZURE_SQL_DATABASE", ""),
        },
        "tenant_id": os.getenv("AZURE_SQL_TENANT_ID"),
        "client_id": os.getenv("AZURE_SQL_CLIENT_ID"),
        "client_secret": os.getenv("AZURE_SQL_CLIENT_SECRET"),
    }

    print("Config being used:")
    for key, value in config.items():
        if key == "client_secret":
            print(f"  {key}: {'*' * len(str(value)) if value else 'None'}")
        else:
            print(f"  {key}: {value}")
    print()

    # Initialize the toolset with the config
    success, error_msg = toolset.prerequisites_callable(config)

    if not success:
        print(f"Failed to initialize toolset: {error_msg}")
        return

    print("Toolset initialized successfully!")
    print()

    # Create the AnalyzeDatabaseStorage tool
    storage_tool = AnalyzeDatabaseStorage(toolset)

    # Run the tool with default parameters
    params = {"hours_back": 24, "top_tables": 10}

    print("Running AnalyzeDatabaseStorage tool...")
    print(f"Parameters: {params}")
    print()

    # Try to gather data manually to identify the issue
    try:
        db_config = toolset.database_config()
        api_client = toolset.api_client()

        from holmes.plugins.toolsets.azure_sql.storage_analysis_api import (
            StorageAnalysisAPI,
        )

        storage_api = StorageAnalysisAPI(
            credential=api_client.credential,
            subscription_id=db_config.subscription_id,
            sql_username=api_client.sql_username,
            sql_password=api_client.sql_password,
        )

        # Gather storage data manually and test the report building step by step
        storage_data = {}

        print("Getting storage summary...")
        storage_data["summary"] = storage_api.get_storage_summary(
            db_config.server_name, db_config.database_name
        )

        print("Getting file details...")
        storage_data["file_details"] = storage_api.get_database_size_details(
            db_config.server_name, db_config.database_name
        )

        print("Getting table usage...")
        storage_data["table_usage"] = storage_api.get_table_space_usage(
            db_config.server_name, db_config.database_name, 10
        )

        print("Getting growth trend...")
        storage_data["growth_trend"] = storage_api.get_storage_growth_trend(
            db_config.server_name, db_config.database_name
        )

        print("Getting storage metrics...")
        storage_data["metrics"] = storage_api.get_storage_metrics(
            db_config.resource_group, db_config.server_name, db_config.database_name, 24
        )

        print("Getting tempdb usage...")
        storage_data["tempdb"] = storage_api.get_tempdb_usage(
            db_config.server_name, db_config.database_name
        )

        print("Building report...")
        report_text = storage_tool._build_storage_report(
            db_config, storage_data, 24, 10
        )

        print("=" * 80)
        print("STORAGE ANALYSIS REPORT OUTPUT:")
        print("=" * 80)
        print(report_text)

    except Exception as e:
        print("=" * 80)
        print("EXCEPTION DURING EXECUTION:")
        print("=" * 80)
        import traceback

        print(traceback.format_exc())
        print(f"Exception: {e}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
