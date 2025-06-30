#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime, timezone

# Add the project root to sys.path so we can import modules
sys.path.insert(0, "/home/nherment/workspace/robusta-dev/holmesgpt")

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import AzureSQLToolset
from holmes.plugins.toolsets.azure_sql.tools.get_alert_history import GetAlertHistory
from holmes.plugins.toolsets.azure_sql.azure_base_toolset import (
    AzureSQLConfig,
    AzureSQLDatabaseConfig,
)


def main():
    # Set up verbose logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("🔍 Azure SQL Alert History Detailed Test")
    print("=" * 60)

    # Read configuration from environment variables
    required_env_vars = [
        "AZURE_SQL_SUBSCRIPTION_ID",
        "AZURE_SQL_RESOURCE_GROUP",
        "AZURE_SQL_SERVER",
        "AZURE_SQL_DATABASE",
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    # Optional authentication variables
    tenant_id = os.getenv("AZURE_SQL_TENANT_ID")
    client_id = os.getenv("AZURE_SQL_CLIENT_ID")
    client_secret = os.getenv("AZURE_SQL_CLIENT_SECRET")

    print("✅ Environment variables found")
    print(f"   Subscription: {os.getenv('AZURE_SQL_SUBSCRIPTION_ID')}")
    print(f"   Resource Group: {os.getenv('AZURE_SQL_RESOURCE_GROUP')}")
    print(f"   Server: {os.getenv('AZURE_SQL_SERVER')}")
    print(f"   Database: {os.getenv('AZURE_SQL_DATABASE')}")

    # Create configuration
    database_config = AzureSQLDatabaseConfig(
        subscription_id=os.getenv("AZURE_SQL_SUBSCRIPTION_ID"),
        resource_group=os.getenv("AZURE_SQL_RESOURCE_GROUP"),
        server_name=os.getenv("AZURE_SQL_SERVER"),
        database_name=os.getenv("AZURE_SQL_DATABASE"),
    )

    config = AzureSQLConfig(
        database=database_config,
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )

    try:
        # Initialize the toolset
        print("\n🔧 Initializing Azure SQL Toolset...")
        toolset = AzureSQLToolset()

        # Test prerequisites
        config_dict = config.model_dump()
        success, message = toolset.prerequisites_callable(config_dict)

        if not success:
            print(f"❌ Prerequisites failed: {message}")
            sys.exit(1)

        print("✅ Prerequisites passed")

        # Create and invoke the GetAlertHistory tool
        print("\n📊 Testing different time ranges for alert history...")
        history_tool = GetAlertHistory(toolset)

        # Test with different time windows including periods when we know activity happened
        test_cases = [
            {"hours_back": 24, "description": "Last 24 hours"},
            {"hours_back": 72, "description": "Last 3 days"},
            {"hours_back": 168, "description": "Last 7 days"},
            {"hours_back": 336, "description": "Last 14 days"},  # Include last Friday
            {"hours_back": 720, "description": "Last 30 days"},  # Cast a wider net
        ]

        found_alerts = False

        for test_case in test_cases:
            print(
                f"\n🔍 Testing: {test_case['description']} ({test_case['hours_back']} hours)"
            )
            print("=" * 40)

            result = history_tool._invoke(test_case)

            if result.status.value == "success":
                print("✅ API call successful!")
                print("\n" + "=" * 60)
                print(f"ALERT HISTORY REPORT - {test_case['description'].upper()}")
                print("=" * 60)
                print(result.data)
                print("\n" + "=" * 60)

                # Check if we found any alerts
                if "No alerts found" not in result.data:
                    found_alerts = True
                    print(f"🎉 Found alerts in {test_case['description']}!")
                    break  # Stop at first successful result with alerts
                else:
                    print(f"ℹ️  No alerts found in {test_case['description']}")
            else:
                print(f"❌ Failed to retrieve alert history: {result.error}")
                if hasattr(result, "data") and result.data:
                    print(f"Additional data: {result.data}")

        if not found_alerts:
            print("\n🤔 No alerts found in any time period. This could mean:")
            print("   • No alerts were actually triggered")
            print("   • Alerts are stored differently than expected")
            print("   • We need to look at different activity types")
            print("   • The resource IDs don't match exactly")

            # Let's also try to look at ALL activity logs without filtering by level
            print("\n🔧 Let's try a broader search for ANY activity...")

            # Create a custom test to see what activity logs exist
            try:
                from holmes.plugins.toolsets.azure_sql.apis.alert_monitoring_api import (
                    AlertMonitoringAPI,
                )
                from azure.identity import ClientSecretCredential

                credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )

                alert_api = AlertMonitoringAPI(
                    credential, database_config.subscription_id
                )

                # Try to get a small sample of any activity logs
                from datetime import timedelta

                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=24)

                database_resource_id = (
                    f"/subscriptions/{database_config.subscription_id}/"
                    f"resourceGroups/{database_config.resource_group}/"
                    f"providers/Microsoft.Sql/servers/{database_config.server_name}/"
                    f"databases/{database_config.database_name}"
                )

                filter_query = (
                    f"eventTimestamp ge '{start_time.isoformat()}' and "
                    f"eventTimestamp le '{end_time.isoformat()}'"
                )

                print(f"🔍 Searching for ANY activity logs with filter: {filter_query}")

                activity_logs = alert_api.monitor_client.activity_logs.list(
                    filter=filter_query
                )
                activity_count = 0
                relevant_count = 0

                for log_entry in activity_logs:
                    activity_count += 1
                    resource_id = str(getattr(log_entry, "resource_id", ""))
                    if database_resource_id.lower() in resource_id.lower():
                        relevant_count += 1
                        print(
                            f"   📋 Found relevant activity: {getattr(log_entry, 'operation_name', 'Unknown')} - Level: {getattr(log_entry, 'level', 'Unknown')}"
                        )

                    if (
                        activity_count >= 20
                    ):  # Limit to first 20 to avoid overwhelming output
                        break

                print(
                    f"📊 Found {activity_count} total activity log entries, {relevant_count} relevant to our database"
                )

            except Exception as e:
                print(f"❌ Error in broad activity search: {e}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        logging.exception("Detailed error:")


if __name__ == "__main__":
    main()
