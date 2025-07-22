"""
Generic Elasticsearch Toolset for HolmesGPT

This toolset reads connection details from environment variables set by the InfraInsights plugin
and provides Elasticsearch investigation capabilities without direct InfraInsights coupling.
"""

import os
import json
import logging
from typing import Dict, Any
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, AuthenticationException, NotFoundError

from holmes.core.tools import StructuredTool, StructuredToolResult, ToolResultStatus
from holmes.plugins.infrainsights_plugin import resolve_instance_for_toolset
from holmes.plugins.smart_router import parse_prompt_for_routing

logger = logging.getLogger(__name__)

class BaseElasticsearchTool(StructuredTool):
    """Base class for generic Elasticsearch tools"""
    
    def _get_elasticsearch_client(self) -> Elasticsearch:
        """Create Elasticsearch client from environment variables"""
        
        # Get connection details from environment (set by InfraInsights plugin)
        url = os.getenv('ELASTICSEARCH_URL')
        username = os.getenv('ELASTICSEARCH_USERNAME')
        password = os.getenv('ELASTICSEARCH_PASSWORD')
        api_key = os.getenv('ELASTICSEARCH_API_KEY')
        
        if not url:
            raise Exception("Elasticsearch connection not configured. No ELASTICSEARCH_URL environment variable found.")
        
        # Set up authentication
        auth = None
        if api_key:
            auth = {'api_key': api_key}
        elif username and password:
            auth = (username, password)
        
        # Create client
        try:
            client = Elasticsearch(
                [url],
                auth=auth,
                verify_certs=False,  # For development environments
                timeout=30,
                retry_on_timeout=True,
                max_retries=3
            )
            
            # Test connection
            if not client.ping():
                raise Exception("Failed to connect to Elasticsearch cluster")
            
            return client
            
        except Exception as e:
            raise Exception(f"Failed to create Elasticsearch client: {str(e)}")
    
    def _get_instance_info(self) -> Dict[str, str]:
        """Get information about the current instance"""
        return {
            "name": os.getenv('CURRENT_INSTANCE_NAME', 'unknown'),
            "environment": os.getenv('CURRENT_INSTANCE_ENVIRONMENT', 'unknown'),
            "id": os.getenv('CURRENT_INSTANCE_ID', 'unknown'),
            "url": os.getenv('ELASTICSEARCH_URL', 'unknown')
        }
    
    def _ensure_instance_resolved(self, params: Dict[str, Any], prompt: str = "") -> bool:
        """
        Ensure that an Elasticsearch instance is resolved and configured.
        
        Args:
            params: Tool parameters (may contain instance hints)
            prompt: Original user prompt for context
            
        Returns:
            bool: True if instance is resolved, False otherwise
        """
        # Check if we already have a configured instance
        if os.getenv('ELASTICSEARCH_URL'):
            return True
        
        # Try to resolve instance from parameters or prompt
        instance_hint = (
            params.get('instance_name') or 
            params.get('instance_id') or
            params.get('cluster_name')
        )
        
        # If no explicit hint, try to extract from prompt
        if not instance_hint and prompt:
            route_info = parse_prompt_for_routing(prompt)
            if route_info.instance_hint:
                instance_hint = route_info.instance_hint
        
        # If still no hint, use a default
        if not instance_hint:
            instance_hint = "default"
        
        # Resolve the instance
        result = resolve_instance_for_toolset('elasticsearch', instance_hint, params.get('user_id'))
        
        if not result.success:
            logger.error(f"Failed to resolve Elasticsearch instance: {result.error_message}")
            return False
        
        logger.info(f"✅ Resolved Elasticsearch instance: {result.instance.name}")
        return True

class ElasticsearchHealthTool(BaseElasticsearchTool):
    """Generic Elasticsearch cluster health check tool"""
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_info = self._get_instance_info()
        return f"Get Elasticsearch cluster health for instance: {instance_info['name']}"
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        """Get Elasticsearch cluster health"""
        try:
            # Ensure instance is resolved
            if not self._ensure_instance_resolved(params, params.get('prompt', '')):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not resolve Elasticsearch instance. Please specify instance name or check InfraInsights configuration.",
                    params=params
                )
            
            # Get instance info for response
            instance_info = self._get_instance_info()
            
            # Create Elasticsearch client
            es = self._get_elasticsearch_client()
            
            # Get cluster health
            health = es.cluster.health()
            
            # Get additional cluster info
            stats = es.cluster.stats()
            
            result = {
                "instance": {
                    "name": instance_info['name'],
                    "environment": instance_info['environment'],
                    "url": instance_info['url']
                },
                "cluster_health": {
                    "cluster_name": health.get("cluster_name"),
                    "status": health.get("status"),
                    "timed_out": health.get("timed_out"),
                    "number_of_nodes": health.get("number_of_nodes"),
                    "number_of_data_nodes": health.get("number_of_data_nodes"),
                    "active_primary_shards": health.get("active_primary_shards"),
                    "active_shards": health.get("active_shards"),
                    "relocating_shards": health.get("relocating_shards"),
                    "initializing_shards": health.get("initializing_shards"),
                    "unassigned_shards": health.get("unassigned_shards")
                },
                "cluster_stats": {
                    "total_indices": stats['indices']['count'],
                    "total_docs": stats['indices']['docs']['count'],
                    "total_size_bytes": stats['indices']['store']['size_in_bytes'],
                    "total_size_human": self._bytes_to_human(stats['indices']['store']['size_in_bytes'])
                }
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except ConnectionError as e:
            error_msg = f"Failed to connect to Elasticsearch: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"{error_msg}\n\nPlease check:\n1. Elasticsearch instance is running\n2. Connection URL is correct\n3. Network connectivity",
                params=params
            )
            
        except AuthenticationException as e:
            error_msg = f"Elasticsearch authentication failed: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"{error_msg}\n\nPlease check:\n1. Username/password are correct\n2. API key is valid\n3. User has necessary permissions",
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to get Elasticsearch cluster health: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params
            )
    
    def _bytes_to_human(self, bytes_count: int) -> str:
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} PB"

class ElasticsearchIndicesTool(BaseElasticsearchTool):
    """Generic Elasticsearch indices listing tool"""
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_info = self._get_instance_info()
        return f"List Elasticsearch indices for instance: {instance_info['name']}"
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        """List Elasticsearch indices"""
        try:
            # Ensure instance is resolved
            if not self._ensure_instance_resolved(params, params.get('prompt', '')):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not resolve Elasticsearch instance. Please specify instance name or check InfraInsights configuration.",
                    params=params
                )
            
            # Get instance info for response
            instance_info = self._get_instance_info()
            
            # Create Elasticsearch client
            es = self._get_elasticsearch_client()
            
            # Get indices information
            indices = es.cat.indices(format='json', h='index,status,health,pri,rep,docs.count,store.size')
            
            # Sort by index name
            indices = sorted(indices, key=lambda x: x.get('index', ''))
            
            # Process indices data
            processed_indices = []
            for idx in indices:
                processed_indices.append({
                    "name": idx.get("index"),
                    "status": idx.get("status"),
                    "health": idx.get("health"),
                    "primary_shards": idx.get("pri"),
                    "replica_shards": idx.get("rep"),
                    "docs_count": idx.get("docs.count", "0"),
                    "store_size": idx.get("store.size", "0b")
                })
            
            result = {
                "instance": {
                    "name": instance_info['name'],
                    "environment": instance_info['environment'],
                    "url": instance_info['url']
                },
                "total_indices": len(processed_indices),
                "indices": processed_indices
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to list Elasticsearch indices: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params
            )

class ElasticsearchSearchTool(BaseElasticsearchTool):
    """Generic Elasticsearch document search tool"""
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_info = self._get_instance_info()
        index = params.get('index', 'all indices')
        query = params.get('query', 'match_all')
        return f"Search Elasticsearch {index} with query '{query}' on instance: {instance_info['name']}"
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        """Search Elasticsearch documents"""
        try:
            # Ensure instance is resolved
            if not self._ensure_instance_resolved(params, params.get('prompt', '')):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not resolve Elasticsearch instance. Please specify instance name or check InfraInsights configuration.",
                    params=params
                )
            
            # Get parameters
            index = params.get('index', '_all')
            query = params.get('query', '*')
            size = min(int(params.get('size', 10)), 100)  # Limit to 100 results
            
            # Get instance info for response
            instance_info = self._get_instance_info()
            
            # Create Elasticsearch client
            es = self._get_elasticsearch_client()
            
            # Build search query
            if query == '*' or query == 'match_all':
                search_query = {"match_all": {}}
            else:
                # Simple query string search
                search_query = {"query_string": {"query": query}}
            
            # Execute search
            response = es.search(
                index=index,
                body={
                    "query": search_query,
                    "size": size,
                    "sort": [{"_score": {"order": "desc"}}]
                }
            )
            
            # Process results
            hits = response.get('hits', {})
            documents = []
            
            for hit in hits.get('hits', []):
                documents.append({
                    "index": hit.get('_index'),
                    "id": hit.get('_id'),
                    "score": hit.get('_score'),
                    "source": hit.get('_source', {})
                })
            
            result = {
                "instance": {
                    "name": instance_info['name'],
                    "environment": instance_info['environment'],
                    "url": instance_info['url']
                },
                "search_info": {
                    "index": index,
                    "query": query,
                    "total_hits": hits.get('total', {}).get('value', 0),
                    "max_score": hits.get('max_score'),
                    "took_ms": response.get('took')
                },
                "documents": documents
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except NotFoundError as e:
            error_msg = f"Index not found: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"{error_msg}\n\nPlease check that the index exists and try again.",
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to search Elasticsearch documents: {str(e)}"
            logger.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params
            )

# Tool registration for HolmesGPT
ELASTICSEARCH_TOOLS = [
    ElasticsearchHealthTool(),
    ElasticsearchIndicesTool(),
    ElasticsearchSearchTool()
]

def get_elasticsearch_tools():
    """Get all generic Elasticsearch tools"""
    return ELASTICSEARCH_TOOLS 