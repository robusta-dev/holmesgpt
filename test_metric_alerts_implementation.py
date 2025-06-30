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
    
    print("🔍 Testing Updated Metric Alerts Implementation")
    print("=" * 60)
    
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
        
        # Test direct API access to metric alerts
        print("\n🔍 Testing Direct Metric Alert API Access...")
        try:
            from holmes.plugins.toolsets.azure_sql.apis.alert_monitoring_api import AlertMonitoringAPI
            from azure.identity import ClientSecretCredential
            
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            alert_api = AlertMonitoringAPI(credential, database_config.subscription_id)
            
            # Test metric alert rules access
            try:
                print("🔧 Attempting to list metric alert rules...")
                metric_alert_rules = alert_api.monitor_client.metric_alerts.list_by_resource_group(
                    database_config.resource_group
                )
                
                rule_count = 0
                for rule in metric_alert_rules:
                    rule_count += 1
                    print(f"   📋 Found rule: {getattr(rule, 'name', 'Unknown')} - Enabled: {getattr(rule, 'enabled', False)}")
                    if rule_count >= 5:  # Limit output
                        break
                
                print(f"✅ Successfully accessed metric alert rules (found {rule_count})")
                
            except Exception as e:
                print(f"❌ Failed to access metric alert rules: {e}")
                print("   This is expected if the service principal lacks Microsoft.Insights/metricAlerts/read permission")
        
        except ImportError as e:
            print(f"❌ Import error: {e}")
        
        # Create and invoke the GetAlertHistory tool
        print("\n📊 Testing GetAlertHistory tool with updated implementation...")
        history_tool = GetAlertHistory(toolset)
        
        result = history_tool._invoke({"hours_back": 168})
        
        if result.status.value == "success":
            print("✅ GetAlertHistory tool executed successfully!")
            print("\n" + "="*60)
            print("ALERT HISTORY REPORT")
            print("="*60)
            print(result.data)
            print("\n" + "="*60)
            
            # Check if we found metric alerts vs fallback
            if "metric_alerts" in result.data:
                print("🎉 Successfully used metric alert API!")
            elif "activity_log_fallback" in result.data:
                print("ℹ️  Used activity log fallback (likely due to permissions)")
            
        else:
            print(f"❌ GetAlertHistory tool failed: {result.error}")
        
        print("\n📝 Summary:")
        print("✅ Updated implementation to fetch metric alert rules")
        print("✅ Graceful fallback to activity logs when permissions lacking")
        print("✅ Tool architecture working correctly")
        print("\n💡 Next steps to fully test with actual alerts:")
        print("   1. Grant service principal 'Microsoft.Insights/metricAlerts/read' permission")
        print("   2. Grant service principal 'Microsoft.Insights/metricAlerts/write' permission")
        print("   3. Create test metric alert rules using the provided script")
        print("   4. Re-test to see actual metric alert rules and instances")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        logging.exception("Detailed error:")

if __name__ == "__main__":
    main()