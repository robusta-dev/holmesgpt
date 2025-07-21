"""
Elasticsearch Toolset for InfraInsights

Provides tools for investigating Elasticsearch clusters, indices, and documents
in the InfraInsights multi-instance architecture.
"""

import json
import logging
from typing import Dict, List, Optional, Any
import requests
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ApiError,
    ConnectionError,
    ConnectionTimeout,
    NotFoundError,
    RequestError,
    TransportError,
)

from holmes.core.tools import (
    StructuredToolResult,
    ToolParameter,
    ToolResultStatus,
)
from holmes.plugins.toolsets.utils import get_param_or_raise

from .base_toolset import BaseInfraInsightsTool, BaseInfraInsightsToolset


class ElasticsearchConnection:
    """Manages Elasticsearch connection with authentication"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Elasticsearch"""
        try:
            # Build connection parameters
            hosts = [self.config.get('host', 'localhost')]
            port = self.config.get('port', 9200)
            
            # Build URL
            protocol = 'https' if self.config.get('ssl', False) else 'http'
            url = f"{protocol}://{hosts[0]}:{port}"
            
            # Authentication
            auth = None
            if self.config.get('username') and self.config.get('password'):
                auth = (self.config['username'], self.config['password'])
            
            # SSL verification
            verify_certs = self.config.get('verify_certs', True)
            ca_certs = self.config.get('ca_certs')
            
            # Create client
            self.client = Elasticsearch(
                [url],
                basic_auth=auth,
                verify_certs=verify_certs,
                ca_certs=ca_certs,
                timeout=30
            )
            
            # Test connection
            if not self.client.ping():
                raise Exception("Failed to ping Elasticsearch cluster")
                
        except Exception as e:
            logging.error(f"Failed to connect to Elasticsearch: {e}")
            raise Exception(f"Elasticsearch connection failed: {e}")
    
    def get_client(self) -> Elasticsearch:
        """Get the Elasticsearch client"""
        if not self.client:
            self._connect()
        return self.client


class ListElasticsearchIndices(BaseInfraInsightsTool):
    """List all indices in the Elasticsearch cluster"""
    
    def __init__(self, toolset: "ElasticsearchToolset"):
        super().__init__(
            name="list_elasticsearch_indices",
            description="List all indices in the Elasticsearch cluster with their health, status, and document counts",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Elasticsearch instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Elasticsearch instance name to use",
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
            es_conn = ElasticsearchConnection(connection_config)
            client = es_conn.get_client()
            
            # Get cluster info
            cluster_info = client.info()
            
            # Get indices
            indices = client.cat.indices(format='json', v=True)
            
            # Format response
            result = {
                "cluster_name": cluster_info['cluster_name'],
                "elasticsearch_version": cluster_info['version']['number'],
                "indices": []
            }
            
            for index in indices:
                result["indices"].append({
                    "name": index['index'],
                    "health": index['health'],
                    "status": index['status'],
                    "docs_count": index['docs.count'],
                    "docs_deleted": index['docs.deleted'],
                    "store_size": index['store.size'],
                    "primary_size": index['pri.store.size']
                })
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list Elasticsearch indices: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"List Elasticsearch indices for instance: {instance_name}"


class GetElasticsearchClusterHealth(BaseInfraInsightsTool):
    """Get Elasticsearch cluster health information"""
    
    def __init__(self, toolset: "ElasticsearchToolset"):
        super().__init__(
            name="get_elasticsearch_cluster_health",
            description="Get detailed cluster health information including node status, shard allocation, and cluster state",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Elasticsearch instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Elasticsearch instance name to use",
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
            es_conn = ElasticsearchConnection(connection_config)
            client = es_conn.get_client()
            
            # Get cluster health
            health = client.cluster.health()
            
            # Get nodes info
            nodes = client.nodes.info()
            
            # Get cluster stats
            stats = client.cluster.stats()
            
            # Format response
            result = {
                "cluster_name": health['cluster_name'],
                "status": health['status'],
                "number_of_nodes": health['number_of_nodes'],
                "active_primary_shards": health['active_primary_shards'],
                "active_shards": health['active_shards'],
                "relocating_shards": health['relocating_shards'],
                "initializing_shards": health['initializing_shards'],
                "unassigned_shards": health['unassigned_shards'],
                "delayed_unassigned_shards": health.get('delayed_unassigned_shards', 0),
                "number_of_pending_tasks": health['number_of_pending_tasks'],
                "number_of_in_flight_fetch": health['number_of_in_flight_fetch'],
                "task_max_waiting_in_queue_millis": health['task_max_waiting_in_queue_millis'],
                "active_shards_percent_as_number": health['active_shards_percent_as_number'],
                "nodes": {
                    "total": len(nodes['nodes']),
                    "data": len([n for n in nodes['nodes'].values() if n.get('roles', [])]),
                    "master": len([n for n in nodes['nodes'].values() if 'master' in n.get('roles', [])]),
                    "ingest": len([n for n in nodes['nodes'].values() if 'ingest' in n.get('roles', [])])
                },
                "indices": {
                    "count": stats['indices']['count'],
                    "shards": stats['indices']['shards'],
                    "docs": stats['indices']['docs']
                }
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Elasticsearch cluster health: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"Get Elasticsearch cluster health for instance: {instance_name}"


class SearchElasticsearchDocuments(BaseInfraInsightsTool):
    """Search for documents in Elasticsearch indices"""
    
    def __init__(self, toolset: "ElasticsearchToolset"):
        super().__init__(
            name="search_elasticsearch_documents",
            description="Search for documents in Elasticsearch indices with custom queries",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Elasticsearch instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Elasticsearch instance name to use",
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
                "index_pattern": ToolParameter(
                    description="Index pattern to search in (e.g., 'logs-*', 'my-index')",
                    type="string",
                    required=True,
                ),
                "query": ToolParameter(
                    description="Elasticsearch query in JSON format",
                    type="string",
                    required=True,
                ),
                "size": ToolParameter(
                    description="Number of documents to return (default: 10)",
                    type="integer",
                    required=False,
                ),
                "sort": ToolParameter(
                    description="Sort field and order (e.g., '@timestamp:desc')",
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
            
            # Get parameters
            index_pattern = get_param_or_raise(params, "index_pattern")
            query_str = get_param_or_raise(params, "query")
            size = params.get("size", 10)
            sort = params.get("sort")
            
            # Parse query
            try:
                query = json.loads(query_str)
            except json.JSONDecodeError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Invalid JSON query format",
                    params=params,
                )
            
            # Create connection
            es_conn = ElasticsearchConnection(connection_config)
            client = es_conn.get_client()
            
            # Build search body
            search_body = {"query": query, "size": size}
            
            if sort:
                search_body["sort"] = sort
            
            # Execute search
            response = client.search(index=index_pattern, body=search_body)
            
            # Format response
            result = {
                "took": response['took'],
                "timed_out": response['timed_out'],
                "total_hits": response['hits']['total']['value'],
                "max_score": response['hits']['max_score'],
                "documents": []
            }
            
            for hit in response['hits']['hits']:
                result["documents"].append({
                    "index": hit['_index'],
                    "id": hit['_id'],
                    "score": hit['_score'],
                    "source": hit['_source']
                })
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to search Elasticsearch documents: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        index_pattern = params.get('index_pattern', 'unknown')
        return f"Search Elasticsearch documents in {index_pattern} for instance: {instance_name}"


class GetElasticsearchIndexMapping(BaseInfraInsightsTool):
    """Get mapping information for Elasticsearch indices"""
    
    def __init__(self, toolset: "ElasticsearchToolset"):
        super().__init__(
            name="get_elasticsearch_index_mapping",
            description="Get mapping information for Elasticsearch indices including field types and properties",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific Elasticsearch instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific Elasticsearch instance name to use",
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
                "index_name": ToolParameter(
                    description="Name of the index to get mapping for",
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
            index_name = get_param_or_raise(params, "index_name")
            
            # Create connection
            es_conn = ElasticsearchConnection(connection_config)
            client = es_conn.get_client()
            
            # Get mapping
            mapping = client.indices.get_mapping(index=index_name)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(mapping, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get Elasticsearch index mapping: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        index_name = params.get('index_name', 'unknown')
        return f"Get Elasticsearch mapping for index {index_name} in instance: {instance_name}"


class ElasticsearchToolset(BaseInfraInsightsToolset):
    """Elasticsearch toolset for InfraInsights"""
    
    def __init__(self):
        super().__init__()
        
        # Set tools after parent initialization
        self.tools = [
            ListElasticsearchIndices(self),
            GetElasticsearchClusterHealth(self),
            SearchElasticsearchDocuments(self),
            GetElasticsearchIndexMapping(self),
        ]
    
    def get_service_type(self) -> str:
        return "elasticsearch"
    
    def get_llm_instructions(self) -> str:
        return """
        This toolset provides tools for investigating Elasticsearch clusters managed by InfraInsights.
        
        Available tools:
        - list_elasticsearch_indices: List all indices with health and document counts
        - get_elasticsearch_cluster_health: Get detailed cluster health information
        - search_elasticsearch_documents: Search for documents with custom queries
        - get_elasticsearch_index_mapping: Get field mappings for indices
        
        When investigating Elasticsearch issues:
        1. Start with cluster health to understand overall status
        2. List indices to identify problematic ones
        3. Use search to find specific documents or patterns
        4. Check mappings to understand data structure
        
        The toolset automatically handles:
        - Multi-instance support (production, staging, etc.)
        - Authentication and connection management
        - User context and access control
        """ 