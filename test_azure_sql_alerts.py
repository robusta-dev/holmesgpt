#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime, timezone

# Add the project root to sys.path so we can import modules
sys.path.insert(0, '/home/nherment/workspace/robusta-dev/holmesgpt')

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import (
    AzureSQLToolset, 
    GetActiveAlerts,
    AzureSQLConfig,
    AzureSQLDatabaseConfig
)

def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("🔍 Azure SQL Active Alerts Test")
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
        print("\nPlease set the following environment variables:")
        for var in required_env_vars:
            print(f"  export {var}=<your_value>")
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
        
        # Create and invoke the GetActiveAlerts tool
        print("\n🚨 Retrieving active alerts...")
        alerts_tool = GetActiveAlerts(toolset)
        
        # Enable more detailed logging for this call
        azure_logger = logging.getLogger("azure")
        azure_logger.setLevel(logging.INFO)
        
        result = alerts_tool._invoke({})
        
        if result.status.value == "success":
            print("✅ Successfully retrieved alerts!")
            print("\n" + "="*60)
            print("ACTIVE ALERTS REPORT")
            print("="*60)
            print(result.data)
        else:
            print(f"❌ Failed to retrieve alerts: {result.error}")
            print(f"Status: {result.status.value}")
            if hasattr(result, 'data') and result.data:
                print(f"Additional data: {result.data}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        logging.exception("Detailed error:")

if __name__ == "__main__":
    main()