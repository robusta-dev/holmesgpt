#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime, timezone

# Add the project root to sys.path so we can import modules
sys.path.insert(0, '/home/nherment/workspace/robusta-dev/holmesgpt')

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import AzureSQLToolset
from holmes.plugins.toolsets.azure_sql.tools.get_alert_history import GetAlertHistory
from holmes.plugins.toolsets.azure_sql.azure_base_toolset import (
    AzureSQLConfig,
    AzureSQLDatabaseConfig
)

def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("🔍 Azure SQL Alert History Test")
    print("=" * 50)
    
    # Read configuration from environment variables
    required_env_vars = [
        'AZURE_SQL_SUBSCRIPTION_ID',
        'AZURE_SQL_RESOURCE_GROUP', 
        'AZURE_SQL_SERVER',
        'AZURE_SQL_DATABASE'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Optional authentication variables
    tenant_id = os.getenv('AZURE_SQL_TENANT_ID')
    client_id = os.getenv('AZURE_SQL_CLIENT_ID') 
    client_secret = os.getenv('AZURE_SQL_CLIENT_SECRET')
    
    print("✅ Environment variables found")
    print(f"   Subscription: {os.getenv('AZURE_SQL_SUBSCRIPTION_ID')}")
    print(f"   Resource Group: {os.getenv('AZURE_SQL_RESOURCE_GROUP')}")
    print(f"   Server: {os.getenv('AZURE_SQL_SERVER')}")
    print(f"   Database: {os.getenv('AZURE_SQL_DATABASE')}")
    
    # Create configuration
    database_config = AzureSQLDatabaseConfig(
        subscription_id=os.getenv('AZURE_SQL_SUBSCRIPTION_ID'),
        resource_group=os.getenv('AZURE_SQL_RESOURCE_GROUP'),
        server_name=os.getenv('AZURE_SQL_SERVER'),
        database_name=os.getenv('AZURE_SQL_DATABASE')
    )
    
    config = AzureSQLConfig(
        database=database_config,
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
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
        print("\n📊 Retrieving alert history (last 7 days)...")
        history_tool = GetAlertHistory(toolset)
        
        # Test with different time windows
        test_cases = [
            {"hours_back": 168, "description": "Last 7 days"},
            {"hours_back": 72, "description": "Last 3 days"},
            {"hours_back": 24, "description": "Last 24 hours"}
        ]
        
        for test_case in test_cases:
            print(f"\n🔍 Testing: {test_case['description']} ({test_case['hours_back']} hours)")
            result = history_tool._invoke(test_case)
            
            if result.status.value == "success":
                print("✅ Successfully retrieved alert history!")
                print("\n" + "="*60)
                print(f"ALERT HISTORY REPORT - {test_case['description'].upper()}")
                print("="*60)
                print(result.data)
                print("\n" + "="*60)
                break  # Show first successful result
            else:
                print(f"❌ Failed to retrieve alert history: {result.error}")
                if hasattr(result, 'data') and result.data:
                    print(f"Additional data: {result.data}")
        
        # Also test error scenarios
        print("\n🔧 Testing error handling...")
        error_result = history_tool._invoke({"hours_back": -1})  # Invalid parameter
        print(f"Error test result: {error_result.status.value}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        logging.exception("Detailed error:")

if __name__ == "__main__":
    main()