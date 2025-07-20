"""
Redis Toolset for InfraInsights

Provides tools for investigating Redis instances, keys, and performance
in the InfraInsights multi-instance architecture.
"""

import json
import logging
from typing import Dict, List, Optional, Any
import redis
from redis.exceptions import RedisError

from holmes.core.tools import (
    StructuredToolResult,
    ToolParameter,
    ToolResultStatus,
)
from holmes.plugins.toolsets.utils import get_param_or_raise

from .base_toolset import BaseInfraInsightsTool, BaseInfraInsightsToolset


class RedisConnection:
    """Manages Redis connection with authentication"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Redis"""
        try:
            # Build connection parameters
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 6379)
            password = self.config.get('password')
            db = self.config.get('db', 0)
            
            # SSL configuration
            ssl = self.config.get('ssl', False)
            ssl_cert_reqs = self.config.get('ssl_cert_reqs', 'required')
            
            # Create client
            self.client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                ssl=ssl,
                ssl_cert_reqs=ssl_cert_reqs,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Test connection
            self.client.ping()
            
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise Exception(f"Redis connection failed: {e}")
    
    def get_client(self) -> redis.Redis:
        """Get the Redis client"""
        if not self.client:
            self._connect()
        return self.client


class GetRedisInfo(BaseInfraInsightsTool):
    """Get Redis server information and statistics"""
    
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="get_redis_info",
            description="Get Redis server information including memory usage, connected clients, and performance metrics",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Redis instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Redis instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Create connection
            redis_conn = RedisConnection(connection_config)
            client = redis_conn.get_client()
            
            # Get Redis info
            info = client.info()
            
            # Format response
            result = {
                "server": {
                    "redis_version": info.get('redis_version'),
                    "redis_mode": info.get('redis_mode'),
                    "os": info.get('os'),
                    "arch_bits": info.get('arch_bits'),
                    "uptime_in_seconds": info.get('uptime_in_seconds'),
                    "uptime_in_days": info.get('uptime_in_days')
                },
                "clients": {
                    "connected_clients": info.get('connected_clients'),
                    "blocked_clients": info.get('blocked_clients'),
                    "max_clients": info.get('maxclients')
                },
                "memory": {
                    "used_memory": info.get('used_memory'),
                    "used_memory_human": info.get('used_memory_human'),
                    "used_memory_peak": info.get('used_memory_peak'),
                    "used_memory_peak_human": info.get('used_memory_peak_human'),
                    "used_memory_rss": info.get('used_memory_rss'),
                    "used_memory_rss_human": info.get('used_memory_rss_human'),
                    "mem_fragmentation_ratio": info.get('mem_fragmentation_ratio')
                },
                "stats": {
                    "total_commands_processed": info.get('total_commands_processed'),
                    "total_connections_received": info.get('total_connections_received'),
                    "total_net_input_bytes": info.get('total_net_input_bytes'),
                    "total_net_output_bytes": info.get('total_net_output_bytes'),
                    "instantaneous_ops_per_sec": info.get('instantaneous_ops_per_sec'),
                    "instantaneous_input_kbps": info.get('instantaneous_input_kbps'),
                    "instantaneous_output_kbps": info.get('instantaneous_output_kbps')
                },
                "keyspace": info.get('db0', {})
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Redis info: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"Get Redis info for instance: {instance_name}"


class ListRedisKeys(BaseInfraInsightsTool):
    """List keys in Redis with pattern matching"""
    
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="list_redis_keys",
            description="List Redis keys matching a pattern with their types and TTL information",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Redis instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Redis instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
                "pattern": ToolParameter(
                    description="Key pattern to match (e.g., 'user:*', '*session*')",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of keys to return (default: 100)",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Get parameters
            pattern = params.get('pattern', '*')
            limit = params.get('limit', 100)
            
            # Create connection
            redis_conn = RedisConnection(connection_config)
            client = redis_conn.get_client()
            
            # Get keys
            keys = client.keys(pattern)
            
            # Limit results
            if len(keys) > limit:
                keys = keys[:limit]
            
            # Get key information
            result = {
                "pattern": pattern,
                "total_keys": len(keys),
                "keys": []
            }
            
            for key in keys:
                try:
                    key_type = client.type(key)
                    ttl = client.ttl(key)
                    
                    result["keys"].append({
                        "key": key,
                        "type": key_type,
                        "ttl": ttl if ttl > 0 else None,
                        "size": self._get_key_size(client, key, key_type)
                    })
                except RedisError:
                    # Skip keys we can't access
                    continue
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list Redis keys: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def _get_key_size(self, client: redis.Redis, key: str, key_type: str) -> Optional[int]:
        """Get the size of a Redis key"""
        try:
            if key_type == 'string':
                return client.strlen(key)
            elif key_type == 'list':
                return client.llen(key)
            elif key_type == 'set':
                return client.scard(key)
            elif key_type == 'hash':
                return client.hlen(key)
            elif key_type == 'zset':
                return client.zcard(key)
            else:
                return None
        except RedisError:
            return None
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        pattern = params.get('pattern', '*')
        return f"List Redis keys matching '{pattern}' for instance: {instance_name}"


class GetRedisKeyValue(BaseInfraInsightsTool):
    """Get the value of a specific Redis key"""
    
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="get_redis_key_value",
            description="Get the value and metadata of a specific Redis key",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Redis instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Redis instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
                "key": ToolParameter(
                    description="Redis key to get value for",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Get parameters
            key = get_param_or_raise(params, "key")
            
            # Create connection
            redis_conn = RedisConnection(connection_config)
            client = redis_conn.get_client()
            
            # Check if key exists
            if not client.exists(key):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Key '{key}' does not exist",
                    params=params,
                )
            
            # Get key information
            key_type = client.type(key)
            ttl = client.ttl(key)
            
            # Get value based on type
            value = self._get_key_value(client, key, key_type)
            
            # Format response
            result = {
                "key": key,
                "type": key_type,
                "ttl": ttl if ttl > 0 else None,
                "value": value
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Redis key value: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def _get_key_value(self, client: redis.Redis, key: str, key_type: str) -> Any:
        """Get the value of a Redis key based on its type"""
        try:
            if key_type == 'string':
                return client.get(key)
            elif key_type == 'list':
                return client.lrange(key, 0, -1)
            elif key_type == 'set':
                return list(client.smembers(key))
            elif key_type == 'hash':
                return client.hgetall(key)
            elif key_type == 'zset':
                return client.zrange(key, 0, -1, withscores=True)
            else:
                return None
        except RedisError:
            return None
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        key = params.get('key', 'unknown')
        return f"Get Redis key value for '{key}' in instance: {instance_name}"


class GetRedisMemoryUsage(BaseInfraInsightsTool):
    """Get detailed Redis memory usage information"""
    
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="get_redis_memory_usage",
            description="Get detailed Redis memory usage including memory breakdown by data type",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Redis instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Redis instance name to use",
                    type="string",
                    required=False,
                ),
                "user_id": ToolParameter(
                    description="User ID for context-aware instance selection",
                    type="string",
                    required=False,
                ),
                "prompt": ToolParameter(
                    description="User prompt to help identify the correct instance",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get the appropriate instance
            instance = self.get_instance_from_params(params)
            connection_config = self.get_connection_config(instance)
            
            # Create connection
            redis_conn = RedisConnection(connection_config)
            client = redis_conn.get_client()
            
            # Get memory info
            memory_info = client.memory('usage')
            
            # Get additional memory stats
            info = client.info('memory')
            
            # Format response
            result = {
                "memory_usage": memory_info,
                "memory_stats": {
                    "used_memory": info.get('used_memory'),
                    "used_memory_human": info.get('used_memory_human'),
                    "used_memory_peak": info.get('used_memory_peak'),
                    "used_memory_peak_human": info.get('used_memory_peak_human'),
                    "used_memory_rss": info.get('used_memory_rss'),
                    "used_memory_rss_human": info.get('used_memory_rss_human'),
                    "mem_fragmentation_ratio": info.get('mem_fragmentation_ratio'),
                    "mem_allocator": info.get('mem_allocator')
                }
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Redis memory usage: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"Get Redis memory usage for instance: {instance_name}"


class RedisToolset(BaseInfraInsightsToolset):
    """Redis toolset for InfraInsights"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Set tools after parent initialization
        self.tools = [
            GetRedisInfo(self),
            ListRedisKeys(self),
            GetRedisKeyValue(self),
            GetRedisMemoryUsage(self),
        ]
    
    def get_service_type(self) -> str:
        return "redis"
    
    def get_llm_instructions(self) -> str:
        return """
        This toolset provides tools for investigating Redis instances managed by InfraInsights.
        
        Available tools:
        - get_redis_info: Get server information and performance metrics
        - list_redis_keys: List keys with pattern matching and metadata
        - get_redis_key_value: Get value and metadata of specific keys
        - get_redis_memory_usage: Get detailed memory usage information
        
        When investigating Redis issues:
        1. Start with server info to understand performance and connections
        2. Check memory usage to identify memory pressure
        3. List keys to understand data patterns
        4. Get specific key values to investigate data issues
        
        The toolset automatically handles:
        - Multi-instance support (production, staging, etc.)
        - Authentication and connection management
        - User context and access control
        """ 