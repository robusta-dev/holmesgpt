import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from azure.identity import DefaultAzureCredential
from holmes.plugins.toolsets.azure_sql.connection_monitoring_api import ConnectionMonitoringAPI
from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import GenerateConnectionReport, AzureSQLToolset, AzureSQLDatabaseConfig


@pytest.fixture
def mock_credential():
    """Mock Azure credential."""
    return Mock(spec=DefaultAzureCredential)


@pytest.fixture
def mock_azure_sql_api():
    """Mock AzureSQLAPIClient."""
    mock_api = Mock()
    mock_api.credential = Mock()
    mock_api.sql_username = "test_user"
    mock_api.sql_password = "test_pass"
    return mock_api


@pytest.fixture
def connection_monitoring_api(mock_credential):
    """Create ConnectionMonitoringAPI instance with mocked dependencies."""
    with patch('holmes.plugins.toolsets.azure_sql.connection_monitoring_api.AzureSQLAPIClient'), \
         patch('holmes.plugins.toolsets.azure_sql.connection_monitoring_api.MetricsQueryClient'):
        api = ConnectionMonitoringAPI(
            credential=mock_credential,
            subscription_id="test-subscription",
            sql_username="test_user",
            sql_password="test_pass"
        )
        return api


@pytest.fixture
def mock_db_config():
    """Mock database configuration."""
    return AzureSQLDatabaseConfig(
        name="test-db",
        subscription_id="test-subscription",
        resource_group="test-rg",
        server_name="test-server",
        database_name="test-database"
    )


@pytest.fixture
def mock_toolset(mock_db_config):
    """Mock AzureSQLToolset."""
    toolset = Mock(spec=AzureSQLToolset)
    toolset.api_clients = {"test-subscription": Mock()}
    toolset.database_configs = {"test-db": mock_db_config}
    return toolset


class TestConnectionMonitoringAPI:
    
    def test_init(self, mock_credential):
        """Test ConnectionMonitoringAPI initialization."""
        with patch('holmes.plugins.toolsets.azure_sql.connection_monitoring_api.AzureSQLAPIClient') as mock_sql_api, \
             patch('holmes.plugins.toolsets.azure_sql.connection_monitoring_api.MetricsQueryClient') as mock_metrics:
            
            api = ConnectionMonitoringAPI(
                credential=mock_credential,
                subscription_id="test-subscription",
                sql_username="test_user",
                sql_password="test_pass"
            )
            
            assert api.subscription_id == "test-subscription"
            mock_sql_api.assert_called_once_with(mock_credential, "test-subscription", "test_user", "test_pass")
            mock_metrics.assert_called_once_with(mock_credential)

    def test_get_connection_metrics_success(self, connection_monitoring_api):
        """Test successful connection metrics retrieval."""
        # Mock the metrics query response
        mock_metric = Mock()
        mock_metric.name = "connection_successful"
        mock_timeseries = Mock()
        mock_data_point = Mock()
        mock_data_point.time_stamp.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_data_point.maximum = 10
        mock_data_point.average = 5
        mock_data_point.total = 50
        mock_timeseries.data = [mock_data_point]
        mock_metric.timeseries = [mock_timeseries]
        
        mock_response = Mock()
        mock_response.metrics = [mock_metric]
        connection_monitoring_api.metrics_client.query.return_value = mock_response
        
        result = connection_monitoring_api.get_connection_metrics(
            "test-rg", "test-server", "test-db", 2
        )
        
        assert "connection_successful" in result
        assert len(result["connection_successful"]) == 1
        assert result["connection_successful"][0]["maximum"] == 10
        assert result["connection_successful"][0]["average"] == 5
        assert result["connection_successful"][0]["total"] == 50

    def test_get_connection_metrics_error(self, connection_monitoring_api):
        """Test connection metrics retrieval with error."""
        connection_monitoring_api.metrics_client.query.side_effect = Exception("API Error")
        
        result = connection_monitoring_api.get_connection_metrics(
            "test-rg", "test-server", "test-db", 2
        )
        
        assert "error" in result
        assert "API Error" in result["error"]

    def test_get_active_connections_success(self, connection_monitoring_api):
        """Test successful active connections retrieval."""
        mock_connections = [
            {
                "session_id": 1,
                "login_name": "user1",
                "host_name": "host1",
                "status": "running",
                "connection_status": "Active"
            }
        ]
        connection_monitoring_api.sql_api_client._execute_query.return_value = mock_connections
        
        result = connection_monitoring_api.get_active_connections("test-server", "test-db")
        
        assert len(result) == 1
        assert result[0]["session_id"] == 1
        assert result[0]["login_name"] == "user1"

    def test_get_active_connections_error(self, connection_monitoring_api):
        """Test active connections retrieval with error."""
        connection_monitoring_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = connection_monitoring_api.get_active_connections("test-server", "test-db")
        
        assert result == []

    def test_get_connection_summary_success(self, connection_monitoring_api):
        """Test successful connection summary retrieval."""
        mock_summary = [
            {
                "total_connections": 10,
                "active_connections": 5,
                "idle_connections": 5,
                "blocked_connections": 0,
                "unique_users": 3,
                "unique_hosts": 2
            }
        ]
        connection_monitoring_api.sql_api_client._execute_query.return_value = mock_summary
        
        result = connection_monitoring_api.get_connection_summary("test-server", "test-db")
        
        assert result["total_connections"] == 10
        assert result["active_connections"] == 5
        assert result["blocked_connections"] == 0

    def test_get_connection_summary_error(self, connection_monitoring_api):
        """Test connection summary retrieval with error."""
        connection_monitoring_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = connection_monitoring_api.get_connection_summary("test-server", "test-db")
        
        assert "error" in result
        assert "SQL Error" in result["error"]

    def test_get_failed_connections(self, connection_monitoring_api):
        """Test failed connections retrieval."""
        mock_failed = [
            {
                "timestamp_utc": "2023-01-01T00:00:00Z",
                "record_type": "Error",
                "sni_consumer_error": 123
            }
        ]
        connection_monitoring_api.sql_api_client._execute_query.return_value = mock_failed
        
        result = connection_monitoring_api.get_failed_connections("test-server", "test-db")
        
        assert len(result) == 1
        assert result[0]["record_type"] == "Error"

    def test_get_connection_pool_stats_success(self, connection_monitoring_api):
        """Test successful connection pool stats retrieval."""
        mock_stats = [
            {"metric_name": "Database Connections", "current_value": 10, "unit": "connections"},
            {"metric_name": "Active Requests", "current_value": 5, "unit": "requests"}
        ]
        connection_monitoring_api.sql_api_client._execute_query.return_value = mock_stats
        
        result = connection_monitoring_api.get_connection_pool_stats("test-server", "test-db")
        
        assert "Database Connections" in result
        assert result["Database Connections"]["value"] == 10
        assert result["Database Connections"]["unit"] == "connections"


class TestGenerateConnectionReport:
    
    def test_tool_initialization(self, mock_toolset):
        """Test GenerateConnectionReport tool initialization."""
        tool = GenerateConnectionReport(mock_toolset)
        
        assert tool.name == "generate_connection_report"
        assert "connection monitoring report" in tool.description
        assert "database_name" in tool.parameters
        assert "hours_back" in tool.parameters

    def test_build_connection_report(self, mock_toolset, mock_db_config):
        """Test connection report building."""
        tool = GenerateConnectionReport(mock_toolset)
        
        connection_data = {
            "summary": {
                "total_connections": 10,
                "active_connections": 5,
                "idle_connections": 5,
                "blocked_connections": 1,
                "unique_users": 3,
                "unique_hosts": 2
            },
            "pool_stats": {
                "Database Connections": {"value": 10, "unit": "connections"},
                "Active Requests": {"value": 5, "unit": "requests"}
            },
            "active_connections": [
                {
                    "session_id": 1,
                    "login_name": "user1",
                    "host_name": "host1",
                    "status": "running",
                    "connection_status": "Active",
                    "cpu_time": 1000,
                    "wait_type": "PAGEIOLATCH_SH",
                    "blocking_session_id": 0
                }
            ],
            "metrics": {
                "connection_successful": [
                    {"average": 5, "maximum": 10, "total": 50}
                ]
            }
        }
        
        report = tool._build_connection_report(mock_db_config, connection_data, 2)
        
        assert "Azure SQL Database Connection Report" in report
        assert "test-database" in report
        assert "test-server" in report
        assert "**Total Connections**: 10" in report
        assert "**Active Connections**: 5" in report
        assert "**🚨 Blocked Connections**: 1" in report
        assert "**Database Connections**: 10 connections" in report
        assert "user1@host1" in report
        assert "PAGEIOLATCH_SH" in report

    def test_build_connection_report_with_errors(self, mock_toolset, mock_db_config):
        """Test connection report building with errors."""
        tool = GenerateConnectionReport(mock_toolset)
        
        connection_data = {
            "summary": {"error": "SQL connection failed"},
            "pool_stats": {"error": "Permission denied"},
            "active_connections": [],
            "metrics": {"error": "Metrics unavailable"}
        }
        
        report = tool._build_connection_report(mock_db_config, connection_data, 2)
        
        assert "⚠️ **Error retrieving connection summary:** SQL connection failed" in report
        assert "⚠️ **Error retrieving pool stats:** Permission denied" in report
        assert "⚠️ **Metrics unavailable:** Metrics unavailable" in report
        assert "No active connections found" in report

    @patch('holmes.plugins.toolsets.azure_sql.azure_sql_toolset.ConnectionMonitoringAPI')
    @patch('holmes.plugins.toolsets.azure_sql.azure_sql_toolset.GenerateConnectionReport.get_database_config')
    def test_invoke_success(self, mock_get_db_config, mock_connection_api_class, mock_toolset, mock_db_config):
        """Test successful tool invocation."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_connection_api_class.return_value = mock_api_instance
        mock_get_db_config.return_value = mock_db_config
        
        mock_api_instance.get_connection_summary.return_value = {"total_connections": 5}
        mock_api_instance.get_active_connections.return_value = []
        mock_api_instance.get_connection_pool_stats.return_value = {}
        mock_api_instance.get_connection_metrics.return_value = {}
        
        tool = GenerateConnectionReport(mock_toolset)
        
        params = {"database_name": "test-db", "hours_back": 2}
        result = tool._invoke(params)
        
        assert result.status.value == "success"
        assert "Azure SQL Database Connection Report" in result.data
        assert "**Total Connections**: 5" in result.data

    @patch('holmes.plugins.toolsets.azure_sql.azure_sql_toolset.GenerateConnectionReport.get_database_config')
    def test_invoke_error(self, mock_get_db_config, mock_toolset):
        """Test tool invocation with error."""
        mock_get_db_config.side_effect = Exception("Database not found")
        
        tool = GenerateConnectionReport(mock_toolset)
        params = {"database_name": "nonexistent-db"}
        result = tool._invoke(params)
        
        assert result.status.value == "error"
        assert "Failed to generate connection report" in result.error
        assert "Database not found" in result.error

    def test_get_parameterized_one_liner(self, mock_toolset):
        """Test parameterized one-liner generation."""
        tool = GenerateConnectionReport(mock_toolset)
        params = {"database_name": "test-db"}
        
        one_liner = tool.get_parameterized_one_liner(params)
        
        assert "Generated connection monitoring report for database test-db" in one_liner


# Integration test that requires environment variables
class TestConnectionMonitoringIntegration:
    
    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SQL_SUBSCRIPTION_ID"),
            os.getenv("AZURE_SQL_SERVER"),
            os.getenv("AZURE_SQL_DATABASE")
        ]),
        reason="Azure SQL environment variables not set"
    )
    def test_connection_monitoring_integration(self):
        """Integration test for connection monitoring (requires env vars)."""
        from azure.identity import DefaultAzureCredential
        
        # Get config from environment
        subscription_id = os.getenv("AZURE_SQL_SUBSCRIPTION_ID")
        server_name = os.getenv("AZURE_SQL_SERVER")
        database_name = os.getenv("AZURE_SQL_DATABASE")
        sql_username = os.getenv("AZURE_SQL_USERNAME")
        sql_password = os.getenv("AZURE_SQL_PASSWORD")
        
        # Create API client
        credential = DefaultAzureCredential()
        api = ConnectionMonitoringAPI(
            credential=credential,
            subscription_id=subscription_id,
            sql_username=sql_username,
            sql_password=sql_password
        )

        
        # Test connection summary (should work even if empty)
        summary = api.get_connection_summary(server_name, database_name)
        assert isinstance(summary, dict)
        print(summary)
        
        # Test active connections (should work even if empty)
        connections = api.get_active_connections(server_name, database_name)
        assert isinstance(connections, list)
        print(connections)
        
        # Test pool stats (should work even if empty)
        pool_stats = api.get_connection_pool_stats(server_name, database_name)
        print(pool_stats)
        assert isinstance(pool_stats, dict)
        assert False