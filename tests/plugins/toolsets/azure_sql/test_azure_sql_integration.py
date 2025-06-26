
import pytest
import os
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import (
    AzureSQLToolset,
    AzureSQLConfig,
    AzureSQLDatabaseConfig,
    GetTopCPUQueries,
    GetSlowQueries,
)
from holmes.plugins.toolsets.azure_sql.azure_sql_api import AzureSQLAPIClient

@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "azure_sql_databases": [
            {
                "name": "test-db",
                "subscription_id": os.getenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id"),
                "resource_group": os.getenv("AZURE_RESOURCE_GROUP", "test-resource-group"),
                "server_name": os.getenv("AZURE_SQL_SERVER", "test-server"),
                "database_name": os.getenv("AZURE_SQL_DATABASE", "test-database"),
            }
        ],
        "tenant_id": os.getenv("AZURE_TENANT_ID"),
        "client_id": os.getenv("AZURE_CLIENT_ID"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
    }

def test_query_performance_tools_direct_api_calls(sample_config):
        """Test direct API calls to Azure SQL Query Store for performance data."""
        # Create credential
        if sample_config.get("tenant_id") and sample_config.get("client_id") and sample_config.get("client_secret"):
            credential = ClientSecretCredential(
                tenant_id=sample_config["tenant_id"],
                client_id=sample_config["client_id"],
                client_secret=sample_config["client_secret"]
            )
        else:
            credential = DefaultAzureCredential()
        
        # Get database config
        db_config = sample_config["azure_sql_databases"][0]
        
        # Create API client with SQL authentication fallback
        sql_username = os.getenv("AZURE_SQL_USERNAME")
        sql_password = os.getenv("AZURE_SQL_PASSWORD")
        
        api_client = AzureSQLAPIClient(
            credential, 
            db_config["subscription_id"],
            sql_username=sql_username,
            sql_password=sql_password
        )
        
        try:
            # Test direct API call for top CPU queries
            cpu_results = api_client.get_top_cpu_queries(
                subscription_id=db_config["subscription_id"],
                resource_group=db_config["resource_group"],
                server_name=db_config["server_name"],
                database_name=db_config["database_name"],
                top_count=5,
                hours_back=24
            )
            
            # Verify results structure
            assert isinstance(cpu_results, list)
            print(f"CPU queries API returned {len(cpu_results)} results")
            print(cpu_results)
            # If results exist, verify structure
            if cpu_results:
                first_result = cpu_results[0]
                expected_fields = ['query_sql_text', 'avg_cpu_time', 'execution_count', 'total_cpu_time']
                for field in expected_fields:
                    assert field in first_result, f"Missing field '{field}' in CPU query result"
                print(f"Sample CPU query result: {first_result}")
            
            # Test direct API call for slow queries
            slow_results = api_client.get_slow_queries(
                subscription_id=db_config["subscription_id"],
                resource_group=db_config["resource_group"],
                server_name=db_config["server_name"],
                database_name=db_config["database_name"],
                top_count=5,
                hours_back=24
            )
            
            # Verify results structure
            assert isinstance(slow_results, list)
            print(f"Slow queries API returned {len(slow_results)} results")
            
            print(slow_results)
            # If results exist, verify structure
            if slow_results:
                first_result = slow_results[0]
                expected_fields = ['query_sql_text', 'avg_duration', 'execution_count', 'total_duration']
                for field in expected_fields:
                    assert field in first_result, f"Missing field '{field}' in slow query result"
                print(f"Sample slow query result: {first_result}")
            assert False
                
        except Exception as e:
            error_msg = str(e)
            if "Query Store" in error_msg or "query_store" in error_msg:
                pytest.fail(f"Query Store not available or enabled on this database: {error_msg}")
            elif "query_id" in error_msg or "query_text_id" in error_msg:
                pytest.fail(f"Query Store tables not available - Query Store may not be enabled: {error_msg}")
            elif "Invalid column name" in error_msg and ("query_" in error_msg or "sys.query_store" in error_msg):
                pytest.fail(f"Query Store schema not available - Query Store is not enabled on this database: {error_msg}")
            elif "ODBC" in error_msg and "pyodbc" in error_msg:
                pytest.fail(f"ODBC connection error: {error_msg}")
            elif "permission" in error_msg.lower() or "forbidden" in error_msg.lower():
                pytest.fail(f"Insufficient permissions for Query Store access: {error_msg}")
            elif "authentication" in error_msg.lower() or "login" in error_msg.lower():
                pytest.fail(f"Authentication failed for database access: {error_msg}")
            else:
                pytest.fail(f"Unexpected error during API calls: {error_msg}")