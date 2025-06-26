import os
import pytest
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from holmes.plugins.toolsets.azure_sql.connection_monitoring_api import ConnectionMonitoringAPI


@pytest.fixture(scope="module")
def azure_sql_config():
    """Get Azure SQL configuration from environment variables."""
    required_vars = [
        "AZURE_SQL_SUBSCRIPTION_ID",
        "AZURE_SQL_RESOURCE_GROUP", 
        "AZURE_SQL_SERVER_NAME",
        "AZURE_SQL_DATABASE_NAME"
    ]
    
    config = {}
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            config[var.lower().replace("azure_sql_", "")] = value
    
    if missing_vars:
        pytest.skip(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Optional authentication variables
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID") 
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    sql_username = os.getenv("AZURE_SQL_USERNAME")
    sql_password = os.getenv("AZURE_SQL_PASSWORD")
    
    if tenant_id and client_id and client_secret:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    else:
        credential = DefaultAzureCredential()
    
    config.update({
        "credential": credential,
        "sql_username": sql_username,
        "sql_password": sql_password
    })
    
    return config


@pytest.fixture(scope="module")
def connection_monitoring_api(azure_sql_config):
    """Create ConnectionMonitoringAPI instance."""
    return ConnectionMonitoringAPI(
        credential=azure_sql_config["credential"],
        subscription_id=azure_sql_config["subscription_id"],
        sql_username=azure_sql_config["sql_username"],
        sql_password=azure_sql_config["sql_password"]
    )


class TestConnectionMonitoringAPIIntegration:
    
    def test_get_connection_metrics(self, connection_monitoring_api, azure_sql_config):
        """Test getting connection metrics from Azure Monitor."""
        result = connection_monitoring_api.get_connection_metrics(
            resource_group=azure_sql_config["resource_group"],
            server_name=azure_sql_config["server_name"],
            database_name=azure_sql_config["database_name"],
            hours_back=1
        )
        
        # Should return a dictionary, may be empty if no data in timerange
        assert isinstance(result, dict)
        # Should not contain error if successful
        if "error" in result:
            # This is acceptable for metrics API - might not have data
            assert isinstance(result["error"], str)
        else:
            # If successful, should have metric names as keys
            for key, value in result.items():
                assert isinstance(value, list)
    
    def test_get_active_connections(self, connection_monitoring_api, azure_sql_config):
        """Test getting active connections via DMV."""
        result = connection_monitoring_api.get_active_connections(
            server_name=azure_sql_config["server_name"],
            database_name=azure_sql_config["database_name"]
        )
        
        # Should return a list
        assert isinstance(result, list)
        
        # If there are connections, verify structure
        if result:
            connection = result[0]
            required_fields = [
                "session_id", "login_name", "host_name", "status", 
                "connection_status", "login_time"
            ]
            for field in required_fields:
                assert field in connection, f"Missing field: {field}"
    
    def test_get_connection_summary(self, connection_monitoring_api, azure_sql_config):
        """Test getting connection summary statistics."""
        result = connection_monitoring_api.get_connection_summary(
            server_name=azure_sql_config["server_name"],
            database_name=azure_sql_config["database_name"]
        )
        
        # Should return a dictionary
        assert isinstance(result, dict)
        
        if "error" not in result:
            # Should have summary statistics
            expected_fields = [
                "total_connections", "active_connections", "idle_connections",
                "unique_users", "unique_hosts"
            ]
            for field in expected_fields:
                assert field in result, f"Missing summary field: {field}"
                assert isinstance(result[field], (int, type(None)))
    
    def test_get_failed_connections(self, connection_monitoring_api, azure_sql_config):
        """Test getting failed connection attempts."""
        result = connection_monitoring_api.get_failed_connections(
            server_name=azure_sql_config["server_name"],
            database_name=azure_sql_config["database_name"],
            hours_back=24
        )
        
        # Should return a list (may be empty)
        assert isinstance(result, list)
        
        # If there are failed connections, verify structure
        if result:
            failed_conn = result[0]
            expected_fields = ["timestamp_utc", "record_type"]
            for field in expected_fields:
                assert field in failed_conn, f"Missing field: {field}"
    
    def test_get_connection_pool_stats(self, connection_monitoring_api, azure_sql_config):
        """Test getting connection pool statistics."""
        result = connection_monitoring_api.get_connection_pool_stats(
            server_name=azure_sql_config["server_name"],
            database_name=azure_sql_config["database_name"]
        )
        
        # Should return a dictionary
        assert isinstance(result, dict)
        
        if "error" not in result:
            # Should have pool statistics
            expected_metrics = ["Database Connections", "Active Requests", "Waiting Tasks"]
            for metric in expected_metrics:
                if metric in result:
                    assert "value" in result[metric]
                    assert "unit" in result[metric]
                    assert isinstance(result[metric]["value"], (int, type(None)))
    
    def test_api_credential_validation(self, azure_sql_config):
        """Test that API properly validates credentials."""
        # Test with valid credentials
        api = ConnectionMonitoringAPI(
            credential=azure_sql_config["credential"],
            subscription_id=azure_sql_config["subscription_id"],
            sql_username=azure_sql_config["sql_username"],
            sql_password=azure_sql_config["sql_password"]
        )
        
        assert api.sql_api_client is not None
        assert api.metrics_client is not None
        assert api.subscription_id == azure_sql_config["subscription_id"]
    
    def test_handles_invalid_database(self, connection_monitoring_api, azure_sql_config):
        """Test API handles invalid database gracefully."""
        result = connection_monitoring_api.get_connection_summary(
            server_name=azure_sql_config["server_name"],
            database_name="nonexistent_database"
        )
        
        # Should return error information
        assert isinstance(result, dict)
        assert "error" in result
        assert isinstance(result["error"], str)