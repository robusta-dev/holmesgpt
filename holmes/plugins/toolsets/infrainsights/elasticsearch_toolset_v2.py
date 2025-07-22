import json
import logging
from typing import Dict, Any

from holmes.core.tools import StructuredToolResult, ToolResultStatus
from .base_toolset_v2 import BaseInfraInsightsToolV2, BaseInfraInsightsToolsetV2

logger = logging.getLogger(__name__)

class ElasticsearchHealthToolV2(BaseInfraInsightsToolV2):
    """Tool to check Elasticsearch cluster health with V2 API support"""
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        try:
            # Get service instance using enhanced resolution
            instance = self.get_instance_from_params(params)
            
            # Get connection configuration
            config = self.get_connection_config(instance)
            
            # Extract Elasticsearch connection details
            es_url = config.get('elasticsearchUrl', config.get('elasticsearch_url'))
            username = config.get('username')
            password = config.get('password')
            api_key = config.get('apiKey', config.get('api_key'))
            
            if not es_url:
                raise Exception("Elasticsearch URL not found in instance configuration")
            
            # Import and configure Elasticsearch client
            try:
                from elasticsearch import Elasticsearch
            except ImportError:
                raise Exception("Elasticsearch client library not available")
            
            # Configure authentication
            auth_config = {}
            if api_key:
                auth_config['api_key'] = api_key
            elif username and password:
                auth_config['http_auth'] = (username, password)
            
            # Create Elasticsearch client
            es = Elasticsearch(
                [es_url],
                verify_certs=False,
                timeout=30,
                **auth_config
            )
            
            # Get cluster health
            health = es.cluster.health()
            
            # Get cluster stats for additional information
            try:
                stats = es.cluster.stats()
                nodes_info = es.nodes.info()
            except Exception as e:
                logger.warning(f"Failed to get additional cluster info: {e}")
                stats = {}
                nodes_info = {}
            
            result = {
                "elasticsearch_cluster": {
                    "instance_name": instance.name,
                    "instance_id": instance.instanceId,
                    "environment": instance.environment,
                    "elasticsearch_url": es_url
                },
                "cluster_health": health,
                "cluster_stats": stats,
                "nodes_info": nodes_info,
                "resolution_info": {
                    "resolved_by": "V2 API with name lookup",
                    "instance_found": True,
                    "name_lookup_enabled": self.get_infrainsights_client().config.enable_name_lookup
                },
                "timestamp": "2025-01-22T10:15:00Z"
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to get Elasticsearch cluster health: {str(e)}"
            logger.error(error_msg)
            
            # Provide helpful error message
            helpful_msg = self.get_helpful_error_message(error_msg)
            
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=helpful_msg,
                params=params
            )

class ElasticsearchIndicesToolV2(BaseInfraInsightsToolV2):
    """Tool to list Elasticsearch indices with V2 API support"""
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        try:
            # Get service instance using enhanced resolution
            instance = self.get_instance_from_params(params)
            
            # Get connection configuration
            config = self.get_connection_config(instance)
            
            # Extract Elasticsearch connection details
            es_url = config.get('elasticsearchUrl', config.get('elasticsearch_url'))
            username = config.get('username')
            password = config.get('password')
            api_key = config.get('apiKey', config.get('api_key'))
            
            if not es_url:
                raise Exception("Elasticsearch URL not found in instance configuration")
            
            # Import and configure Elasticsearch client
            try:
                from elasticsearch import Elasticsearch
            except ImportError:
                raise Exception("Elasticsearch client library not available")
            
            # Configure authentication
            auth_config = {}
            if api_key:
                auth_config['api_key'] = api_key
            elif username and password:
                auth_config['http_auth'] = (username, password)
            
            # Create Elasticsearch client
            es = Elasticsearch(
                [es_url],
                verify_certs=False,
                timeout=30,
                **auth_config
            )
            
            # Get indices information
            indices = es.cat.indices(format='json', v=True)
            
            # Get additional index stats
            try:
                index_stats = es.indices.stats()
            except Exception as e:
                logger.warning(f"Failed to get index stats: {e}")
                index_stats = {}
            
            result = {
                "elasticsearch_cluster": {
                    "instance_name": instance.name,
                    "instance_id": instance.instanceId,
                    "environment": instance.environment,
                    "elasticsearch_url": es_url
                },
                "indices": {
                    "total_count": len(indices),
                    "indices_list": indices,
                    "indices_stats": index_stats
                },
                "resolution_info": {
                    "resolved_by": "V2 API with name lookup",
                    "instance_found": True,
                    "name_lookup_enabled": self.get_infrainsights_client().config.enable_name_lookup
                },
                "timestamp": "2025-01-22T10:15:00Z"
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to list Elasticsearch indices: {str(e)}"
            logger.error(error_msg)
            
            # Provide helpful error message
            helpful_msg = self.get_helpful_error_message(error_msg)
            
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=helpful_msg,
                params=params
            )

class ElasticsearchSearchToolV2(BaseInfraInsightsToolV2):
    """Tool to search Elasticsearch documents with V2 API support"""
    
    def run(self, params: Dict[str, Any]) -> StructuredToolResult:
        try:
            # Get service instance using enhanced resolution
            instance = self.get_instance_from_params(params)
            
            # Get connection configuration
            config = self.get_connection_config(instance)
            
            # Extract Elasticsearch connection details
            es_url = config.get('elasticsearchUrl', config.get('elasticsearch_url'))
            username = config.get('username')
            password = config.get('password')
            api_key = config.get('apiKey', config.get('api_key'))
            
            if not es_url:
                raise Exception("Elasticsearch URL not found in instance configuration")
            
            # Get search parameters
            index = params.get('index', '_all')
            query = params.get('query', {"match_all": {}})
            size = params.get('size', 10)
            
            # Import and configure Elasticsearch client
            try:
                from elasticsearch import Elasticsearch
            except ImportError:
                raise Exception("Elasticsearch client library not available")
            
            # Configure authentication
            auth_config = {}
            if api_key:
                auth_config['api_key'] = api_key
            elif username and password:
                auth_config['http_auth'] = (username, password)
            
            # Create Elasticsearch client
            es = Elasticsearch(
                [es_url],
                verify_certs=False,
                timeout=30,
                **auth_config
            )
            
            # Perform search
            search_result = es.search(
                index=index,
                body={"query": query, "size": size}
            )
            
            result = {
                "elasticsearch_cluster": {
                    "instance_name": instance.name,
                    "instance_id": instance.instanceId,
                    "environment": instance.environment,
                    "elasticsearch_url": es_url
                },
                "search_result": search_result,
                "search_parameters": {
                    "index": index,
                    "query": query,
                    "size": size
                },
                "resolution_info": {
                    "resolved_by": "V2 API with name lookup",
                    "instance_found": True,
                    "name_lookup_enabled": self.get_infrainsights_client().config.enable_name_lookup
                },
                "timestamp": "2025-01-22T10:15:00Z"
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params
            )
            
        except Exception as e:
            error_msg = f"Failed to search Elasticsearch: {str(e)}"
            logger.error(error_msg)
            
            # Provide helpful error message
            helpful_msg = self.get_helpful_error_message(error_msg)
            
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=helpful_msg,
                params=params
            )

class ElasticsearchToolsetV2(BaseInfraInsightsToolsetV2):
    """Elasticsearch toolset with V2 API support for name-based instance resolution"""
    
    def __init__(self):
        super().__init__("InfraInsights Elasticsearch V2")
        
        self.tools = [
            ElasticsearchHealthToolV2(self),
            ElasticsearchIndicesToolV2(self),
            ElasticsearchSearchToolV2(self)
        ]
    
    def get_service_type(self) -> str:
        return "elasticsearch" 