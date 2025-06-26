from typing import Dict, List, Optional
import pyodbc
import logging
from azure.core.credentials import TokenCredential
from azure.mgmt.sql import SqlManagementClient


class AzureSQLAPIClient:
    def __init__(self, credential: TokenCredential, subscription_id: str, sql_username: str = None, sql_password: str = None):
        self.sql_client = SqlManagementClient(credential, subscription_id)
        self.credential = credential
        self.sql_username = sql_username
        self.sql_password = sql_password
    
    def _get_access_token(self) -> str:
        """Get access token for Azure SQL Database authentication."""
        try:
            token = self.credential.get_token("https://database.windows.net/")
            if not token or not token.token:
                raise ValueError("Failed to obtain valid access token from Azure credential")
            return token.token
        except Exception as e:
            logging.error(f"Failed to get access token: {str(e)}")
            raise ConnectionError(f"Azure authentication failed: {str(e)}") from e
    
    def _execute_query(self, server_name: str, database_name: str, query: str) -> List[Dict]:
        """Execute a T-SQL query against the Azure SQL database."""
        conn = None
        cursor = None
        
        # Validate connection parameters to prevent segfault
        if not server_name or not database_name:
            raise ValueError("Server name and database name must be provided")
        
        # Try SQL authentication first if credentials are provided
        if self.sql_username and self.sql_password:
            return self._execute_query_with_sql_auth(server_name, database_name, query)
        
        # Fall back to Azure AD token authentication only if no SQL credentials
        try:
            access_token = self._get_access_token()
            
            # Validate access token
            if not access_token or not isinstance(access_token, str):
                raise ValueError("Invalid access token received from Azure credential")
            
            # Build connection string with access token
            connection_string = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server=tcp:{server_name}.database.windows.net,1433;"
                f"Database={database_name};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
            
            logging.info(f"Attempting to connect to {server_name}.database.windows.net with Azure AD token")
            
            # Create connection with access token
            conn = pyodbc.connect(connection_string, attrs_before={1256: access_token}, timeout=10)
            cursor = conn.cursor()
            
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
            
        except pyodbc.Error as e:
            error_msg = f"ODBC Error connecting to {server_name}.{database_name}: {str(e)}"
            logging.error(error_msg)
            raise ConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to execute query on {server_name}.{database_name}: {str(e)}"
            logging.error(error_msg)
            raise
        finally:
            # Ensure resources are properly cleaned up
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def _execute_query_with_sql_auth(self, server_name: str, database_name: str, query: str) -> List[Dict]:
        """Execute a T-SQL query using SQL Server authentication."""
        conn = None
        cursor = None
        
        try:
            # Build connection string with SQL authentication
            connection_string = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server=tcp:{server_name}.database.windows.net,1433;"
                f"Database={database_name};"
                f"Uid={self.sql_username};"
                f"Pwd={self.sql_password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
            
            logging.info(f"Attempting to connect to {server_name}.database.windows.net with SQL authentication")
            
            # Create connection with SQL authentication
            conn = pyodbc.connect(connection_string, timeout=10)
            cursor = conn.cursor()
            
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
            
        except pyodbc.Error as e:
            error_msg = f"SQL Auth ODBC Error connecting to {server_name}.{database_name}: {str(e)}"
            logging.error(error_msg)
            raise ConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"SQL Auth failed to execute query on {server_name}.{database_name}: {str(e)}"
            logging.error(error_msg)
            raise
        finally:
            # Ensure resources are properly cleaned up
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def get_database_advisors(self, subscription_id: str, resource_group: str, server_name: str, database_name: str) -> Dict:
        advisors = self.sql_client.database_advisors.list_by_database(
            resource_group_name=resource_group,
            server_name=server_name,
            database_name=database_name
        )
        return {"value": [advisor.as_dict() for advisor in advisors]}
    
    def get_database_recommended_actions(self, subscription_id: str, resource_group: str, server_name: str, database_name: str, advisor_name: str) -> Dict:
        actions = self.sql_client.database_recommended_actions.list_by_database_advisor(
            resource_group_name=resource_group,
            server_name=server_name,
            database_name=database_name,
            advisor_name=advisor_name
        )
        return {"value": [action.as_dict() for action in actions]}
    
    def get_database_usages(self, subscription_id: str, resource_group: str, server_name: str, database_name: str) -> Dict:
        usages = self.sql_client.database_usages.list_by_database(
            resource_group_name=resource_group,
            server_name=server_name,
            database_name=database_name
        )
        return {"value": [usage.as_dict() for usage in usages]}
    
    def get_database_operations(self, subscription_id: str, resource_group: str, server_name: str, database_name: str) -> Dict:
        operations = self.sql_client.database_operations.list_by_database(
            resource_group_name=resource_group,
            server_name=server_name,
            database_name=database_name
        )
        return {"value": [op.as_dict() for op in operations]}
    
    def get_database_vulnerability_assessments(self, subscription_id: str, resource_group: str, server_name: str, database_name: str) -> Dict:
        assessments = self.sql_client.database_vulnerability_assessments.list_by_database(
            resource_group_name=resource_group,
            server_name=server_name,
            database_name=database_name
        )
        return {"value": [assessment.as_dict() for assessment in assessments]}
    
    def get_database_security_alert_policies(self, subscription_id: str, resource_group: str, server_name: str, database_name: str) -> Dict:
        policies = self.sql_client.database_security_alert_policies.list_by_database(
            resource_group_name=resource_group,
            server_name=server_name,
            database_name=database_name
        )
        return {"value": [policy.as_dict() for policy in policies]}
    
    def get_database_automatic_tuning(self, subscription_id: str, resource_group: str, server_name: str, database_name: str) -> Dict:
        tuning = self.sql_client.database_automatic_tuning.get(
            resource_group_name=resource_group,
            server_name=server_name,
            database_name=database_name
        )
        return tuning.as_dict()
    
    def get_top_cpu_queries(self, subscription_id: str, resource_group: str, server_name: str, database_name: str, 
                           top_count: int = 15, hours_back: int = 2) -> List[Dict]:
        """Get top CPU consuming queries from Query Store."""
        query = f"""
        SELECT TOP {top_count}
            qt.query_sql_text,
            rs.avg_cpu_time,
            rs.count_executions as execution_count,
            (rs.avg_cpu_time * rs.count_executions) as total_cpu_time,
            rs.max_cpu_time,
            rs.min_cpu_time,
            CAST(rs.last_execution_time as DATETIME2) as last_execution_time,
            rs.avg_duration,
            (rs.avg_duration * rs.count_executions) as total_duration
        FROM sys.query_store_query_text qt
        JOIN sys.query_store_query q ON qt.query_text_id = q.query_text_id
        JOIN sys.query_store_plan p ON q.query_id = p.query_id
        JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
        WHERE rs.last_execution_time > DATEADD(hour, -{hours_back}, GETDATE())
        ORDER BY rs.avg_cpu_time DESC;
        """
        
        return self._execute_query(server_name, database_name, query)
    
    def get_slow_queries(self, subscription_id: str, resource_group: str, server_name: str, database_name: str,
                        top_count: int = 15, hours_back: int = 2) -> List[Dict]:
        """Get slow/long-running queries from Query Store."""
        query = f"""
        SELECT TOP {top_count}
            qt.query_sql_text,
            rs.avg_duration,
            rs.count_executions as execution_count,
            (rs.avg_duration * rs.count_executions) as total_duration,
            rs.max_duration,
            rs.min_duration,
            CAST(rs.last_execution_time as DATETIME2) as last_execution_time,
            rs.avg_cpu_time,
            (rs.avg_cpu_time * rs.count_executions) as total_cpu_time
        FROM sys.query_store_query_text qt
        JOIN sys.query_store_query q ON qt.query_text_id = q.query_text_id
        JOIN sys.query_store_plan p ON q.query_id = p.query_id
        JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
        WHERE rs.last_execution_time > DATEADD(hour, -{hours_back}, GETDATE())
        ORDER BY rs.avg_duration DESC;
        """
        
        return self._execute_query(server_name, database_name, query)