import os
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from azure.identity import DefaultAzureCredential
from holmes.plugins.toolsets.azure_sql.blocking_queries_api import BlockingQueriesAPI


@pytest.fixture
def mock_credential():
    """Mock Azure credential."""
    return Mock(spec=DefaultAzureCredential)


@pytest.fixture
def blocking_queries_api(mock_credential):
    """Create BlockingQueriesAPI instance with mocked dependencies."""
    with patch('holmes.plugins.toolsets.azure_sql.blocking_queries_api.AzureSQLAPIClient'):
        api = BlockingQueriesAPI(
            credential=mock_credential,
            subscription_id="test-subscription",
            sql_username="test_user",
            sql_password="test_pass"
        )
        return api


class TestBlockingQueriesAPI:
    
    def test_init(self, mock_credential):
        """Test BlockingQueriesAPI initialization."""
        with patch('holmes.plugins.toolsets.azure_sql.blocking_queries_api.AzureSQLAPIClient') as mock_sql_api:
            api = BlockingQueriesAPI(
                credential=mock_credential,
                subscription_id="test-subscription",
                sql_username="test_user",
                sql_password="test_pass"
            )
            
            assert api.subscription_id == "test-subscription"
            mock_sql_api.assert_called_once_with(mock_credential, "test-subscription", "test_user", "test_pass")

    def test_get_current_blocking_queries_success(self, blocking_queries_api):
        """Test successful current blocking queries retrieval."""
        mock_blocking_data = [
            {
                "session_id": 55,
                "blocking_session_id": 0,
                "login_name": "user1",
                "host_name": "host1",
                "program_name": "SSMS",
                "start_time": datetime(2023, 1, 1, 10, 0, 0),
                "status": "running",
                "command": "SELECT",
                "total_elapsed_time": 30000,
                "wait_type": None,
                "wait_time": 0,
                "wait_resource": None,
                "sql_text": "SELECT * FROM users WHERE id = 1",
                "blocking_level": 0,
                "blocking_chain": "55",
                "session_type": "Head Blocker"
            },
            {
                "session_id": 60,
                "blocking_session_id": 55,
                "login_name": "user2",
                "host_name": "host2",
                "program_name": "AppServer",
                "start_time": datetime(2023, 1, 1, 10, 1, 0),
                "status": "suspended",
                "command": "SELECT",
                "total_elapsed_time": 25000,
                "wait_type": "LCK_M_S",
                "wait_time": 25000,
                "wait_resource": "KEY: 5:123456789:1",
                "sql_text": "SELECT * FROM users WHERE id = 1",
                "blocking_level": 1,
                "blocking_chain": "55->60",
                "session_type": "Blocked Session"
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_blocking_data
        
        result = blocking_queries_api.get_current_blocking_queries("test-server", "test-db")
        
        assert len(result) == 2
        assert result[0]["session_type"] == "Head Blocker"
        assert result[1]["session_type"] == "Blocked Session"
        assert result[1]["blocking_session_id"] == 55
        assert result[1]["wait_type"] == "LCK_M_S"

    def test_get_current_blocking_queries_error(self, blocking_queries_api):
        """Test current blocking queries retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = blocking_queries_api.get_current_blocking_queries("test-server", "test-db")
        
        assert result == []

    def test_get_deadlock_information_success(self, blocking_queries_api):
        """Test successful deadlock information retrieval."""
        mock_deadlocks = [
            {
                "deadlock_time": datetime(2023, 1, 1, 10, 0, 0),
                "victim_id": "process123",
                "process1_hostname": "host1",
                "process1_login": "user1",
                "process1_query": "UPDATE users SET name = 'John' WHERE id = 1",
                "process2_hostname": "host2",
                "process2_login": "user2",
                "process2_query": "UPDATE orders SET status = 'complete' WHERE user_id = 1",
                "locked_object": "users.PK_users"
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_deadlocks
        
        result = blocking_queries_api.get_deadlock_information("test-server", "test-db", 24)
        
        assert len(result) == 1
        assert result[0]["victim_id"] == "process123"
        assert "UPDATE users" in result[0]["process1_query"]
        assert result[0]["locked_object"] == "users.PK_users"

    def test_get_deadlock_information_error(self, blocking_queries_api):
        """Test deadlock information retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("Extended events not available")
        
        result = blocking_queries_api.get_deadlock_information("test-server", "test-db")
        
        assert result == []

    def test_get_lock_waits_summary_success(self, blocking_queries_api):
        """Test successful lock waits summary retrieval."""
        mock_lock_waits = [
            {
                "wait_type": "LCK_M_S",
                "waiting_task_count": 5,
                "total_wait_time_ms": 50000,
                "avg_wait_time_ms": 10000,
                "max_wait_time_ms": 25000,
                "resource_description": "KEY: 5:123456789:1",
                "unique_sessions_waiting": 3
            },
            {
                "wait_type": "LCK_M_X",
                "waiting_task_count": 2,
                "total_wait_time_ms": 30000,
                "avg_wait_time_ms": 15000,
                "max_wait_time_ms": 20000,
                "resource_description": "PAGE: 5:1:12345",
                "unique_sessions_waiting": 2
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_lock_waits
        
        result = blocking_queries_api.get_lock_waits_summary("test-server", "test-db")
        
        assert len(result) == 2
        assert result[0]["wait_type"] == "LCK_M_S"
        assert result[0]["waiting_task_count"] == 5
        assert result[0]["total_wait_time_ms"] == 50000

    def test_get_lock_waits_summary_error(self, blocking_queries_api):
        """Test lock waits summary retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = blocking_queries_api.get_lock_waits_summary("test-server", "test-db")
        
        assert result == []

    def test_get_blocking_history_success(self, blocking_queries_api):
        """Test successful blocking history retrieval."""
        mock_history = [
            {
                "start_time": datetime(2023, 1, 1, 9, 0, 0),
                "end_time": datetime(2023, 1, 1, 9, 5, 0),
                "avg_duration_ms": 45000.0,
                "avg_cpu_time_ms": 15000.0,
                "avg_logical_io_reads": 150000,
                "count_executions": 10,
                "query_category": "Long Running",
                "query_text_preview": "SELECT * FROM large_table WHERE complex_condition..."
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_history
        
        result = blocking_queries_api.get_blocking_history("test-server", "test-db", 24)
        
        assert len(result) == 1
        assert result[0]["query_category"] == "Long Running"
        assert result[0]["avg_duration_ms"] == 45000.0
        assert result[0]["count_executions"] == 10

    def test_get_blocking_history_error(self, blocking_queries_api):
        """Test blocking history retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("Query Store not available")
        
        result = blocking_queries_api.get_blocking_history("test-server", "test-db")
        
        assert result == []

    def test_get_wait_statistics_success(self, blocking_queries_api):
        """Test successful wait statistics retrieval."""
        mock_wait_stats = [
            {
                "wait_type": "LCK_M_S",
                "waiting_tasks_count": 15,
                "wait_time_ms": 120000,
                "max_wait_time_ms": 30000,
                "signal_wait_time_ms": 5000,
                "signal_wait_percentage": 4.17
            },
            {
                "wait_type": "PAGEIOLATCH_SH",
                "waiting_tasks_count": 8,
                "wait_time_ms": 80000,
                "max_wait_time_ms": 15000,
                "signal_wait_time_ms": 2000,
                "signal_wait_percentage": 2.50
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_wait_stats
        
        result = blocking_queries_api.get_wait_statistics("test-server", "test-db")
        
        assert len(result) == 2
        assert result[0]["wait_type"] == "LCK_M_S"
        assert result[0]["waiting_tasks_count"] == 15
        assert result[0]["signal_wait_percentage"] == 4.17

    def test_get_wait_statistics_error(self, blocking_queries_api):
        """Test wait statistics retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = blocking_queries_api.get_wait_statistics("test-server", "test-db")
        
        assert result == []

    def test_get_lock_escalation_events_success(self, blocking_queries_api):
        """Test successful lock escalation events retrieval."""
        mock_escalations = [
            {
                "escalation_time": datetime(2023, 1, 1, 10, 0, 0),
                "database_name": "test_db",
                "object_name": "users",
                "statement": "SELECT * FROM users WHERE region = 'US'",
                "escalated_lock_count": 5000,
                "hobt_id": 123456789
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_escalations
        
        result = blocking_queries_api.get_lock_escalation_events("test-server", "test-db", 24)
        
        assert len(result) == 1
        assert result[0]["object_name"] == "users"
        assert result[0]["escalated_lock_count"] == 5000

    def test_get_lock_escalation_events_error(self, blocking_queries_api):
        """Test lock escalation events retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("Extended events not available")
        
        result = blocking_queries_api.get_lock_escalation_events("test-server", "test-db")
        
        assert result == []

    def test_get_blocking_summary_success(self, blocking_queries_api):
        """Test successful blocking summary retrieval."""
        mock_summary = [
            {
                "total_blocked_sessions": 5,
                "total_blocking_sessions": 2,
                "longest_blocked_time_ms": 45000,
                "avg_blocked_time_ms": 25000.0,
                "unique_wait_types": 3,
                "common_wait_types": "LCK_M_S, LCK_M_X, PAGEIOLATCH_SH"
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_summary
        
        result = blocking_queries_api.get_blocking_summary("test-server", "test-db")
        
        assert result["total_blocked_sessions"] == 5
        assert result["total_blocking_sessions"] == 2
        assert result["longest_blocked_time_ms"] == 45000
        assert "LCK_M_S" in result["common_wait_types"]

    def test_get_blocking_summary_error(self, blocking_queries_api):
        """Test blocking summary retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = blocking_queries_api.get_blocking_summary("test-server", "test-db")
        
        assert "error" in result
        assert "SQL Error" in result["error"]

    def test_get_long_running_transactions_success(self, blocking_queries_api):
        """Test successful long-running transactions retrieval."""
        mock_transactions = [
            {
                "session_id": 55,
                "login_name": "user1",
                "host_name": "host1",
                "program_name": "SSMS",
                "transaction_id": 123456,
                "transaction_name": "user_transaction",
                "transaction_begin_time": datetime(2023, 1, 1, 9, 0, 0),
                "duration_seconds": 300,
                "transaction_type": 1,
                "transaction_state": 2,
                "transaction_state_desc": "Active",
                "resource_type": "KEY",
                "request_mode": "S",
                "request_type": "LOCK",
                "command": "SELECT",
                "request_status": "running",
                "current_sql": "SELECT * FROM users WHERE region = 'US'"
            }
        ]
        blocking_queries_api.sql_api_client._execute_query.return_value = mock_transactions
        
        result = blocking_queries_api.get_long_running_transactions("test-server", "test-db", 60)
        
        assert len(result) == 1
        assert result[0]["duration_seconds"] == 300
        assert result[0]["transaction_state_desc"] == "Active"
        assert result[0]["login_name"] == "user1"

    def test_get_long_running_transactions_error(self, blocking_queries_api):
        """Test long-running transactions retrieval with error."""
        blocking_queries_api.sql_api_client._execute_query.side_effect = Exception("SQL Error")
        
        result = blocking_queries_api.get_long_running_transactions("test-server", "test-db")
        
        assert result == []


# Integration test that requires environment variables
class TestBlockingQueriesIntegration:
    
    @pytest.mark.skipif(
        not all([
            os.getenv("AZURE_SQL_SUBSCRIPTION_ID"),
            os.getenv("AZURE_SQL_RESOURCE_GROUP"),
            os.getenv("AZURE_SQL_SERVER_NAME"),
            os.getenv("AZURE_SQL_DATABASE_NAME")
        ]),
        reason="Azure SQL environment variables not set"
    )
    def test_blocking_queries_integration(self):
        """Integration test for blocking queries analysis (requires env vars)."""
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
        api = BlockingQueriesAPI(
            credential=credential,
            subscription_id=subscription_id,
            sql_username=sql_username,
            sql_password=sql_password
        )
        
        # Test blocking summary (should work even if no blocking)
        summary = api.get_blocking_summary(server_name, database_name)
        assert isinstance(summary, dict)
        
        # Test current blocking queries (should work even if empty)
        blocking_queries = api.get_current_blocking_queries(server_name, database_name)
        assert isinstance(blocking_queries, list)
        
        # Test wait statistics (should work even if empty)
        wait_stats = api.get_wait_statistics(server_name, database_name)
        assert isinstance(wait_stats, list)