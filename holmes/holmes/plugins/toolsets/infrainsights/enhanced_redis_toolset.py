import json
import logging
from typing import Dict, Any, Optional
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite, ToolParameter

logger = logging.getLogger(__name__)


class RedisHealthCheckTool(Tool):
    """Tool to check Redis instance health and server information"""
    
    name: str = "redis_health_check"
    description: str = "Check the health status of a Redis instance including server info, memory usage, and connectivity"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to check",
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
            
            logger.info(f"🔍 Checking health for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            health_data = self.toolset.infrainsights_client.get_redis_health(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=health_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error checking Redis health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Redis health: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_health_check(instance_name={instance_name})"


class RedisPerformanceMetricsTool(Tool):
    """Tool to get Redis performance metrics and statistics"""
    
    name: str = "redis_performance_metrics"
    description: str = "Get comprehensive Redis performance metrics including operations per second, hit rates, memory usage, and connection statistics"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Getting performance metrics for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            metrics_data = self.toolset.infrainsights_client.get_redis_performance_metrics(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=metrics_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error getting Redis performance metrics: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get Redis performance metrics: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_performance_metrics(instance_name={instance_name})"


class RedisMemoryAnalysisTool(Tool):
    """Tool to analyze Redis memory usage and optimization opportunities"""
    
    name: str = "redis_memory_analysis"
    description: str = "Analyze Redis memory usage, fragmentation, and provide memory optimization recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Analyzing memory usage for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            memory_data = self.toolset.infrainsights_client.get_redis_memory_analysis(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=memory_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis memory: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis memory: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_memory_analysis(instance_name={instance_name})"


class RedisKeyAnalysisTool(Tool):
    """Tool to analyze Redis keys, patterns, and key space statistics"""
    
    name: str = "redis_key_analysis"
    description: str = "Analyze Redis key patterns, key space distribution, and identify large or problematic keys"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
            type="string",
            required=True
        ),
        "database_id": ToolParameter(
            description="Redis database ID to analyze (default: 0)",
            type="integer",
            required=False
        ),
        "pattern": ToolParameter(
            description="Key pattern to analyze (optional, e.g., 'user:*')",
            type="string",
            required=False
        ),
        "sample_size": ToolParameter(
            description="Number of keys to sample for analysis (default: 1000)",
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
            database_id = params.get('database_id', 0)
            pattern = params.get('pattern')
            sample_size = params.get('sample_size', 1000)
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing keys for Redis instance: {instance_name}, DB: {database_id}, pattern: {pattern or 'all'}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            key_data = self.toolset.infrainsights_client.get_redis_key_analysis(instance, database_id, pattern, sample_size)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=key_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis keys: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis keys: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        database_id = params.get('database_id', 0)
        pattern = params.get('pattern', 'all')
        return f"redis_key_analysis(instance_name={instance_name}, database_id={database_id}, pattern={pattern})"


class RedisSlowLogAnalysisTool(Tool):
    """Tool to analyze Redis slow log and query performance"""
    
    name: str = "redis_slow_log_analysis"
    description: str = "Analyze Redis slow log to identify performance bottlenecks and slow commands"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
            type="string",
            required=True
        ),
        "max_entries": ToolParameter(
            description="Maximum number of slow log entries to analyze (default: 100)",
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
            max_entries = params.get('max_entries', 100)
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing slow log for Redis instance: {instance_name}, max entries: {max_entries}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            slow_log_data = self.toolset.infrainsights_client.get_redis_slow_log_analysis(instance, max_entries)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=slow_log_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis slow log: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis slow log: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        max_entries = params.get('max_entries', 100)
        return f"redis_slow_log_analysis(instance_name={instance_name}, max_entries={max_entries})"


class RedisConnectionAnalysisTool(Tool):
    """Tool to analyze Redis connections and client statistics"""
    
    name: str = "redis_connection_analysis"
    description: str = "Analyze Redis connections, client statistics, and connection pool health"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Analyzing connections for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            connection_data = self.toolset.infrainsights_client.get_redis_connection_analysis(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=connection_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis connections: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis connections: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_connection_analysis(instance_name={instance_name})"


class RedisReplicationStatusTool(Tool):
    """Tool to check Redis replication status and master-slave health"""
    
    name: str = "redis_replication_status"
    description: str = "Check Redis replication status, master-slave configuration, and replication lag"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Checking replication status for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            replication_data = self.toolset.infrainsights_client.get_redis_replication_status(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=replication_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error checking Redis replication status: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Redis replication status: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_replication_status(instance_name={instance_name})"


class RedisPersistenceAnalysisTool(Tool):
    """Tool to analyze Redis persistence configuration and backup status"""
    
    name: str = "redis_persistence_analysis"
    description: str = "Analyze Redis persistence settings (RDB/AOF), backup status, and data durability configuration"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Analyzing persistence for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            persistence_data = self.toolset.infrainsights_client.get_redis_persistence_analysis(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=persistence_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis persistence: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis persistence: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_persistence_analysis(instance_name={instance_name})"


class RedisClusterAnalysisTool(Tool):
    """Tool to analyze Redis Cluster status and node health"""
    
    name: str = "redis_cluster_analysis"
    description: str = "Analyze Redis Cluster status, node health, slot distribution, and cluster configuration"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Analyzing cluster status for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            cluster_data = self.toolset.infrainsights_client.get_redis_cluster_analysis(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=cluster_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis cluster: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis cluster: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_cluster_analysis(instance_name={instance_name})"


class RedisSecurityAuditTool(Tool):
    """Tool to perform Redis security audit and configuration analysis"""
    
    name: str = "redis_security_audit"
    description: str = "Perform Redis security audit including authentication, ACL configuration, and security best practices"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Performing security audit for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            security_data = self.toolset.infrainsights_client.get_redis_security_audit(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=security_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error performing Redis security audit: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to perform Redis security audit: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_security_audit(instance_name={instance_name})"


class RedisCapacityPlanningTool(Tool):
    """Tool to analyze Redis capacity and provide growth projections"""
    
    name: str = "redis_capacity_planning"
    description: str = "Analyze Redis memory usage, growth trends, and provide capacity planning recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Analyzing capacity planning for Redis instance: {instance_name}, projection: {projection_days} days")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            capacity_data = self.toolset.infrainsights_client.get_redis_capacity_planning(instance, projection_days)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=capacity_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis capacity planning: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis capacity planning: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        projection_days = params.get('projection_days', 30)
        return f"redis_capacity_planning(instance_name={instance_name}, projection_days={projection_days})"


class RedisConfigurationAnalysisTool(Tool):
    """Tool to analyze Redis configuration and optimization opportunities"""
    
    name: str = "redis_configuration_analysis"
    description: str = "Analyze Redis configuration settings and provide optimization recommendations for performance and reliability"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance",
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
            
            logger.info(f"🔍 Analyzing configuration for Redis instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "redis", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Redis instance '{instance_name}' not found",
                    params=params
                )
            
            config_data = self.toolset.infrainsights_client.get_redis_configuration_analysis(instance)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=config_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis configuration: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis configuration: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_configuration_analysis(instance_name={instance_name})"


class EnhancedRedisToolset(Toolset):
    """Enhanced Redis toolset with InfraInsights integration for comprehensive cache monitoring and analysis"""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2, InfraInsightsConfig
        
        logger.info("🚀🚀🚀 CREATING ENHANCED REDIS TOOLSET 🚀🚀🚀")
        
        # Create comprehensive Redis tools
        tools = [
            # Basic operations and health
            RedisHealthCheckTool(toolset=None),
            RedisPerformanceMetricsTool(toolset=None),
            
            # Memory and optimization
            RedisMemoryAnalysisTool(toolset=None),
            RedisKeyAnalysisTool(toolset=None),
            RedisConfigurationAnalysisTool(toolset=None),
            
            # Performance monitoring
            RedisSlowLogAnalysisTool(toolset=None),
            RedisConnectionAnalysisTool(toolset=None),
            
            # High availability and clustering
            RedisReplicationStatusTool(toolset=None),
            RedisClusterAnalysisTool(toolset=None),
            
            # Data persistence and reliability
            RedisPersistenceAnalysisTool(toolset=None),
            
            # Security and compliance
            RedisSecurityAuditTool(toolset=None),
            
            # Operational excellence
            RedisCapacityPlanningTool(toolset=None),
        ]
        
        # Initialize Toolset with required parameters
        super().__init__(
            name="infrainsights_redis_enhanced",
            description="Enhanced Redis toolset with InfraInsights instance management for comprehensive cache monitoring, performance analysis, and operational excellence",
            enabled=True,
            tools=tools,
            tags=[ToolsetTag.CLUSTER],
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
        
        logger.info("✅✅✅ ENHANCED REDIS TOOLSET CREATED SUCCESSFULLY ✅✅✅")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with the provided configuration"""
        logger.info(f"🚀🚀🚀 CONFIGURING ENHANCED REDIS TOOLSET 🚀🚀🚀")
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
        
        logger.info(f"✅✅✅ ENHANCED REDIS TOOLSET CONFIGURED WITH URL: {base_url} ✅✅✅")
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if InfraInsights client can connect to the backend"""
        try:
            logger.info(f"🔍 Checking prerequisites for InfraInsights Redis client")
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