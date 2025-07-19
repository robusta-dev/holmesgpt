"""
MongoDB Toolset for InfraInsights

Provides tools for investigating MongoDB databases, collections, and documents
in the InfraInsights multi-instance architecture.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from holmes.core.tools import (
    StructuredToolResult,
    ToolParameter,
    ToolResultStatus,
)
from holmes.plugins.toolsets.utils import get_param_or_raise

from .base_toolset import BaseInfraInsightsTool, BaseInfraInsightsToolset


class MongoDBConnection:
    """Manages MongoDB connection with authentication"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to MongoDB"""
        try:
            # Build connection string
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 27017)
            database = self.config.get('database', 'admin')
            
            # Build connection string
            if self.config.get('username') and self.config.get('password'):
                connection_string = f"mongodb://{self.config['username']}:{self.config['password']}@{host}:{port}/{database}"
            else:
                connection_string = f"mongodb://{host}:{port}/{database}"
            
            # Add SSL options
            if self.config.get('ssl', False):
                connection_string += "?ssl=true"
                if self.config.get('ssl_ca_certs'):
                    connection_string += f"&ssl_ca_certs={self.config['ssl_ca_certs']}"
            
            # Create client
            self.client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
            
            # Test connection
            self.client.admin.command('ping')
            
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise Exception(f"MongoDB connection failed: {e}")
    
    def get_client(self) -> MongoClient:
        """Get the MongoDB client"""
        if not self.client:
            self._connect()
        return self.client


class ListMongoDBDatabases(BaseInfraInsightsTool):
    """List all databases in MongoDB"""
    
    def __init__(self, toolset: "MongoDBToolset"):
        super().__init__(
            name="list_mongodb_databases",
            description="List all databases in MongoDB with their sizes and collection counts",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific MongoDB instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific MongoDB instance name to use",
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
            mongo_conn = MongoDBConnection(connection_config)
            client = mongo_conn.get_client()
            
            # Get database list
            databases = client.list_database_names()
            
            # Get database stats
            result = {
                "databases": []
            }
            
            for db_name in databases:
                if db_name not in ['admin', 'local', 'config']:  # Skip system databases
                    try:
                        db = client[db_name]
                        stats = db.command('dbStats')
                        
                        result["databases"].append({
                            "name": db_name,
                            "collections": stats.get('collections', 0),
                            "views": stats.get('views', 0),
                            "objects": stats.get('objects', 0),
                            "avg_obj_size": stats.get('avgObjSize', 0),
                            "data_size": stats.get('dataSize', 0),
                            "storage_size": stats.get('storageSize', 0),
                            "indexes": stats.get('indexes', 0),
                            "index_size": stats.get('indexSize', 0)
                        })
                    except PyMongoError:
                        # Skip databases we can't access
                        continue
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list MongoDB databases: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"List MongoDB databases for instance: {instance_name}"


class ListMongoDBCollections(BaseInfraInsightsTool):
    """List collections in a MongoDB database"""
    
    def __init__(self, toolset: "MongoDBToolset"):
        super().__init__(
            name="list_mongodb_collections",
            description="List all collections in a MongoDB database with their document counts and sizes",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific MongoDB instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific MongoDB instance name to use",
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
                "database_name": ToolParameter(
                    description="Name of the database to list collections from",
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
            database_name = get_param_or_raise(params, "database_name")
            
            # Create connection
            mongo_conn = MongoDBConnection(connection_config)
            client = mongo_conn.get_client()
            
            # Get database
            db = client[database_name]
            
            # Get collections
            collections = db.list_collection_names()
            
            # Get collection stats
            result = {
                "database": database_name,
                "collections": []
            }
            
            for collection_name in collections:
                try:
                    collection = db[collection_name]
                    stats = db.command('collStats', collection_name)
                    
                    result["collections"].append({
                        "name": collection_name,
                        "count": stats.get('count', 0),
                        "size": stats.get('size', 0),
                        "avg_obj_size": stats.get('avgObjSize', 0),
                        "storage_size": stats.get('storageSize', 0),
                        "indexes": stats.get('nindexes', 0),
                        "index_size": stats.get('totalIndexSize', 0)
                    })
                except PyMongoError:
                    # Skip collections we can't access
                    continue
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to list MongoDB collections: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        database_name = params.get('database_name', 'unknown')
        return f"List MongoDB collections in database {database_name} for instance: {instance_name}"


class SearchMongoDBDocuments(BaseInfraInsightsTool):
    """Search for documents in MongoDB collections"""
    
    def __init__(self, toolset: "MongoDBToolset"):
        super().__init__(
            name="search_mongodb_documents",
            description="Search for documents in MongoDB collections with custom queries",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific MongoDB instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific MongoDB instance name to use",
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
                "database_name": ToolParameter(
                    description="Name of the database to search in",
                    type="string",
                    required=True,
                ),
                "collection_name": ToolParameter(
                    description="Name of the collection to search in",
                    type="string",
                    required=True,
                ),
                "query": ToolParameter(
                    description="MongoDB query in JSON format",
                    type="string",
                    required=True,
                ),
                "limit": ToolParameter(
                    description="Maximum number of documents to return (default: 10)",
                    type="integer",
                    required=False,
                ),
                "sort": ToolParameter(
                    description="Sort criteria in JSON format (e.g., '{\"_id\": -1}')",
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
            database_name = get_param_or_raise(params, "database_name")
            collection_name = get_param_or_raise(params, "collection_name")
            query_str = get_param_or_raise(params, "query")
            limit = params.get("limit", 10)
            sort_str = params.get("sort")
            
            # Parse query
            try:
                query = json.loads(query_str)
            except json.JSONDecodeError:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Invalid JSON query format",
                    params=params,
                )
            
            # Parse sort
            sort = None
            if sort_str:
                try:
                    sort = json.loads(sort_str)
                except json.JSONDecodeError:
                    return StructuredToolResult(
                        status=ToolResultStatus.ERROR,
                        error="Invalid JSON sort format",
                        params=params,
                    )
            
            # Create connection
            mongo_conn = MongoDBConnection(connection_config)
            client = mongo_conn.get_client()
            
            # Get collection
            collection = client[database_name][collection_name]
            
            # Execute query
            cursor = collection.find(query, limit=limit)
            if sort:
                cursor = cursor.sort(sort)
            
            # Convert cursor to list
            documents = list(cursor)
            
            # Convert ObjectId to string for JSON serialization
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
            
            # Format response
            result = {
                "database": database_name,
                "collection": collection_name,
                "query": query,
                "total_found": len(documents),
                "documents": documents
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to search MongoDB documents: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        database_name = params.get('database_name', 'unknown')
        collection_name = params.get('collection_name', 'unknown')
        return f"Search MongoDB documents in {database_name}.{collection_name} for instance: {instance_name}"


class GetMongoDBServerStatus(BaseInfraInsightsTool):
    """Get MongoDB server status and performance metrics"""
    
    def __init__(self, toolset: "MongoDBToolset"):
        super().__init__(
            name="get_mongodb_server_status",
            description="Get MongoDB server status including performance metrics, connections, and operations",
            parameters={
                "instance_id": ToolParameter(
                    description="Specific MongoDB instance ID to use",
                    type="string",
                    required=False,
                ),
                "instance_name": ToolParameter(
                    description="Specific MongoDB instance name to use",
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
            mongo_conn = MongoDBConnection(connection_config)
            client = mongo_conn.get_client()
            
            # Get server status
            status = client.admin.command('serverStatus')
            
            # Format response
            result = {
                "host": status.get('host'),
                "version": status.get('version'),
                "uptime": status.get('uptime'),
                "connections": status.get('connections', {}),
                "opcounters": status.get('opcounters', {}),
                "opcountersRepl": status.get('opcountersRepl', {}),
                "mem": status.get('mem', {}),
                "extra_info": status.get('extra_info', {}),
                "metrics": status.get('metrics', {})
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"Failed to get MongoDB server status: {str(e)}"
            logging.error(error_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        instance_name = params.get('instance_name', 'default')
        return f"Get MongoDB server status for instance: {instance_name}"


class MongoDBToolset(BaseInfraInsightsToolset):
    """MongoDB toolset for InfraInsights"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.name = "InfraInsights MongoDB"
        self.description = "Tools for investigating MongoDB databases, collections, and documents in InfraInsights"
        self.tags = [ToolsetTag.CLUSTER]
        self.enabled = True
        
        # Initialize tools
        self.tools = [
            ListMongoDBDatabases(self),
            ListMongoDBCollections(self),
            SearchMongoDBDocuments(self),
            GetMongoDBServerStatus(self),
        ]
    
    def get_service_type(self) -> str:
        return "mongodb"
    
    def get_llm_instructions(self) -> str:
        return """
        This toolset provides tools for investigating MongoDB databases managed by InfraInsights.
        
        Available tools:
        - list_mongodb_databases: List all databases with sizes and collection counts
        - list_mongodb_collections: List collections in a database with document counts
        - search_mongodb_documents: Search for documents with custom queries
        - get_mongodb_server_status: Get server performance metrics and status
        
        When investigating MongoDB issues:
        1. Start with server status to understand performance and connections
        2. List databases to understand the data structure
        3. List collections to identify problematic ones
        4. Search documents to find specific data or patterns
        
        The toolset automatically handles:
        - Multi-instance support (production, staging, etc.)
        - Authentication and connection management
        - User context and access control
        """ 