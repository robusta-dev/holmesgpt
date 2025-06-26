#   Azure Credentials Setup Guide

#   Option 1: Service Principal (Recommended for CI/CD)

#   1. Create a Service Principal in Azure:
#   az ad sp create-for-rbac --name "holmesgpt-azure-sql" --role contributor --scopes /subscriptions/YOUR_SUBSCRIPTION_ID
#   2. Set the following environment variables:
#   export AZURE_TENANT_ID="your-tenant-id"
#   export AZURE_CLIENT_ID="your-client-id"
#   export AZURE_CLIENT_SECRET="your-client-secret"
#   export AZURE_SUBSCRIPTION_ID="your-subscription-id"
#   export AZURE_RESOURCE_GROUP="your-resource-group-name"
#   export AZURE_SQL_SERVER="your-sql-server-name"
#   export AZURE_SQL_DATABASE="your-database-name"

#   Option 2: Default Azure Credential (Recommended for local development)

#   If you're logged in via Azure CLI, you can use Default Azure Credential:

#   1. Login to Azure:
#   az login
#   2. Set these environment variables:
#   export AZURE_SUBSCRIPTION_ID="your-subscription-id"
#   export AZURE_RESOURCE_GROUP="your-resource-group-name"
#   export AZURE_SQL_SERVER="your-sql-server-name"
#   export AZURE_SQL_DATABASE="your-database-name"

#   Required Permissions

#   Your service principal or user needs these permissions on the Azure SQL database:
#   - SQL Database Contributor or Contributor role on the resource group
#   - Reader access to the subscription

#   Running the Test

#   # Run the integration test
#   python -m pytest tests/plugins/toolsets/test_azure_sql_integration.py -v

#   # Run with specific markers to skip tests requiring full setup
#   python -m pytest tests/plugins/toolsets/test_azure_sql_integration.py::TestAzureSQLIntegration::test_configuration_parsing -v

#   The test will automatically skip tests that require Azure credentials if they're not provided, making it safe to run in any environment.



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


class TestAzureSQLIntegration:
    """Integration tests for Azure SQL toolset - tests actual Azure connectivity."""
    
    @pytest.fixture
    def sample_config(self):
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

    @pytest.fixture
    def azure_sql_toolset(self):
        """Create AzureSQLToolset instance."""
        return AzureSQLToolset()

    def test_configuration_parsing(self, sample_config):
        """Test that configuration is parsed correctly."""
        config = AzureSQLConfig(**sample_config)
        
        assert len(config.azure_sql_databases) == 1
        assert config.azure_sql_databases[0].name == "test-db"
        assert config.azure_sql_databases[0].database_name == sample_config["azure_sql_databases"][0]["database_name"]

    def test_credential_setup_with_service_principal(self, azure_sql_toolset, sample_config):
        """Test credential setup with service principal."""
        # Only run if service principal credentials are provided
        if not all([sample_config.get("tenant_id"), sample_config.get("client_id"), sample_config.get("client_secret")]):
            pytest.skip("Service principal credentials not provided")
        
        success, message = azure_sql_toolset.prerequisites_callable(sample_config)
        
        # Test should pass if credentials are valid
        assert success, f"Prerequisites check failed: {message}"
        assert len(azure_sql_toolset.database_configs) == 1

    def test_credential_setup_with_default_credential(self, azure_sql_toolset):
        """Test credential setup with DefaultAzureCredential."""
        config = {
            "azure_sql_databases": [
                {
                    "name": "test-db",
                    "subscription_id": os.getenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id"),
                    "resource_group": os.getenv("AZURE_RESOURCE_GROUP", "test-resource-group"),
                    "server_name": os.getenv("AZURE_SQL_SERVER", "test-server"),
                    "database_name": os.getenv("AZURE_SQL_DATABASE", "test-database"),
                }
            ]
        }
        
        success, message = azure_sql_toolset.prerequisites_callable(config)
        
        # This might fail if not running in an Azure environment
        # but we can still test the code path
        if not success:
            assert "Failed to set up Azure authentication" in message
        else:
            # Check that api_clients dict has the expected subscription
            subscription_id = config["azure_sql_databases"][0]["subscription_id"]
            assert subscription_id in azure_sql_toolset.api_clients
            assert isinstance(azure_sql_toolset.api_clients[subscription_id], AzureSQLAPIClient)

    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SUBSCRIPTION_ID"),
            os.getenv("AZURE_RESOURCE_GROUP"), 
            os.getenv("AZURE_SQL_SERVER"),
            os.getenv("AZURE_SQL_DATABASE")
        ]),
        reason="Azure SQL database configuration not provided"
    )
    def test_api_client_connection(self, sample_config):
        """Test actual API client connection to Azure SQL."""
        # Create credential
        if sample_config.get("tenant_id") and sample_config.get("client_id") and sample_config.get("client_secret"):
            credential = ClientSecretCredential(
                tenant_id=sample_config["tenant_id"],
                client_id=sample_config["client_id"],
                client_secret=sample_config["client_secret"]
            )
        else:
            credential = DefaultAzureCredential()
        
        # Test getting a token
        try:
            token = credential.get_token("https://management.azure.com/.default")
            assert token.token is not None
            assert len(token.token) > 0
            print(f"Successfully obtained Azure token (length: {len(token.token)})")
        except ClientAuthenticationError as e:
            pytest.fail(f"Authentication failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during authentication: {e}")

    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SUBSCRIPTION_ID"),
            os.getenv("AZURE_RESOURCE_GROUP"), 
            os.getenv("AZURE_SQL_SERVER"),
            os.getenv("AZURE_SQL_DATABASE")
        ]),
        reason="Azure SQL database configuration not provided"
    )
    def test_database_operations_api_call(self, sample_config):
        """Test making an actual API call to get database operations."""
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
        
        # Create API client
        api_client = AzureSQLAPIClient(credential, db_config["subscription_id"])
        
        try:
            # Test getting database operations
            operations = api_client.get_database_operations(
                subscription_id=db_config["subscription_id"],
                resource_group=db_config["resource_group"],
                server_name=db_config["server_name"],
                database_name=db_config["database_name"]
            )
            
            # Should return a dict with 'value' key
            assert isinstance(operations, dict)
            assert "value" in operations
            print(f"Successfully retrieved database operations: {len(operations.get('value', []))} operations found")
            
        except Exception as e:
            error_msg = str(e)
            if "Forbidden" in error_msg or "403" in error_msg:
                pytest.fail(f"Insufficient permissions to access Azure SQL database: {error_msg}")
            elif "NotFound" in error_msg or "404" in error_msg:
                pytest.fail(f"Azure SQL database not found (check configuration): {error_msg}")
            else:
                pytest.fail(f"Unexpected error during API call: {error_msg}")

    def test_toolset_list_databases_tool(self, azure_sql_toolset, sample_config):
        """Test the list_azure_sql_databases tool."""
        # Setup the toolset
        success, _ = azure_sql_toolset.prerequisites_callable(sample_config)
        if not success:
            pytest.skip("Prerequisites not met")
        
        # Get the list databases tool
        list_tool = None
        for tool in azure_sql_toolset.tools:
            if tool.name == "list_azure_sql_databases":
                list_tool = tool
                break
        
        assert list_tool is not None, "list_azure_sql_databases tool not found"
        
        # Execute the tool
        result = list_tool.invoke({})
        
        # Check the result
        assert result.status.name == "SUCCESS"
        print(f"Database list result: {result.data}")
        assert "Available Azure SQL Databases" in result.data
        assert "test-db" in result.data

    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SUBSCRIPTION_ID"),
            os.getenv("AZURE_RESOURCE_GROUP"), 
            os.getenv("AZURE_SQL_SERVER"),
            os.getenv("AZURE_SQL_DATABASE")
        ]),
        reason="Azure SQL database configuration not provided"
    )
    def test_get_top_cpu_queries_tool_live(self, azure_sql_toolset, sample_config):
        """Test GetTopCPUQueries tool with live Azure SQL database connection."""
        # Setup the toolset
        success, message = azure_sql_toolset.prerequisites_callable(sample_config)
        if not success:
            pytest.skip(f"Prerequisites not met: {message}")
        
        # Get the GetTopCPUQueries tool
        cpu_tool = None
        for tool in azure_sql_toolset.tools:
            if tool.name == "get_top_cpu_queries":
                cpu_tool = tool
                break
        
        assert cpu_tool is not None, "get_top_cpu_queries tool not found"
        
        try:
            # Execute the tool with default parameters
            result = cpu_tool.invoke({
                "database_name": "test-db"
            })
            
            # Check the result
            assert result.status.name == "SUCCESS"
            print(f"Top CPU queries result: {result.data}")
            
            # Verify the report structure
            assert "Top CPU Consuming Queries Report" in result.data
            assert sample_config["azure_sql_databases"][0]["database_name"] in result.data
            assert sample_config["azure_sql_databases"][0]["server_name"] in result.data
            assert "Last 2 hours" in result.data  # Default hours_back
            assert "Top Queries: 15" in result.data  # Default top_count
            
            # Should contain either query results or "No queries found"
            assert ("No queries found for the specified time period" in result.data or 
                   "## Query Details" in result.data)
            
        except Exception as e:
            error_msg = str(e)
            if "Query Store" in error_msg:
                pytest.skip(f"Query Store not available or enabled: {error_msg}")
            elif "permission" in error_msg.lower() or "forbidden" in error_msg.lower():
                pytest.fail(f"Insufficient permissions for Query Store access: {error_msg}")
            else:
                pytest.fail(f"Unexpected error during CPU queries test: {error_msg}")

    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SUBSCRIPTION_ID"),
            os.getenv("AZURE_RESOURCE_GROUP"), 
            os.getenv("AZURE_SQL_SERVER"),
            os.getenv("AZURE_SQL_DATABASE")
        ]),
        reason="Azure SQL database configuration not provided"
    )
    def test_get_slow_queries_tool_live(self, azure_sql_toolset, sample_config):
        """Test GetSlowQueries tool with live Azure SQL database connection."""
        # Setup the toolset
        success, message = azure_sql_toolset.prerequisites_callable(sample_config)
        if not success:
            pytest.skip(f"Prerequisites not met: {message}")
        
        # Get the GetSlowQueries tool
        slow_tool = None
        for tool in azure_sql_toolset.tools:
            if tool.name == "get_slow_queries":
                slow_tool = tool
                break
        
        assert slow_tool is not None, "get_slow_queries tool not found"
        
        try:
            # Execute the tool with custom parameters
            result = slow_tool.invoke({
                "database_name": "test-db",
                "top_count": 10,
                "hours_back": 1
            })
            
            # Check the result
            assert result.status.name == "SUCCESS"
            print(f"Slow queries result: {result.data}")
            
            # Verify the report structure
            assert "Slowest/Longest-Running Queries Report" in result.data
            assert sample_config["azure_sql_databases"][0]["database_name"] in result.data
            assert sample_config["azure_sql_databases"][0]["server_name"] in result.data
            assert "Last 1 hours" in result.data  # Custom hours_back
            assert "Top Queries: 10" in result.data  # Custom top_count
            
            # Should contain either query results or "No queries found"
            assert ("No queries found for the specified time period" in result.data or 
                   "## Query Details" in result.data)
            
        except Exception as e:
            error_msg = str(e)
            if "Query Store" in error_msg:
                pytest.skip(f"Query Store not available or enabled: {error_msg}")
            elif "permission" in error_msg.lower() or "forbidden" in error_msg.lower():
                pytest.fail(f"Insufficient permissions for Query Store access: {error_msg}")
            else:
                pytest.fail(f"Unexpected error during slow queries test: {error_msg}")

    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SUBSCRIPTION_ID"),
            os.getenv("AZURE_RESOURCE_GROUP"), 
            os.getenv("AZURE_SQL_SERVER"),
            os.getenv("AZURE_SQL_DATABASE")
        ]),
        reason="Azure SQL database configuration not provided"
    )
    def test_query_performance_tools_direct_api_calls(self, sample_config):
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
            # assert False
                
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

    def test_query_performance_tools_registration(self, azure_sql_toolset):
        """Test that the new query performance tools are properly registered."""
        tool_names = [tool.name for tool in azure_sql_toolset.tools]
        
        # Verify new tools are registered
        assert "get_top_cpu_queries" in tool_names, "get_top_cpu_queries tool not registered"
        assert "get_slow_queries" in tool_names, "get_slow_queries tool not registered"
        
        # Verify existing tools are still there
        assert "list_azure_sql_databases" in tool_names, "list_azure_sql_databases tool missing"
        assert "generate_health_report" in tool_names, "generate_health_report tool missing"
        assert "generate_performance_report" in tool_names, "generate_performance_report tool missing"
        assert "generate_security_report" in tool_names, "generate_security_report tool missing"
        
        print(f"All tools registered: {tool_names}")

    def test_query_performance_tools_error_handling_live(self, azure_sql_toolset, sample_config):
        """Test error handling for query performance tools with invalid database names."""
        # Setup the toolset
        success, message = azure_sql_toolset.prerequisites_callable(sample_config)
        if not success:
            pytest.skip(f"Prerequisites not met: {message}")
        
        # Get the tools
        cpu_tool = None
        slow_tool = None
        for tool in azure_sql_toolset.tools:
            if tool.name == "get_top_cpu_queries":
                cpu_tool = tool
            elif tool.name == "get_slow_queries":
                slow_tool = tool
        
        assert cpu_tool is not None, "get_top_cpu_queries tool not found"
        assert slow_tool is not None, "get_slow_queries tool not found"
        
        # Test with invalid database name
        cpu_result = cpu_tool.invoke({"database_name": "non-existent-database"})
        assert cpu_result.status.name == "ERROR"
        assert "Database configuration not found" in cpu_result.error
        
        slow_result = slow_tool.invoke({"database_name": "non-existent-database"})
        assert slow_result.status.name == "ERROR"
        assert "Database configuration not found" in slow_result.error
        
        print("Error handling tests passed for invalid database names")


