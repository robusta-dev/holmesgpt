#!/usr/bin/env python3

import os
import sys
import logging
import traceback

# Add the project root to the Python path
sys.path.insert(0, "/home/nherment/workspace/robusta-dev/holmesgpt")

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import AzureSQLToolset
from holmes.plugins.toolsets.azure_sql.storage_analysis_api import StorageAnalysisAPI


def debug_storage_data():
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

    # Initialize the toolset with the config
    success, error_msg = toolset.prerequisites_callable(config)

    if not success:
        print(f"Failed to initialize toolset: {error_msg}")
        return

    print("Toolset initialized successfully!")
    print()

    db_config = toolset.database_config()
    api_client = toolset.api_client()
    storage_api = StorageAnalysisAPI(
        credential=api_client.credential,
        subscription_id=db_config.subscription_id,
        sql_username=api_client.sql_username,
        sql_password=api_client.sql_password,
    )

    # Debug each storage data source individually
    print("=" * 60)
    print("STORAGE SUMMARY:")
    try:
        summary = storage_api.get_storage_summary(
            db_config.server_name, db_config.database_name
        )
        print(f"Summary data: {summary}")
        for key, value in summary.items():
            print(f"  {key}: {value} (type: {type(value)})")
    except Exception as e:
        print(f"Error getting storage summary: {e}")
        traceback.print_exc()

    print("=" * 60)
    print("FILE DETAILS:")
    try:
        file_details = storage_api.get_database_size_details(
            db_config.server_name, db_config.database_name
        )
        print(f"File details data: {file_details}")
        for file_info in file_details:
            print(f"File info: {file_info}")
            for key, value in file_info.items():
                print(f"  {key}: {value} (type: {type(value)})")
    except Exception as e:
        print(f"Error getting file details: {e}")
        traceback.print_exc()

    print("=" * 60)
    print("TABLE USAGE:")
    try:
        table_usage = storage_api.get_table_space_usage(
            db_config.server_name, db_config.database_name, 10
        )
        print(f"Table usage data: {table_usage}")
        for table in table_usage[:3]:  # Just first 3
            print(f"Table info: {table}")
            for key, value in table.items():
                print(f"  {key}: {value} (type: {type(value)})")
    except Exception as e:
        print(f"Error getting table usage: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    debug_storage_data()
