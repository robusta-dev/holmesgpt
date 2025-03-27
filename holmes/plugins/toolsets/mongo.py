import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pymongo
from pydantic import BaseModel, ConfigDict, Field
from holmes.core.tools import (
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
)


class BaseMongoTool(Tool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    toolset: "MongoToolset"

    def _get_client(self) -> pymongo.MongoClient:
        """Helper function to get a MongoDB client, handling authentication."""
        mongo_url = os.getenv("MONGO_URL", self.toolset.config.get("mongo_url"))
        username = os.getenv("MONGO_USERNAME", self.toolset.config.get("username"))
        password = os.getenv("MONGO_PASSWORD", self.toolset.config.get("password"))

        if not mongo_url:
            raise ValueError("Config must provide 'mongo_url'.")

        if username and password:
            client = pymongo.MongoClient(
                f"mongodb://{username}:{password}@{mongo_url}"
            )
        else:
            client = pymongo.MongoClient(mongo_url)

        return client


class FetchDBStats(BaseMongoTool):
    def __init__(self, toolset: "MongoToolset"):
        super().__init__(
            name="mongo_fetch_db_stats",
            description="""Fetch statistics for a specific MongoDB database.
                           You MUST provide the 'database_name'.
                           Use this to get an overview of a database's size, number of collections, etc.""",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the MongoDB database (e.g., 'admin', 'config', 'my_app_db'). This is REQUIRED.",
                    type="string",
                    required=True,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        client = self._get_client()
        db_name = params["database_name"]
        try:
            db = client[db_name]
            stats = db.command("dbStats")
            return json.dumps(stats, indent=2, default=str)
        except Exception as e:
            logging.exception(f"Failed to fetch stats for database {db_name}")
            return f"Error fetching database stats: {e}"
        finally:
            client.close()

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"mongo_fetch_db_stats(database_name='{params.get('database_name')}')"


class FetchCollectionStats(BaseMongoTool):
    def __init__(self, toolset: "MongoToolset"):
        super().__init__(
            name="mongo_fetch_collection_stats",
            description="""Fetch statistics for a *specific* collection within a MongoDB database.
                           You MUST provide BOTH 'database_name' and 'collection_name'.
                           Use this to get details about a single collection, like its size, document count, etc.""",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the MongoDB database (e.g., 'my_app_db'). This is REQUIRED.",
                    type="string",
                    required=True,
                ),
                "collection_name": ToolParameter(
                    description="The name of the collection within the database (e.g., 'users', 'products'). This is REQUIRED.",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        client = self._get_client()
        db_name = params["database_name"]
        collection_name = params["collection_name"]
        try:
            db = client[db_name]
            stats = db.command("collStats", collection_name)
            return json.dumps(stats, indent=2, default=str)
        except Exception as e:
            logging.exception(
                f"Failed to fetch stats for collection {collection_name} in database {db_name}"
            )
            return f"Error fetching collection stats: {e}"
        finally:
            client.close()

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return (
            f"mongo_fetch_collection_stats(database_name='{params.get('database_name')}', "
            f"collection_name='{params.get('collection_name')}')"
        )


class FetchServerStatus(BaseMongoTool):
    def __init__(self, toolset: "MongoToolset"):
        super().__init__(
            name="mongo_fetch_server_status",
            description="""Fetch the server status of the MongoDB instance.  This provides overall server information,
                           like uptime, version, connection details, and memory usage.  It does NOT require any parameters.""",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        client = self._get_client()
        try:
            status = client.admin.command("serverStatus")
            return json.dumps(status, indent=2, default=str)
        except Exception as e:
            logging.exception("Failed to fetch server status")
            return f"Error fetching server status: {e}"
        finally:
            client.close()

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "mongo_fetch_server_status()"


class FetchSlowLogs(BaseMongoTool):
    def __init__(self, toolset: "MongoToolset"):
        super().__init__(
            name="mongo_fetch_slow_logs",
            description="""Fetch slow query logs from the MongoDB profiler for a specific database.
                           You MUST provide the 'database_name'.
                           You can OPTIONALLY provide 'threshold_ms' (default 100ms), 'limit' (default 10), 'start_time', and 'end_time'.
                           Use this to identify slow-running queries that might be causing performance problems.""",
            parameters={
                "database_name": ToolParameter(
                    description="The name of the MongoDB database. This is REQUIRED.",
                    type="string",
                    required=True,
                ),
                "threshold_ms": ToolParameter(
                    description="The minimum query execution time (in milliseconds) to be considered 'slow'.  Defaults to 100ms.",
                    type="integer",
                    required=False,
                    default=100,
                ),
                "limit": ToolParameter(
                    description="The maximum number of slow logs to return. Defaults to 10.",
                    type="integer",
                    required=False,
                    default=10,
                ),
                "start_time": ToolParameter(
                    description="The start time for the query (ISO 8601 format, e.g., '2023-10-27T10:00:00Z').",
                    type="string",
                    required=False,
                ),
                "end_time": ToolParameter(
                    description="The end time for the query (ISO 8601 format).",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        client = self._get_client()
        db_name = params["database_name"]
        threshold_ms = params.get("threshold_ms", 100)
        limit = params.get("limit", 10)
        start_time_str = params.get("start_time")
        end_time_str = params.get("end_time")

        try:
            db = client[db_name]

            query_filter: Dict[str, Any] = {"millis": {"$gte": threshold_ms}}

            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    query_filter["ts"] = {"$gte": start_time}
                except ValueError:
                    return "Error: Invalid start_time format.  Use ISO 8601 (e.g., '2023-10-27T10:00:00Z')."
            if end_time_str:
                try:
                    end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    if "ts" in query_filter:
                        query_filter["ts"]["$lte"] = end_time
                    else:
                        query_filter["ts"] = {"$lte": end_time}
                except ValueError:
                    return "Error: Invalid end_time format.  Use ISO 8601 (e.g., '2023-10-27T10:00:00Z')."

            slow_logs = list(
                db.system.profile.find(query_filter).sort([("millis", pymongo.DESCENDING)]).limit(limit)
            )
            return json.dumps(slow_logs, indent=2, default=str)

        except Exception as e:
            logging.exception(f"Failed to fetch slow logs for database {db_name}")
            return f"Error fetching slow logs: {e}"
        finally:
            client.close()

    def get_parameterized_one_liner(self, params: Dict) -> str:
        parts = [f"database_name='{params.get('database_name')}'"]
        if params.get("threshold_ms") is not None:
            parts.append(f"threshold_ms={params.get('threshold_ms')}")
        if params.get("limit") is not None:
            parts.append(f"limit={params.get('limit')}")
        if params.get("start_time") is not None:
            parts.append(f"start_time='{params.get('start_time')}'")
        if params.get("end_time") is not None:
            parts.append(f"end_time='{params.get('end_time')}'")

        return f"mongo_fetch_slow_logs({', '.join(parts)})"


class MongoToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: Dict[str, Any] = {}  # Initialize config

    def __init__(self, config: Optional[Dict[str, Any]] = None):  # Accept a config
        super().__init__(
            name="mongodb",
            description="Toolset to query MongoDB for database and collection stats, server status, and slow logs.",
            docs_url="https://www.mongodb.com/docs/",
            icon_url="https://www.mongodb.com/assets/images/mongodb-logo.png",
            prerequisites=[],
            tools=[
                FetchDBStats(self),
                FetchCollectionStats(self),
                FetchServerStatus(self),
                FetchSlowLogs(self),
            ],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )
        if config:
            self.config = config # Set the config if provided

    def prerequisites_callable(self, config: Dict[str, Any]) -> bool:
        return bool(config.get("mongo_url"))

    def get_example_config(self) -> Dict[str, Any]:
        return {
            "mongo_url": "your-mongodb-host:27017",
            "username": "your_username",
            "password": "your_password",
        }
