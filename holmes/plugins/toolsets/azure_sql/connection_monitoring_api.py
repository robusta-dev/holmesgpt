from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
from azure.core.credentials import TokenCredential
from azure.monitor.query import MetricsQueryClient
from .azure_sql_api import AzureSQLAPIClient


class ConnectionMonitoringAPI:
    def __init__(self, credential: TokenCredential, subscription_id: str, sql_username: str = None, sql_password: str = None):
        self.sql_api_client = AzureSQLAPIClient(credential, subscription_id, sql_username, sql_password)
        self.metrics_client = MetricsQueryClient(credential)
        self.subscription_id = subscription_id
    
    def get_connection_metrics(self, resource_group: str, server_name: str, database_name: str, hours_back: int = 2) -> Dict:
        """Get connection-related metrics from Azure Monitor."""
        resource_id = (
            f"subscriptions/{self.subscription_id}/"
            f"resourceGroups/{resource_group}/"
            f"providers/Microsoft.Sql/servers/{server_name}/"
            f"databases/{database_name}"
        )
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        try:
            metrics_data = self.metrics_client.query(
                resource_uri=resource_id,
                metric_names=[
                    "connection_successful", 
                    "connection_failed", 
                    "sessions_count",
                    "blocked_by_firewall"
                ],
                timespan=(start_time, end_time),
                granularity=timedelta(minutes=5),
                aggregations=["Maximum", "Average", "Total"]
            )
            
            result = {}
            for metric in metrics_data.metrics:
                metric_data = []
                for timeseries in metric.timeseries:
                    for data_point in timeseries.data:
                        metric_data.append({
                            "timestamp": data_point.time_stamp.isoformat(),
                            "maximum": data_point.maximum,
                            "average": data_point.average,
                            "total": data_point.total
                        })
                result[metric.name] = metric_data
            
            return result
            
        except Exception as e:
            logging.error(f"Failed to get connection metrics: {str(e)}")
            return {"error": str(e)}
    
    def get_active_connections(self, server_name: str, database_name: str) -> List[Dict]:
        """Get currently active connections using DMV."""
        query = """
        SELECT 
            s.session_id,
            s.login_name,
            s.host_name,
            s.program_name,
            s.login_time,
            s.last_request_start_time,
            s.last_request_end_time,
            s.status,
            s.cpu_time,
            s.memory_usage,
            s.total_scheduled_time,
            s.total_elapsed_time,
            s.reads,
            s.writes,
            s.logical_reads,
            CASE 
                WHEN r.session_id IS NOT NULL THEN 'Active'
                ELSE 'Inactive'
            END as connection_status,
            r.blocking_session_id,
            r.wait_type,
            r.wait_time,
            r.wait_resource
        FROM sys.dm_exec_sessions s
        LEFT JOIN sys.dm_exec_requests r ON s.session_id = r.session_id
        WHERE s.is_user_process = 1
        ORDER BY s.login_time DESC;
        """
        
        try:
            return self.sql_api_client._execute_query(server_name, database_name, query)
        except Exception as e:
            logging.error(f"Failed to get active connections: {str(e)}")
            return []
    
    def get_connection_summary(self, server_name: str, database_name: str) -> Dict:
        """Get connection summary statistics."""
        query = """
        SELECT 
            COUNT(*) as total_connections,
            COUNT(CASE WHEN r.session_id IS NOT NULL THEN 1 END) as active_connections,
            COUNT(CASE WHEN r.session_id IS NULL THEN 1 END) as idle_connections,
            COUNT(CASE WHEN r.blocking_session_id > 0 THEN 1 END) as blocked_connections,
            COUNT(DISTINCT s.login_name) as unique_users,
            COUNT(DISTINCT s.host_name) as unique_hosts,
            MAX(s.login_time) as latest_login,
            MIN(s.login_time) as earliest_login
        FROM sys.dm_exec_sessions s
        LEFT JOIN sys.dm_exec_requests r ON s.session_id = r.session_id
        WHERE s.is_user_process = 1;
        """
        
        try:
            result = self.sql_api_client._execute_query(server_name, database_name, query)
            return result[0] if result else {}
        except Exception as e:
            logging.error(f"Failed to get connection summary: {str(e)}")
            return {"error": str(e)}
    
    def get_failed_connections(self, server_name: str, database_name: str, hours_back: int = 24) -> List[Dict]:
        """Get failed connection attempts from extended events or system health."""
        # Note: This query looks for connectivity ring buffer events
        query = f"""
        WITH ConnectivityEvents AS (
            SELECT 
                CAST(event_data AS XML) as event_xml,
                timestamp_utc
            FROM sys.fn_xe_file_target_read_file('system_health*.xel', null, null, null)
            WHERE object_name = 'connectivity_ring_buffer_recorded'
            AND timestamp_utc > DATEADD(hour, -{hours_back}, GETUTCDATE())
        )
        SELECT TOP 100
            timestamp_utc,
            event_xml.value('(/Record/ConnectivityTraceRecord/RecordType)[1]', 'varchar(50)') as record_type,
            event_xml.value('(/Record/ConnectivityTraceRecord/RecordSource)[1]', 'varchar(50)') as record_source,
            event_xml.value('(/Record/ConnectivityTraceRecord/Spid)[1]', 'int') as spid,
            event_xml.value('(/Record/ConnectivityTraceRecord/SniConsumerError)[1]', 'int') as sni_consumer_error,
            event_xml.value('(/Record/ConnectivityTraceRecord/State)[1]', 'int') as state,
            event_xml.value('(/Record/ConnectivityTraceRecord/RemoteHost)[1]', 'varchar(100)') as remote_host,
            event_xml.value('(/Record/ConnectivityTraceRecord/RemotePort)[1]', 'varchar(10)') as remote_port
        FROM ConnectivityEvents
        WHERE event_xml.value('(/Record/ConnectivityTraceRecord/RecordType)[1]', 'varchar(50)') LIKE '%Error%'
        ORDER BY timestamp_utc DESC;
        """
        
        try:
            return self.sql_api_client._execute_query(server_name, database_name, query)
        except Exception as e:
            logging.warning(f"Failed to get failed connections (extended events may not be available): {str(e)}")
            # Fallback to a simpler approach using error log if available
            return []
    
    def get_connection_pool_stats(self, server_name: str, database_name: str) -> Dict:
        """Get connection pool related statistics."""
        query = """
        SELECT 
            'Database Connections' as metric_name,
            COUNT(*) as current_value,
            'connections' as unit
        FROM sys.dm_exec_sessions
        WHERE is_user_process = 1
        UNION ALL
        SELECT 
            'Active Requests' as metric_name,
            COUNT(*) as current_value,
            'requests' as unit
        FROM sys.dm_exec_requests
        WHERE session_id > 50
        UNION ALL
        SELECT 
            'Waiting Tasks' as metric_name,
            COUNT(*) as current_value,
            'tasks' as unit
        FROM sys.dm_os_waiting_tasks
        WHERE session_id > 50;
        """
        
        try:
            results = self.sql_api_client._execute_query(server_name, database_name, query)
            return {row['metric_name']: {"value": row['current_value'], "unit": row['unit']} for row in results}
        except Exception as e:
            logging.error(f"Failed to get connection pool stats: {str(e)}")
            return {"error": str(e)}