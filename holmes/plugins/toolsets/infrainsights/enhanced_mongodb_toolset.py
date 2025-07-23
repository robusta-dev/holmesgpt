import json
import logging
from typing import Dict, Any, Optional
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite, ToolParameter

logger = logging.getLogger(__name__)


class MongoDBHealthCheckTool(Tool):
    """Tool to check MongoDB instance health and server status"""
    
    name: str = "mongodb_health_check"
    description: str = "Check the health status of a MongoDB instance including server status, replica set status, and basic connectivity"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance to check",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Checking health for MongoDB instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            health_data = self.toolset.infrainsights_client.get_mongodb_health(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=health_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error checking MongoDB health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check MongoDB health: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"mongodb_health_check(instance_name={instance_name})"


class MongoDBDatabaseListTool(Tool):
    """Tool to list all databases in MongoDB instance"""
    
    name: str = "mongodb_list_databases"
    description: str = "List all databases in the MongoDB instance with size information and collection counts"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Listing databases for MongoDB instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            databases_data = self.toolset.infrainsights_client.get_mongodb_databases(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=databases_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error listing MongoDB databases: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list MongoDB databases: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"mongodb_list_databases(instance_name={instance_name})"


class MongoDBCollectionStatsTool(Tool):
    """Tool to get MongoDB collection statistics"""
    
    name: str = "mongodb_collection_stats"
    description: str = "Get detailed statistics for MongoDB collections including document counts, storage size, and index information"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        ),
        "database_name": ToolParameter(
            description="Name of the database to analyze",
            type="string",
            required=True
        ),
        "collection_name": ToolParameter(
            description="Name of the collection (optional - if not provided, returns stats for all collections)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            database_name = params.get('database_name')
            collection_name = params.get('collection_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
                
            if not database_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="database_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting collection stats for MongoDB instance: {instance_name}, database: {database_name}, collection: {collection_name or 'all'}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            stats_data = self.toolset.infrainsights_client.get_mongodb_collection_stats(instance, database_name, collection_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=stats_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting MongoDB collection stats: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get MongoDB collection stats: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        database_name = params.get('database_name', 'unknown')
        collection_name = params.get('collection_name', 'all')
        return f"mongodb_collection_stats(instance_name={instance_name}, database_name={database_name}, collection_name={collection_name})"


class MongoDBPerformanceMetricsTool(Tool):
    """Tool to get MongoDB performance metrics and server statistics"""
    
    name: str = "mongodb_performance_metrics"
    description: str = "Get comprehensive performance metrics including operations per second, memory usage, connection stats, and lock statistics"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Getting performance metrics for MongoDB instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            metrics_data = self.toolset.infrainsights_client.get_mongodb_performance_metrics(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=metrics_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting MongoDB performance metrics: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get MongoDB performance metrics: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"mongodb_performance_metrics(instance_name={instance_name})"


class MongoDBSlowQueriesAnalysisTool(Tool):
    """Tool to analyze slow queries and query performance"""
    
    name: str = "mongodb_slow_queries_analysis"
    description: str = "Analyze slow queries, query patterns, and execution statistics to identify performance bottlenecks"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        ),
        "database_name": ToolParameter(
            description="Name of the database to analyze (optional - if not provided, analyzes all databases)",
            type="string",
            required=False
        ),
        "slow_threshold_ms": ToolParameter(
            description="Threshold in milliseconds for slow queries (default: 100ms)",
            type="integer",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            database_name = params.get('database_name')
            slow_threshold_ms = params.get('slow_threshold_ms', 100)
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing slow queries for MongoDB instance: {instance_name}, database: {database_name or 'all'}, threshold: {slow_threshold_ms}ms")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            slow_queries_data = self.toolset.infrainsights_client.get_mongodb_slow_queries(instance, database_name, slow_threshold_ms)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=slow_queries_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing MongoDB slow queries: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze MongoDB slow queries: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        database_name = params.get('database_name', 'all')
        slow_threshold_ms = params.get('slow_threshold_ms', 100)
        return f"mongodb_slow_queries_analysis(instance_name={instance_name}, database_name={database_name}, slow_threshold_ms={slow_threshold_ms})"


class MongoDBIndexAnalysisTool(Tool):
    """Tool to analyze MongoDB indexes and optimization opportunities"""
    
    name: str = "mongodb_index_analysis"
    description: str = "Analyze index usage, identify missing indexes, and find optimization opportunities for better query performance"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        ),
        "database_name": ToolParameter(
            description="Name of the database to analyze",
            type="string",
            required=True
        ),
        "collection_name": ToolParameter(
            description="Name of the collection (optional - if not provided, analyzes all collections)",
            type="string",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            database_name = params.get('database_name')
            collection_name = params.get('collection_name')
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
                
            if not database_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="database_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing indexes for MongoDB instance: {instance_name}, database: {database_name}, collection: {collection_name or 'all'}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            index_data = self.toolset.infrainsights_client.get_mongodb_index_analysis(instance, database_name, collection_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=index_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing MongoDB indexes: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze MongoDB indexes: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        database_name = params.get('database_name', 'unknown')
        collection_name = params.get('collection_name', 'all')
        return f"mongodb_index_analysis(instance_name={instance_name}, database_name={database_name}, collection_name={collection_name})"


class MongoDBReplicaSetStatusTool(Tool):
    """Tool to check MongoDB replica set status and configuration"""
    
    name: str = "mongodb_replica_set_status"
    description: str = "Check replica set status, member health, election status, and replication lag for MongoDB cluster analysis"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Checking replica set status for MongoDB instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            replica_status_data = self.toolset.infrainsights_client.get_mongodb_replica_set_status(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=replica_status_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error checking MongoDB replica set status: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check MongoDB replica set status: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"mongodb_replica_set_status(instance_name={instance_name})"


class MongoDBConnectionAnalysisTool(Tool):
    """Tool to analyze MongoDB connections and connection pool statistics"""
    
    name: str = "mongodb_connection_analysis"
    description: str = "Analyze active connections, connection pool statistics, and identify connection-related issues"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing connections for MongoDB instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            connection_data = self.toolset.infrainsights_client.get_mongodb_connection_analysis(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=connection_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing MongoDB connections: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze MongoDB connections: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"mongodb_connection_analysis(instance_name={instance_name})"


class MongoDBOperationsAnalysisTool(Tool):
    """Tool to analyze MongoDB operations and operation statistics"""
    
    name: str = "mongodb_operations_analysis"
    description: str = "Analyze current operations, long-running queries, and operation statistics for performance troubleshooting"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        ),
        "operation_threshold_ms": ToolParameter(
            description="Threshold in milliseconds for long-running operations (default: 1000ms)",
            type="integer",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            operation_threshold_ms = params.get('operation_threshold_ms', 1000)
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing operations for MongoDB instance: {instance_name}, threshold: {operation_threshold_ms}ms")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            operations_data = self.toolset.infrainsights_client.get_mongodb_operations_analysis(instance, operation_threshold_ms)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=operations_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing MongoDB operations: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze MongoDB operations: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        operation_threshold_ms = params.get('operation_threshold_ms', 1000)
        return f"mongodb_operations_analysis(instance_name={instance_name}, operation_threshold_ms={operation_threshold_ms})"


class MongoDBSecurityAuditTool(Tool):
    """Tool to perform MongoDB security audit and best practices check"""
    
    name: str = "mongodb_security_audit"
    description: str = "Perform security audit including authentication, authorization, encryption, and security best practices compliance"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Performing security audit for MongoDB instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            security_data = self.toolset.infrainsights_client.get_mongodb_security_audit(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=security_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error performing MongoDB security audit: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to perform MongoDB security audit: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"mongodb_security_audit(instance_name={instance_name})"


class MongoDBBackupAnalysisTool(Tool):
    """Tool to analyze MongoDB backup status and strategies"""
    
    name: str = "mongodb_backup_analysis"
    description: str = "Analyze backup configuration, recent backup status, and backup strategy recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing backup status for MongoDB instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            backup_data = self.toolset.infrainsights_client.get_mongodb_backup_analysis(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=backup_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing MongoDB backup status: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze MongoDB backup status: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"mongodb_backup_analysis(instance_name={instance_name})"


class MongoDBCapacityPlanningTool(Tool):
    """Tool to analyze MongoDB capacity and provide growth projections"""
    
    name: str = "mongodb_capacity_planning"
    description: str = "Analyze storage usage, growth trends, and provide capacity planning recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the MongoDB instance",
            type="string",
            required=True
        ),
        "projection_days": ToolParameter(
            description="Number of days to project growth (default: 30)",
            type="integer",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            projection_days = params.get('projection_days', 30)
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing capacity planning for MongoDB instance: {instance_name}, projection: {projection_days} days")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "mongodb", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"MongoDB instance '{instance_name}' not found",
                    params=params
                )
            
            capacity_data = self.toolset.infrainsights_client.get_mongodb_capacity_planning(instance, projection_days)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=capacity_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing MongoDB capacity planning: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze MongoDB capacity planning: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        projection_days = params.get('projection_days', 30)
        return f"mongodb_capacity_planning(instance_name={instance_name}, projection_days={projection_days})"


class EnhancedMongoDBToolset(Toolset):
    """Enhanced MongoDB toolset with InfraInsights integration for comprehensive database monitoring and analysis"""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2, InfraInsightsConfig
        
        logger.info("🚀🚀🚀 CREATING ENHANCED MONGODB TOOLSET 🚀🚀🚀")
        
        # Create comprehensive MongoDB tools
        tools = [
            # Basic operations and health
            MongoDBHealthCheckTool(toolset=None),
            MongoDBDatabaseListTool(toolset=None),
            
            # Performance and monitoring
            MongoDBPerformanceMetricsTool(toolset=None),
            MongoDBSlowQueriesAnalysisTool(toolset=None),
            MongoDBOperationsAnalysisTool(toolset=None),
            
            # Database and collection analysis
            MongoDBCollectionStatsTool(toolset=None),
            MongoDBIndexAnalysisTool(toolset=None),
            
            # Cluster and replication
            MongoDBReplicaSetStatusTool(toolset=None),
            MongoDBConnectionAnalysisTool(toolset=None),
            
            # Security and compliance
            MongoDBSecurityAuditTool(toolset=None),
            
            # Operational excellence
            MongoDBBackupAnalysisTool(toolset=None),
            MongoDBCapacityPlanningTool(toolset=None),
        ]
        
        # Initialize Toolset with required parameters
        super().__init__(
            name="infrainsights_mongodb_enhanced",
            description="Enhanced MongoDB toolset with InfraInsights instance management for comprehensive database monitoring, performance analysis, and operational excellence",
            enabled=True,
            tools=tools,
            tags=[ToolsetTag.DATABASE],
            prerequisites=[]  # Remove prerequisites during initialization
        )
        
        # Initialize InfraInsights client with default config
        self.infrainsights_config = InfraInsightsConfig(
            base_url="http://localhost:3000",  # Default backend URL
            api_key=None,  # Will be set from environment or config
            username=None,
            password=None,
            timeout=30,
            enable_name_lookup=True,
            use_v2_api=True
        )
        self.infrainsights_client = InfraInsightsClientV2(self.infrainsights_config)
        
        logger.info(f"🔧 Initialized with default URL: {self.infrainsights_config.base_url}")
        
        # Set toolset reference for tools
        for tool in self.tools:
            tool.toolset = self
        
        # Set config to None initially
        self.config = None
        
        logger.info("✅✅✅ ENHANCED MONGODB TOOLSET CREATED SUCCESSFULLY ✅✅✅")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with the provided configuration"""
        logger.info(f"🚀🚀🚀 CONFIGURING ENHANCED MONGODB TOOLSET 🚀🚀🚀")
        logger.info(f"🔧 Config received: {config}")
        
        # Store the config
        self.config = config
        
        # Extract InfraInsights configuration - handle both nested and flat structures
        if isinstance(config, dict) and 'config' in config:
            # Nested structure: { "config": { "infrainsights_url": "...", ... } }
            infrainsights_config = config['config']
            logger.info(f"🔧 Using nested config structure: {infrainsights_config}")
        elif isinstance(config, dict):
            # Flat structure: { "infrainsights_url": "...", ... }
            infrainsights_config = config
            logger.info(f"🔧 Using flat config structure: {infrainsights_config}")
        else:
            logger.warning(f"🔧 Unexpected config type: {type(config)}, using defaults")
            infrainsights_config = {}
        
        # Update InfraInsights client configuration
        base_url = infrainsights_config.get('infrainsights_url', 'http://localhost:3000')
        api_key = infrainsights_config.get('api_key')
        timeout = infrainsights_config.get('timeout', 30)
        enable_name_lookup = infrainsights_config.get('enable_name_lookup', True)
        use_v2_api = infrainsights_config.get('use_v2_api', True)
        
        logger.info(f"🔧 Extracted configuration:")
        logger.info(f"🔧   base_url: {base_url}")
        logger.info(f"🔧   api_key: {'***' if api_key else 'None'}")
        logger.info(f"🔧   timeout: {timeout}")
        logger.info(f"🔧   enable_name_lookup: {enable_name_lookup}")
        logger.info(f"🔧   use_v2_api: {use_v2_api}")
        
        # Update the InfraInsights config
        self.infrainsights_config.base_url = base_url
        self.infrainsights_config.api_key = api_key
        self.infrainsights_config.timeout = timeout
        self.infrainsights_config.enable_name_lookup = enable_name_lookup
        self.infrainsights_config.use_v2_api = use_v2_api
        
        # Reinitialize the client with updated config
        from .infrainsights_client_v2 import InfraInsightsClientV2
        self.infrainsights_client = InfraInsightsClientV2(self.infrainsights_config)
        
        # Now add prerequisites after configuration is complete
        self.prerequisites = [CallablePrerequisite(callable=self._check_prerequisites)]
        
        logger.info(f"✅✅✅ ENHANCED MONGODB TOOLSET CONFIGURED WITH URL: {base_url} ✅✅✅")
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if InfraInsights client can connect to the backend"""
        try:
            logger.info(f"🔍 Checking prerequisites for InfraInsights MongoDB client")
            logger.info(f"🔍 Current base_url: {self.infrainsights_config.base_url}")
            logger.info(f"🔍 API key configured: {'Yes' if self.infrainsights_config.api_key else 'No'}")
            
            # Try to connect to InfraInsights backend
            logger.info(f"🔍 Attempting health check to: {self.infrainsights_config.base_url}/api/health")
            if self.infrainsights_client.health_check():
                logger.info("✅ InfraInsights backend health check passed")
                return True, f"InfraInsights backend is accessible at {self.infrainsights_config.base_url}"
            else:
                logger.warning("❌ InfraInsights backend health check failed")
                return False, f"InfraInsights backend at {self.infrainsights_config.base_url} is not accessible"
        except Exception as e:
            logger.error(f"🔍 Prerequisites check failed: {str(e)}")
            # Still allow toolset to load even if health check fails
            return True, f"InfraInsights backend health check failed: {str(e)} (toolset still enabled)"
    
    def get_example_config(self) -> Dict[str, Any]:
        """Return example configuration for this toolset"""
        return {
            "config": {
                "infrainsights_url": "http://k8s-ui-service.monitoring:5000",
                "api_key": "your-api-key-here",
                "timeout": 30,
                "enable_name_lookup": True,
                "use_v2_api": True
            }
        } 