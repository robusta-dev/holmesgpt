"""
Mocked unit tests for Azure SQL toolset query performance tools.

These tests use mocks and don't require actual Azure SQL Database connections,
making them suitable for CI/CD environments and rapid testing.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import (
    AzureSQLToolset,
    AzureSQLDatabaseConfig,
    GetTopCPUQueries,
    GetSlowQueries,
)
from holmes.plugins.toolsets.azure_sql.azure_sql_api import AzureSQLAPIClient
from azure.core.credentials import TokenCredential


class TestAzureSQLQueryPerformanceTools:
    """Mocked tests for the new query performance tools (GetTopCPUQueries, GetSlowQueries)."""
    
    @pytest.fixture
    def mock_query_results_cpu(self):
        """Mock Query Store results for CPU queries."""
        return [
            {
                'query_sql_text': 'SELECT * FROM Orders WHERE OrderDate > @param1',
                'avg_cpu_time': 1500.5,
                'execution_count': 1250,
                'total_cpu_time': 1875625.0,
                'max_cpu_time': 3000.0,
                'min_cpu_time': 800.0,
                'last_execution_time': '2023-12-01 10:30:00.000',
                'avg_duration': 2500.75,
                'total_duration': 3125937.5
            },
            {
                'query_sql_text': 'UPDATE Products SET LastModified = GETDATE() WHERE ProductID = @id',
                'avg_cpu_time': 1200.25,
                'execution_count': 980,
                'total_cpu_time': 1176245.0,
                'max_cpu_time': 2500.0,
                'min_cpu_time': 600.0,
                'last_execution_time': '2023-12-01 10:25:00.000',
                'avg_duration': 1800.5,
                'total_duration': 1764490.0
            }
        ]
    
    @pytest.fixture
    def mock_query_results_slow(self):
        """Mock Query Store results for slow queries."""
        return [
            {
                'query_sql_text': 'SELECT COUNT(*) FROM BigTable bt JOIN AnotherTable at ON bt.id = at.big_table_id',
                'avg_duration': 5500.75,
                'execution_count': 45,
                'total_duration': 247533.75,
                'max_duration': 8000.0,
                'min_duration': 3500.0,
                'last_execution_time': '2023-12-01 10:15:00.000',
                'avg_cpu_time': 4200.5,
                'total_cpu_time': 189022.5
            },
            {
                'query_sql_text': 'SELECT * FROM ComplexView WHERE filter_column LIKE @pattern',
                'avg_duration': 4800.25,
                'execution_count': 75,
                'total_duration': 360018.75,
                'max_duration': 7500.0,
                'min_duration': 2000.0,
                'last_execution_time': '2023-12-01 10:20:00.000',
                'avg_cpu_time': 3800.0,
                'total_cpu_time': 285000.0
            }
        ]
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return {
            "azure_sql_databases": [
                {
                    "name": "test-db",
                    "subscription_id": "test-subscription-id",
                    "resource_group": "test-resource-group",
                    "server_name": "test-server",
                    "database_name": "test-database",
                }
            ]
        }
    
    @pytest.fixture
    def mock_toolset(self, sample_config):
        """Create a mock toolset with mocked API client."""
        toolset = AzureSQLToolset()
        
        # Mock the API client
        mock_client = Mock(spec=AzureSQLAPIClient)
        toolset.api_clients = {"test-subscription-id": mock_client}
        
        # Mock database configs
        db_config = AzureSQLDatabaseConfig(**sample_config["azure_sql_databases"][0])
        toolset.database_configs = {"test-db": db_config}
        
        return toolset, mock_client
    
    def test_get_top_cpu_queries_tool_success(self, mock_toolset, mock_query_results_cpu):
        """Test GetTopCPUQueries tool with successful execution."""
        toolset, mock_client = mock_toolset
        mock_client.get_top_cpu_queries.return_value = mock_query_results_cpu
        
        # Create the tool
        tool = GetTopCPUQueries(toolset)
        
        # Execute the tool
        result = tool.invoke({
            "database_name": "test-db",
            "top_count": 10,
            "hours_back": 2
        })
        
        # Verify the result
        assert result.status.name == "SUCCESS"
        assert "Top CPU Consuming Queries Report" in result.data
        assert "test-database" in result.data
        assert "test-server" in result.data
        assert "Last 2 hours" in result.data
        assert "SELECT * FROM Orders" in result.data
        assert "UPDATE Products" in result.data
        assert "1,500 μs" in result.data  # Formatted CPU time
        assert "1,250" in result.data      # Execution count
        
        # Verify API client was called correctly
        mock_client.get_top_cpu_queries.assert_called_once_with(
            "test-subscription-id", "test-resource-group", 
            "test-server", "test-database", 10, 2
        )
    
    def test_get_top_cpu_queries_tool_default_params(self, mock_toolset, mock_query_results_cpu):
        """Test GetTopCPUQueries tool with default parameters."""
        toolset, mock_client = mock_toolset
        mock_client.get_top_cpu_queries.return_value = mock_query_results_cpu
        
        tool = GetTopCPUQueries(toolset)
        result = tool.invoke({"database_name": "test-db"})
        
        assert result.status.name == "SUCCESS"
        
        # Verify default parameters were used
        mock_client.get_top_cpu_queries.assert_called_once_with(
            "test-subscription-id", "test-resource-group", 
            "test-server", "test-database", 15, 2  # Default values
        )
    
    def test_get_top_cpu_queries_tool_no_results(self, mock_toolset):
        """Test GetTopCPUQueries tool with no query results."""
        toolset, mock_client = mock_toolset
        mock_client.get_top_cpu_queries.return_value = []
        
        tool = GetTopCPUQueries(toolset)
        result = tool.invoke({"database_name": "test-db"})
        
        assert result.status.name == "SUCCESS"
        assert "No queries found for the specified time period" in result.data
    
    def test_get_slow_queries_tool_success(self, mock_toolset, mock_query_results_slow):
        """Test GetSlowQueries tool with successful execution."""
        toolset, mock_client = mock_toolset
        mock_client.get_slow_queries.return_value = mock_query_results_slow
        
        tool = GetSlowQueries(toolset)
        result = tool.invoke({
            "database_name": "test-db",
            "top_count": 5,
            "hours_back": 4
        })
        
        assert result.status.name == "SUCCESS"
        assert "Slowest/Longest-Running Queries Report" in result.data
        assert "test-database" in result.data
        assert "test-server" in result.data
        assert "Last 4 hours" in result.data
        assert "BigTable bt JOIN AnotherTable" in result.data
        assert "ComplexView" in result.data
        assert "5,501 μs" in result.data  # Formatted duration
        assert "45" in result.data         # Execution count
        
        mock_client.get_slow_queries.assert_called_once_with(
            "test-subscription-id", "test-resource-group", 
            "test-server", "test-database", 5, 4
        )
    
    def test_get_slow_queries_tool_default_params(self, mock_toolset, mock_query_results_slow):
        """Test GetSlowQueries tool with default parameters."""
        toolset, mock_client = mock_toolset
        mock_client.get_slow_queries.return_value = mock_query_results_slow
        
        tool = GetSlowQueries(toolset)
        result = tool.invoke({"database_name": "test-db"})
        
        assert result.status.name == "SUCCESS"
        
        mock_client.get_slow_queries.assert_called_once_with(
            "test-subscription-id", "test-resource-group", 
            "test-server", "test-database", 15, 2  # Default values
        )
    
    def test_get_slow_queries_tool_no_results(self, mock_toolset):
        """Test GetSlowQueries tool with no query results."""
        toolset, mock_client = mock_toolset
        mock_client.get_slow_queries.return_value = []
        
        tool = GetSlowQueries(toolset)
        result = tool.invoke({"database_name": "test-db"})
        
        assert result.status.name == "SUCCESS"
        assert "No queries found for the specified time period" in result.data
    
    def test_query_text_truncation(self, mock_toolset):
        """Test that long query text is properly truncated."""
        toolset, mock_client = mock_toolset
        
        long_query_text = "SELECT " + "very_long_column_name, " * 50 + "FROM very_long_table_name"
        mock_results = [{
            'query_sql_text': long_query_text,
            'avg_cpu_time': 1000.0,
            'execution_count': 1,
            'total_cpu_time': 1000.0,
            'max_cpu_time': 1000.0,
            'min_cpu_time': 1000.0,
            'last_execution_time': '2023-12-01 10:30:00.000',
            'avg_duration': 1000.0,
            'total_duration': 1000.0
        }]
        
        mock_client.get_top_cpu_queries.return_value = mock_results
        
        tool = GetTopCPUQueries(toolset)
        result = tool.invoke({"database_name": "test-db"})
        
        assert result.status.name == "SUCCESS"
        # Should contain truncated query with ellipsis
        assert "..." in result.data
        # Full query should not appear
        assert long_query_text not in result.data
    
    def test_database_not_found_error(self, mock_toolset):
        """Test error handling when database configuration is not found."""
        toolset, mock_client = mock_toolset
        
        tool = GetTopCPUQueries(toolset)
        result = tool.invoke({"database_name": "non-existent-db"})
        
        assert result.status.name == "ERROR"
        assert "Database configuration not found" in result.error
    
    def test_api_client_error_handling(self, mock_toolset):
        """Test error handling when API client throws an exception."""
        toolset, mock_client = mock_toolset
        mock_client.get_top_cpu_queries.side_effect = Exception("Database connection failed")
        
        tool = GetTopCPUQueries(toolset)
        result = tool.invoke({"database_name": "test-db"})
        
        assert result.status.name == "ERROR"
        assert "Failed to get top CPU queries" in result.error
        assert "Database connection failed" in result.error
    
    def test_tools_registered_in_toolset(self):
        """Test that the new tools are properly registered in the toolset."""
        toolset = AzureSQLToolset()
        
        tool_names = [tool.name for tool in toolset.tools]
        
        assert "get_top_cpu_queries" in tool_names
        assert "get_slow_queries" in tool_names
        assert "list_azure_sql_databases" in tool_names  # Existing tool
        assert "generate_health_report" in tool_names     # Existing tool
    
    def test_parameterized_one_liner(self, mock_toolset):
        """Test the parameterized one-liner descriptions."""
        toolset, mock_client = mock_toolset
        
        cpu_tool = GetTopCPUQueries(toolset)
        slow_tool = GetSlowQueries(toolset)
        
        params = {"database_name": "test-db"}
        
        cpu_liner = cpu_tool.get_parameterized_one_liner(params)
        slow_liner = slow_tool.get_parameterized_one_liner(params)
        
        assert "Retrieved top CPU consuming queries for database test-db" == cpu_liner
        assert "Retrieved slowest queries for database test-db" == slow_liner


class TestAzureSQLAPIClientQueryMethods:
    """Mocked tests for the new query execution methods in AzureSQLAPIClient."""
    
    @pytest.fixture
    def mock_credential(self):
        """Mock Azure credential."""
        mock_cred = Mock(spec=TokenCredential)
        mock_cred.get_token.return_value = Mock(token="mock-access-token-12345")
        return mock_cred
    
    @pytest.fixture  
    def api_client(self, mock_credential):
        """Create API client with mocked credential."""
        return AzureSQLAPIClient(mock_credential, "test-subscription")
    
    @patch('holmes.plugins.toolsets.azure_sql.azure_sql_api.pyodbc')
    def test_execute_query_success(self, mock_pyodbc, api_client):
        """Test successful query execution."""
        # Mock pyodbc connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_pyodbc.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query results
        mock_cursor.description = [('query_sql_text',), ('avg_cpu_time',), ('execution_count',)]
        mock_cursor.fetchall.return_value = [
            ('SELECT * FROM Orders', 1500.5, 1250),
            ('UPDATE Products SET LastModified = GETDATE()', 1200.25, 980)
        ]
        
        # Execute query
        results = api_client._execute_query("test-server", "test-db", "SELECT TOP 10 * FROM sys.query_store_query")
        
        # Verify results
        assert len(results) == 2
        assert results[0]['query_sql_text'] == 'SELECT * FROM Orders'
        assert results[0]['avg_cpu_time'] == 1500.5
        assert results[0]['execution_count'] == 1250
        
        # Verify connection was made with correct parameters
        mock_pyodbc.connect.assert_called_once()
        call_args = mock_pyodbc.connect.call_args
        connection_string = call_args[0][0]
        assert "test-server.database.windows.net" in connection_string
        assert "test-db" in connection_string
        assert "Encrypt=yes" in connection_string
        
        # Verify access token was used
        attrs_before = call_args[1]['attrs_before']
        assert 1256 in attrs_before  # SQL_COPT_SS_ACCESS_TOKEN
        assert attrs_before[1256] == "mock-access-token-12345"
    
    @patch('holmes.plugins.toolsets.azure_sql.azure_sql_api.pyodbc')
    def test_get_top_cpu_queries_method(self, mock_pyodbc, api_client):
        """Test get_top_cpu_queries method."""
        # Mock pyodbc
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_pyodbc.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.description = [('query_sql_text',), ('avg_cpu_time',)]
        mock_cursor.fetchall.return_value = [('SELECT * FROM Orders', 1500.5)]
        
        # Call method
        results = api_client.get_top_cpu_queries(
            "sub-id", "rg", "server", "db", top_count=5, hours_back=1
        )
        
        # Verify query was executed with correct parameters
        mock_cursor.execute.assert_called_once()
        executed_query = mock_cursor.execute.call_args[0][0]
        assert "TOP 5" in executed_query
        assert "DATEADD(hour, -1, GETDATE())" in executed_query
        assert "ORDER BY rs.avg_cpu_time DESC" in executed_query
        
        assert len(results) == 1
        assert results[0]['query_sql_text'] == 'SELECT * FROM Orders'
    
    @patch('holmes.plugins.toolsets.azure_sql.azure_sql_api.pyodbc')
    def test_get_slow_queries_method(self, mock_pyodbc, api_client):
        """Test get_slow_queries method."""
        # Mock pyodbc
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_pyodbc.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.description = [('query_sql_text',), ('avg_duration',)]
        mock_cursor.fetchall.return_value = [('SELECT COUNT(*) FROM BigTable', 5500.75)]
        
        # Call method
        results = api_client.get_slow_queries(
            "sub-id", "rg", "server", "db", top_count=3, hours_back=6
        )
        
        # Verify query was executed with correct parameters
        mock_cursor.execute.assert_called_once()
        executed_query = mock_cursor.execute.call_args[0][0]
        assert "TOP 3" in executed_query
        assert "DATEADD(hour, -6, GETDATE())" in executed_query
        assert "ORDER BY rs.avg_duration DESC" in executed_query
        
        assert len(results) == 1
        assert results[0]['avg_duration'] == 5500.75
    
    @patch('holmes.plugins.toolsets.azure_sql.azure_sql_api.pyodbc')
    def test_query_execution_error_handling(self, mock_pyodbc, api_client):
        """Test error handling during query execution."""
        # Mock pyodbc to raise an exception
        mock_pyodbc.connect.side_effect = Exception("Connection failed")
        
        # Verify exception is raised
        with pytest.raises(Exception) as exc_info:
            api_client._execute_query("server", "db", "SELECT 1")
        
        assert "Connection failed" in str(exc_info.value)
    
    def test_get_access_token(self, api_client, mock_credential):
        """Test access token retrieval."""
        token = api_client._get_access_token()
        
        # Verify credential was called with correct scope
        mock_credential.get_token.assert_called_once_with("https://database.windows.net/")
        assert token == "mock-access-token-12345"


if __name__ == "__main__":
    # Allow running this test file directly for manual testing
    pytest.main([__file__, "-v"])