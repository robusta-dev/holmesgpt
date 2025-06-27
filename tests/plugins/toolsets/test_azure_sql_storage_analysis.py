import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from azure.identity import DefaultAzureCredential
from holmes.plugins.toolsets.azure_sql.storage_analysis_api import StorageAnalysisAPI


@pytest.fixture
def mock_credential():
    """Mock Azure credential."""
    return Mock(spec=DefaultAzureCredential)


@pytest.fixture
def storage_analysis_api(mock_credential):
    """Create StorageAnalysisAPI instance with mocked dependencies."""
    with patch('holmes.plugins.toolsets.azure_sql.storage_analysis_api.AzureSQLAPIClient'), \
         patch('holmes.plugins.toolsets.azure_sql.storage_analysis_api.MetricsQueryClient'):
        api = StorageAnalysisAPI(
            credential=mock_credential,
            subscription_id="test-subscription",
            sql_username="test_user",
            sql_password="test_pass"
        )
        return api


class TestStorageAnalysisAPI:
    
    def test_init(self, mock_credential):
        """Test StorageAnalysisAPI initialization."""
        with patch('holmes.plugins.toolsets.azure_sql.storage_analysis_api.AzureSQLAPIClient') as mock_sql_api, \
             patch('holmes.plugins.toolsets.azure_sql.storage_analysis_api.MetricsQueryClient') as mock_metrics:
            
            api = StorageAnalysisAPI(
                credential=mock_credential,
                subscription_id="test-subscription",
                sql_username="test_user",
                sql_password="test_pass"
            )
            
            assert api.subscription_id == "test-subscription"
            mock_sql_api.assert_called_once_with(mock_credential, "test-subscription", "test_user", "test_pass")
            mock_metrics.assert_called_once_with(mock_credential)

    def test_get_storage_metrics_success(self, storage_analysis_api):
        """Test successful storage metrics retrieval."""
        # Mock the metrics query response
        mock_metric = Mock()
        mock_metric.name = "storage_percent"
        mock_timeseries = Mock()
        mock_data_point = Mock()
        mock_data_point.time_stamp.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_data_point.maximum = 85.5
        mock_data_point.average = 75.0
        mock_data_point.minimum = 65.2
        mock_timeseries.data = [mock_data_point]
        mock_metric.timeseries = [mock_timeseries]
        
        mock_response = Mock()
        mock_response.metrics = [mock_metric]
        storage_analysis_api.metrics_client.query.return_value = mock_response
        
        result = storage_analysis_api.get_storage_metrics(
            "test-rg", "test-server", "test-db", 24
        )
        
        assert "storage_percent" in result
        assert len(result["storage_percent"]) == 1
        assert result["storage_percent"][0]["maximum"] == 85.5
        assert result["storage_percent"][0]["average"] == 75.0
        assert result["storage_percent"][0]["minimum"] == 65.2

    def test_get_storage_metrics_error(self, storage_analysis_api):
        """Test storage metrics retrieval with error."""
        storage_analysis_api.metrics_client.query.side_effect = Exception("API Error")
        
        result = storage_analysis_api.get_storage_metrics(
            "test-rg", "test-server", "test-db", 24
        )
        
        assert "error" in result
        assert "API Error" in result["error"]

    def test_get_database_size_details_success(self, storage_analysis_api):
        """Test successful database size details retrieval."""
        mock_files = [
            {
                "database_name": "test_db",
                "file_type": "Data",
                "logical_name": "test_db_data",
                "size_mb": 1024.0,
                "used_mb": 800.0,
                "free_mb": 224.0,
                "used_percent": 78.13,
                "max_size": "Default (2TB)",
                "growth_setting": "10%",
                "file_state": "ONLINE"
            },
            {
                "database_name": "test_db",
                "file_type": "Log",
                "logical_name": "test_db_log",
                "size_mb": 256.0,
                "used_mb": 100.0,
                "free_mb": 156.0,
                "used_percent": 39.06,
                "max_size": "Unlimited",
                "growth_setting": "64 MB",
                "file_state": "ONLINE"
            }
        ]
        storage_analysis_api.sql_api_client._execute_query.return_value = mock_files
        
        result = storage_analysis_api.get_database_size_details("test-server", "test-db")
        
        assert len(result) == 2
        assert result[0]["file_type"] == "Data"
        assert result[0]["size_mb"] == 1024.0
        assert result[1]["file_type"] == "Log"
        assert result[1]["size_mb"] == 256.0

    def test_get_database_size_details_error(self, storage_analysis_api):
        """Test database size details retrieval with error."""
        storage_analysis_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = storage_analysis_api.get_database_size_details("test-server", "test-db")
        
        assert "error" in result
        assert "SQL Error" in result["error"]

    def test_get_storage_summary_success(self, storage_analysis_api):
        """Test successful storage summary retrieval."""
        mock_summary = [
            {
                "database_name": "test_db",
                "total_data_size_mb": 1024.0,
                "used_data_size_mb": 800.0,
                "total_log_size_mb": 256.0,
                "used_log_size_mb": 100.0,
                "total_database_size_mb": 1280.0,
                "total_used_size_mb": 900.0,
                "data_files_count": 1,
                "log_files_count": 1
            }
        ]
        storage_analysis_api.sql_api_client._execute_query.return_value = mock_summary
        
        result = storage_analysis_api.get_storage_summary("test-server", "test-db")
        
        assert result["total_database_size_mb"] == 1280.0
        assert result["total_used_size_mb"] == 900.0
        assert result["data_files_count"] == 1
        assert result["log_files_count"] == 1

    def test_get_storage_summary_error(self, storage_analysis_api):
        """Test storage summary retrieval with error."""
        storage_analysis_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = storage_analysis_api.get_storage_summary("test-server", "test-db")
        
        assert "error" in result
        assert "SQL Error" in result["error"]

    def test_get_table_space_usage_success(self, storage_analysis_api):
        """Test successful table space usage retrieval."""
        mock_tables = [
            {
                "schema_name": "dbo",
                "table_name": "users",
                "index_name": "PK_users",
                "index_type": "CLUSTERED",
                "row_count": 100000,
                "total_space_mb": 50.5,
                "used_space_mb": 45.2,
                "data_space_mb": 40.1,
                "unused_space_mb": 5.3,
                "index_space_mb": 5.1
            }
        ]
        storage_analysis_api.sql_api_client._execute_query.return_value = mock_tables
        
        result = storage_analysis_api.get_table_space_usage("test-server", "test-db", 20)
        
        assert len(result) == 1
        assert result[0]["table_name"] == "users"
        assert result[0]["total_space_mb"] == 50.5
        assert result[0]["row_count"] == 100000

    def test_get_table_space_usage_error(self, storage_analysis_api):
        """Test table space usage retrieval with error."""
        storage_analysis_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = storage_analysis_api.get_table_space_usage("test-server", "test-db")
        
        assert result == []

    def test_get_storage_growth_trend_success(self, storage_analysis_api):
        """Test successful storage growth trend retrieval."""
        mock_backups = [
            {
                "backup_date": datetime(2023, 1, 5).date(),
                "database_name": "test_db",
                "backup_size_mb": 1000.0,
                "compressed_backup_size_mb": 800.0,
                "compression_ratio_percent": 20.0
            },
            {
                "backup_date": datetime(2023, 1, 1).date(),
                "database_name": "test_db", 
                "backup_size_mb": 900.0,
                "compressed_backup_size_mb": 720.0,
                "compression_ratio_percent": 20.0
            }
        ]
        storage_analysis_api.sql_api_client._execute_query.return_value = mock_backups
        
        result = storage_analysis_api.get_storage_growth_trend("test-server", "test-db")
        
        assert "backup_history" in result
        assert "growth_analysis" in result
        assert len(result["backup_history"]) == 2
        assert result["growth_analysis"]["total_growth_mb"] == 100.0
        assert result["growth_analysis"]["days_analyzed"] == 4

    def test_get_storage_growth_trend_insufficient_data(self, storage_analysis_api):
        """Test storage growth trend with insufficient data."""
        mock_backups = [
            {
                "backup_date": datetime(2023, 1, 1).date(),
                "database_name": "test_db",
                "backup_size_mb": 900.0,
                "compressed_backup_size_mb": 720.0,
                "compression_ratio_percent": 20.0
            }
        ]
        storage_analysis_api.sql_api_client._execute_query.return_value = mock_backups
        
        result = storage_analysis_api.get_storage_growth_trend("test-server", "test-db")
        
        assert "backup_history" in result
        assert result["growth_analysis"] is None

    def test_get_storage_growth_trend_error(self, storage_analysis_api):
        """Test storage growth trend retrieval with error."""
        storage_analysis_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = storage_analysis_api.get_storage_growth_trend("test-server", "test-db")
        
        assert "error" in result
        assert "SQL Error" in result["error"]

    def test_get_tempdb_usage_success(self, storage_analysis_api):
        """Test successful tempdb usage retrieval."""
        mock_tempdb = [
            {
                "metric_type": "TempDB Usage",
                "total_size_mb": 512.0,
                "used_size_mb": 256.0,
                "free_size_mb": 256.0,
                "used_percent": 50.0
            },
            {
                "metric_type": "TempDB Log",
                "total_size_mb": 128.0,
                "used_size_mb": 32.0,
                "free_size_mb": 96.0,
                "used_percent": 25.0
            }
        ]
        storage_analysis_api.sql_api_client._execute_query.return_value = mock_tempdb
        
        result = storage_analysis_api.get_tempdb_usage("test-server", "test-db")
        
        assert "TempDB Usage" in result
        assert "TempDB Log" in result
        assert result["TempDB Usage"]["total_size_mb"] == 512.0
        assert result["TempDB Usage"]["used_percent"] == 50.0
        assert result["TempDB Log"]["used_percent"] == 25.0

    def test_get_tempdb_usage_error(self, storage_analysis_api):
        """Test tempdb usage retrieval with error."""
        storage_analysis_api.sql_api_client._execute_query.side_effect = Exception("Permission denied")
        
        result = storage_analysis_api.get_tempdb_usage("test-server", "test-db")
        
        assert "error" in result
        assert "Permission denied" in result["error"]


# Integration test that requires environment variables
class TestStorageAnalysisIntegration:
    
    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SQL_SUBSCRIPTION_ID"),
            os.getenv("AZURE_SQL_RESOURCE_GROUP"),
            os.getenv("AZURE_SQL_SERVER_NAME"),
            os.getenv("AZURE_SQL_DATABASE_NAME")
        ]),
        reason="Azure SQL environment variables not set"
    )
    def test_storage_analysis_integration(self):
        """Integration test for storage analysis (requires env vars)."""
        from azure.identity import DefaultAzureCredential
        
        # Get config from environment
        subscription_id = os.getenv("AZURE_SQL_SUBSCRIPTION_ID")
        resource_group = os.getenv("AZURE_SQL_RESOURCE_GROUP")
        server_name = os.getenv("AZURE_SQL_SERVER_NAME")
        database_name = os.getenv("AZURE_SQL_DATABASE_NAME")
        sql_username = os.getenv("AZURE_SQL_USERNAME")
        sql_password = os.getenv("AZURE_SQL_PASSWORD")
        
        # Create API client
        credential = DefaultAzureCredential()
        api = StorageAnalysisAPI(
            credential=credential,
            subscription_id=subscription_id,
            sql_username=sql_username,
            sql_password=sql_password
        )
        
        # Test storage summary (should work even if empty)
        summary = api.get_storage_summary(server_name, database_name)
        assert isinstance(summary, dict)
        
        # Test database size details (should work even if empty)
        size_details = api.get_database_size_details(server_name, database_name)
        assert isinstance(size_details, (list, dict))
        
        # Test table space usage (should work even if empty)
        table_usage = api.get_table_space_usage(server_name, database_name)
        assert isinstance(table_usage, list)