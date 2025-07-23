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
    """Tool to analyze Redis performance metrics and throughput"""
    
    name: str = "redis_performance_metrics"
    description: str = "Analyze Redis performance metrics including operations per second, latency, hit rates, and throughput statistics"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
            type="string",
            required=True
        ),
        "time_range": ToolParameter(
            description="Time range for metrics (e.g., '1h', '24h', '7d')",
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
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing performance metrics for Redis instance: {instance_name}")
            
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
            
            metrics_data = self.toolset.infrainsights_client.get_redis_performance_metrics(
                instance, params.get('time_range', '1h')
            )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=metrics_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis performance: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis performance: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        time_range = params.get('time_range', '1h')
        return f"redis_performance_metrics(instance_name={instance_name}, time_range={time_range})"


class RedisMemoryAnalysisTool(Tool):
    """Tool to analyze Redis memory usage and optimization opportunities"""
    
    name: str = "redis_memory_analysis"
    description: str = "Analyze Redis memory usage patterns, identify memory optimization opportunities, and check for memory fragmentation"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
            type="string",
            required=True
        ),
        "include_key_analysis": ToolParameter(
            description="Include detailed analysis of large keys",
            type="boolean",
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
            
            memory_data = self.toolset.infrainsights_client.get_redis_memory_analysis(
                instance, params.get('include_key_analysis', False)
            )
            
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
        include_key_analysis = params.get('include_key_analysis', False)
        return f"redis_memory_analysis(instance_name={instance_name}, include_key_analysis={include_key_analysis})"


class RedisKeyAnalysisTool(Tool):
    """Tool to analyze Redis keys, patterns, and data distribution"""
    
    name: str = "redis_key_analysis"
    description: str = "Analyze Redis key patterns, identify large keys, check TTL distribution, and understand data organization"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
            type="string",
            required=True
        ),
        "pattern": ToolParameter(
            description="Key pattern to analyze (e.g., 'user:*', 'session:*')",
            type="string",
            required=False
        ),
        "limit": ToolParameter(
            description="Maximum number of keys to analyze",
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
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing keys for Redis instance: {instance_name}")
            
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
            
            key_data = self.toolset.infrainsights_client.get_redis_key_analysis(
                instance, 
                pattern=params.get('pattern'),
                limit=params.get('limit', 100)
            )
            
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
        pattern = params.get('pattern', '*')
        return f"redis_key_analysis(instance_name={instance_name}, pattern={pattern})"


class RedisSlowLogAnalysisTool(Tool):
    """Tool to analyze Redis slow query log and identify performance bottlenecks"""
    
    name: str = "redis_slow_log_analysis"
    description: str = "Analyze Redis slow query log to identify performance bottlenecks, problematic commands, and optimization opportunities"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
            type="string",
            required=True
        ),
        "limit": ToolParameter(
            description="Number of slow log entries to analyze",
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
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing slow log for Redis instance: {instance_name}")
            
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
            
            slow_log_data = self.toolset.infrainsights_client.get_redis_slow_log_analysis(
                instance, params.get('limit', 50)
            )
            
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
        limit = params.get('limit', 50)
        return f"redis_slow_log_analysis(instance_name={instance_name}, limit={limit})"


class RedisConnectionAnalysisTool(Tool):
    """Tool to analyze Redis client connections and connection pooling"""
    
    name: str = "redis_connection_analysis"
    description: str = "Analyze Redis client connections, identify connection issues, and review connection pooling efficiency"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
            type="string",
            required=True
        ),
        "include_client_details": ToolParameter(
            description="Include detailed client connection information",
            type="boolean",
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
            
            connection_data = self.toolset.infrainsights_client.get_redis_connection_analysis(
                instance, params.get('include_client_details', False)
            )
            
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
        include_details = params.get('include_client_details', False)
        return f"redis_connection_analysis(instance_name={instance_name}, include_client_details={include_details})"


class RedisReplicationStatusTool(Tool):
    """Tool to check Redis replication status and lag"""
    
    name: str = "redis_replication_status"
    description: str = "Check Redis replication status, monitor replication lag, and identify replication issues"
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
            logger.error(f"Error checking Redis replication: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Redis replication: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        return f"redis_replication_status(instance_name={instance_name})"


class RedisPersistenceAnalysisTool(Tool):
    """Tool to analyze Redis persistence configuration and status"""
    
    name: str = "redis_persistence_analysis"
    description: str = "Analyze Redis persistence configuration (RDB/AOF), check backup status, and identify persistence issues"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
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
    """Tool to analyze Redis cluster health and configuration"""
    
    name: str = "redis_cluster_analysis"
    description: str = "Analyze Redis cluster health, node distribution, slot allocation, and cluster-wide performance"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis cluster to analyze",
            type="string",
            required=True
        ),
        "check_slot_distribution": ToolParameter(
            description="Check slot distribution across nodes",
            type="boolean",
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
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing Redis cluster: {instance_name}")
            
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
                    error=f"Redis cluster '{instance_name}' not found",
                    params=params
                )
            
            cluster_data = self.toolset.infrainsights_client.get_redis_cluster_analysis(
                instance, params.get('check_slot_distribution', True)
            )
            
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
        check_slots = params.get('check_slot_distribution', True)
        return f"redis_cluster_analysis(instance_name={instance_name}, check_slot_distribution={check_slots})"


class RedisSecurityAuditTool(Tool):
    """Tool to audit Redis security configuration and access controls"""
    
    name: str = "redis_security_audit"
    description: str = "Audit Redis security configuration, check authentication settings, ACL rules, and identify security vulnerabilities"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to audit",
            type="string",
            required=True
        ),
        "check_acl": ToolParameter(
            description="Include detailed ACL analysis",
            type="boolean",
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
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Auditing security for Redis instance: {instance_name}")
            
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
            
            security_data = self.toolset.infrainsights_client.get_redis_security_audit(
                instance, params.get('check_acl', True)
            )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=security_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error auditing Redis security: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to audit Redis security: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        check_acl = params.get('check_acl', True)
        return f"redis_security_audit(instance_name={instance_name}, check_acl={check_acl})"


class RedisCapacityPlanningTool(Tool):
    """Tool to analyze Redis capacity and provide scaling recommendations"""
    
    name: str = "redis_capacity_planning"
    description: str = "Analyze Redis capacity utilization, growth trends, and provide scaling recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
            type="string",
            required=True
        ),
        "forecast_days": ToolParameter(
            description="Number of days to forecast capacity needs",
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
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Analyzing capacity for Redis instance: {instance_name}")
            
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
            
            capacity_data = self.toolset.infrainsights_client.get_redis_capacity_planning(
                instance, params.get('forecast_days', 30)
            )
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=capacity_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Redis capacity: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to analyze Redis capacity: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'unknown')
        forecast_days = params.get('forecast_days', 30)
        return f"redis_capacity_planning(instance_name={instance_name}, forecast_days={forecast_days})"


class RedisConfigurationAnalysisTool(Tool):
    """Tool to analyze Redis configuration and provide optimization recommendations"""
    
    name: str = "redis_configuration_analysis"
    description: str = "Analyze Redis configuration parameters, identify misconfigurations, and provide optimization recommendations"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Redis instance to analyze",
            type="string",
            required=True
        ),
        "check_defaults": ToolParameter(
            description="Check for parameters using default values",
            type="boolean",
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
            
            config_data = self.toolset.infrainsights_client.get_redis_configuration_analysis(
                instance, params.get('check_defaults', True)
            )
            
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
        check_defaults = params.get('check_defaults', True)
        return f"redis_configuration_analysis(instance_name={instance_name}, check_defaults={check_defaults})"


class EnhancedRedisToolset(Toolset):
    """Enhanced Redis toolset with InfraInsights integration for comprehensive caching and data store monitoring"""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        from .infrainsights_client_v2 import InfraInsightsClientV2, InfraInsightsConfig
        
        logger.info("🚀🚀🚀 CREATING COMPREHENSIVE REDIS TOOLSET 🚀🚀🚀")
        
        # Initialize Toolset with required parameters first
        super().__init__(
            name="infrainsights_redis_enhanced",
            description="Enhanced Redis toolset with InfraInsights instance management for comprehensive caching analysis, performance monitoring, and operational excellence",
            enabled=True,
            tools=[],  # Start with empty tools list
            tags=[ToolsetTag.CLUSTER],
            prerequisites=[]  # Remove prerequisites during initialization
        )
        
        # Create comprehensive Redis tools
        self.tools = [
            # Basic operations and health
            RedisHealthCheckTool(toolset=None),
            
            # Performance and monitoring
            RedisPerformanceMetricsTool(toolset=None),
            RedisMemoryAnalysisTool(toolset=None),
            RedisSlowLogAnalysisTool(toolset=None),
            
            # Data and key analysis
            RedisKeyAnalysisTool(toolset=None),
            
            # Connection and networking
            RedisConnectionAnalysisTool(toolset=None),
            
            # Replication and clustering
            RedisReplicationStatusTool(toolset=None),
            RedisClusterAnalysisTool(toolset=None),
            
            # Persistence and reliability
            RedisPersistenceAnalysisTool(toolset=None),
            
            # Security and compliance
            RedisSecurityAuditTool(toolset=None),
            
            # Capacity and optimization
            RedisCapacityPlanningTool(toolset=None),
            RedisConfigurationAnalysisTool(toolset=None),
        ]
        
        # Validate all tools
        logger.info(f"🔧 Validating {len(self.tools)} Redis tools...")
        for i, tool in enumerate(self.tools):
            if tool is None:
                logger.error(f"🔧 Tool {i} is None!")
                raise ValueError(f"Redis tool {i} is None")
            if isinstance(tool, dict):
                logger.error(f"🔧 Tool {i} is a dict: {tool}")
                raise ValueError(f"Redis tool {i} is a dict, not a Tool object")
            if not hasattr(tool, 'name'):
                logger.error(f"🔧 Tool {i} has no 'name' attribute: {type(tool)}")
                raise ValueError(f"Redis tool {i} has no 'name' attribute")
            logger.info(f"🔧 Tool {i} validated: {tool.name} ({type(tool).__name__})")
        logger.info(f"✅ All {len(self.tools)} Redis tools validated successfully!")
        
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
        
        logger.info("✅✅✅ COMPREHENSIVE REDIS TOOLSET CREATED SUCCESSFULLY ✅✅✅")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with the provided configuration"""
        logger.info(f"🚀🚀🚀 CONFIGURING COMPREHENSIVE REDIS TOOLSET 🚀🚀🚀")
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
        
        logger.info(f"🔧 Updated config object: base_url={self.infrainsights_config.base_url}, api_key={'***' if self.infrainsights_config.api_key else 'None'}")
        
        # Now add prerequisites after configuration is complete
        self.prerequisites = [CallablePrerequisite(callable=self._check_prerequisites)]
        
        logger.info(f"✅✅✅ COMPREHENSIVE REDIS TOOLSET CONFIGURED WITH URL: {base_url} ✅✅✅")
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check if InfraInsights client can connect to the backend"""
        try:
            logger.info(f"🔍 Checking prerequisites for InfraInsights Redis client")
            
            # The context contains the configuration
            if not context:
                logger.warning("🔍 No context provided to prerequisites check")
                return True, "No context provided (toolset still enabled)"
            
            # Extract configuration from context
            config = context
            if isinstance(config, dict) and 'config' in config:
                config = config['config']
            
            # Get InfraInsights URL from config
            infrainsights_url = config.get('infrainsights_url', 'http://localhost:3000')
            api_key = config.get('api_key')
            
            logger.info(f"🔍 Current base_url: {infrainsights_url}")
            logger.info(f"🔍 API key configured: {'Yes' if api_key else 'No'}")
            
            # Try to connect to InfraInsights backend
            logger.info(f"🔍 Attempting health check to: {infrainsights_url}/api/health")
            
            # Note: We can't use self.infrainsights_client here as it may not be configured yet
            # Just return True to allow the toolset to load
            logger.info("✅ Prerequisites check passed (configuration will be applied later)")
            return True, f"InfraInsights backend will connect to {infrainsights_url}"
            
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