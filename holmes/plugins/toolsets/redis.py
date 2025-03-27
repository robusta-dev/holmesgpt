import os
import json
import logging
from typing import Any, Dict, List, Optional, Union

import redis
from pydantic import ConfigDict
from holmes.core.tools import Tool, ToolParameter, Toolset, ToolsetTag
from datetime import datetime

class BaseRedisTool(Tool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    toolset: "RedisToolset"

    def _get_client(self, db: Optional[int] = None) -> redis.Redis:  # Add optional db parameter
        """Helper function to get a Redis client, handling authentication and database selection."""
        redis_url = os.getenv("REDIS_URL", self.toolset.config.get("redis_url"))
        password = os.getenv("REDIS_PASSWORD", self.toolset.config.get("password"))

        # Use the provided db, or get from config, or default to 0
        selected_db = db if db is not None else int(os.getenv("REDIS_DB", self.toolset.config.get("db", 0)))

        if not redis_url:
            raise ValueError("Config must provide 'redis_url'.")

        try:
            if "redis://" in redis_url or "rediss://" in redis_url:
                client = redis.from_url(redis_url, db=selected_db, password=password)  # Use selected_db
            else:
                host, port_str = redis_url.split(":")
                port = int(port_str)
                client = redis.Redis(host=host, port=port, db=selected_db, password=password) # Use selected_db

            client.ping()
            return client
        except redis.exceptions.ConnectionError as e:
            logging.exception("Failed to connect to Redis")
            raise ConnectionError(f"Could not connect to Redis: {e}")
        except Exception as e:
            logging.exception(f"An unexpected error occurred: {e}")
            raise

class RedisInfo(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_info",
            description="""Retrieves information and statistics about the Redis server.
                           This is similar to the INFO command in redis-cli.  Returns a dictionary
                           of various server stats.  You can OPTIONALLY specify the 'db' parameter
                           to get information about a specific database.
                        """,
            parameters={
                "db": ToolParameter(
                    description="The database number to get info for (e.g., 0, 1, 2).  If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        db = params.get("db")  # Get the db from parameters, if provided
        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            info = client.info()
            for section, section_data in info.items():
                if isinstance(section_data, dict):
                    for key, value in section_data.items():
                        if isinstance(value, (bytes, int, float)):
                            info[section][key] = str(value)

            return json.dumps(info, indent=2)
        except Exception as e:
            logging.exception("Failed to get Redis info")
            return f"Error getting Redis info: {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f"db={params.get('db')}"
        return f"redis_info({db_str})"


class RedisGet(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_get",
            description="""Retrieves the value of a key from Redis. You MUST provide the 'key' parameter.
                           You can OPTIONALLY specify the 'db' parameter.
                        """,
            parameters={
                "key": ToolParameter(
                    description="The key to retrieve from Redis. This is REQUIRED.",
                    type="string",
                    required=True,
                ),
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        key = params["key"]
        db = params.get("db")
        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            value = client.get(key)
            if value is None:
                return f"Key '{key}' not found in Redis."
            return value.decode('utf-8')
        except Exception as e:
            logging.exception(f"Failed to get key '{key}' from Redis")
            return f"Error getting key '{key}': {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f", db={params.get('db')}"
        return f"redis_get(key='{params.get('key')}'{db_str})"

class RedisKeys(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_keys",
            description="""Retrieves keys matching a pattern from Redis.
                           You MUST provide the 'pattern' parameter.  Use * as a wildcard.
                           For example, 'user:*' will return all keys starting with 'user:'.
                           Be careful with broad patterns like '*' on large databases.
                           You can OPTIONALLY specify the 'db' parameter.
                        """,
            parameters={
                "pattern": ToolParameter(
                    description="The pattern to match keys against (e.g., 'user:*', 'session:*', '*'). This is REQUIRED.",
                    type="string",
                    required=True,
                ),
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        pattern = params["pattern"]
        db = params.get("db")
        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            keys = client.keys(pattern)
            decoded_keys = [key.decode('utf-8') for key in keys]
            return json.dumps(decoded_keys, indent=2)

        except Exception as e:
            logging.exception(f"Failed to get keys matching pattern '{pattern}' from Redis")
            return f"Error getting keys with pattern '{pattern}': {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f", db={params.get('db')}"
        return f"redis_keys(pattern='{params.get('pattern')}'{db_str})"

class RedisLLen(BaseRedisTool):
     def __init__(self, toolset: "RedisToolset"):
         super().__init__(
             name="redis_llen",
             description="""Retrieves the length of a list stored at the specified key.
                            You MUST provide the key parameter. You can OPTIONALLY specify the 'db' parameter.
                         """,
            parameters={
                "key": ToolParameter(
                    description = "The key of the list to measure length for.",
                    type="string",
                    required = True
                ),
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset
         )

     def _invoke(self, params: Dict[str, Any]) -> str:
         key = params["key"]
         db = params.get("db")
         try:
             client = self._get_client(db=db) # Pass db to _get_client
             list_length = client.llen(key)
             return str(list_length)

         except Exception as e:
             logging.exception(f"Failed to retrieve list length for key '{key}'")
             return f"Error retrieving list length for key '{key}' {e}"

     def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f", db={params.get('db')}"
        return f"redis_llen(key='{params.get('key')}'{db_str})"

class RedisLRange(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_lrange",
            description = """Retrieves a range of elements from a list stored at the specified key.
                           You must provide the 'key', 'start', and 'end' parameters. You can OPTIONALLY specify the 'db' parameter.
                        """,
            parameters = {
                "key": ToolParameter(
                    description = "The key of the list to retrieve elements from",
                    type = "string",
                    required=True
                ),
                "start": ToolParameter(
                    description = "The start index of the range (inclusive, 0-based).",
                    type="integer",
                    required=True
                ),
                 "end": ToolParameter(
                    description = "The end index of the range (inclusive). Use -1 to get all elements to the end of the list.",
                    type="integer",
                    required=True
                ),
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        key = params["key"]
        start = params["start"]
        end = params["end"]
        db = params.get("db")

        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            list_elements = client.lrange(key, start, end)
            decoded_elements = [element.decode('utf-8') for element in list_elements]
            return json.dumps(decoded_elements, indent=2)
        except Exception as e:
            logging.exception(f"Failed to retrieve list elements for '{key}'")
            return f"Error retrieving elements from list '{key}': {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f", db={params.get('db')}"
        return f"redis_lrange(key='{params.get('key')}', start={params.get('start')}, end={params.get('end')}{db_str})"

class RedisMemoryUsage(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_memory_usage",
            description="""Retrieves the memory usage of the Redis server.  Returns the 'used_memory_human'
                           value from the INFO command. You can OPTIONALLY specify the 'db' parameter.
                        """,
            parameters={
                 "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        db = params.get("db")
        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            memory_info = client.info("memory")
            return memory_info["used_memory_human"]
        except Exception as e:
            logging.exception("Failed to get Redis memory usage")
            return f"Error getting Redis memory usage: {e}"
    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f"db={params.get('db')}"
        return f"redis_memory_usage({db_str})"

class RedisSlowlogGet(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_slowlog_get",
            description="""Retrieves the Redis slowlog. You can OPTIONALLY specify the number of
                           entries to retrieve using the 'count' parameter (defaults to 10).
                           You can also OPTIONALLY specify the 'db' parameter.
                        """,
            parameters={
                "count": ToolParameter(
                    description="The number of slowlog entries to retrieve. Defaults to 10.",
                    type="integer",
                    required=False,
                    default=10,
                ),
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        count = params.get("count", 10)
        db = params.get("db")
        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            slowlog = client.slowlog_get(count)
            formatted_slowlog = []
            for entry in slowlog:
                formatted_entry = {
                    "id": entry["id"],
                    "start_time": datetime.fromtimestamp(entry["start_time"]).isoformat(),
                    "duration_ms": entry["duration"] / 1000,
                    "command": entry["command"].decode('utf-8', errors='replace'),
                }
                formatted_slowlog.append(formatted_entry)

            return json.dumps(formatted_slowlog, indent=2)
        except Exception as e:
            logging.exception("Failed to get Redis slowlog")
            return f"Error getting Redis slowlog: {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        count_str = "" if params.get("count") is None else f"count={params.get('count')}"
        db_str = "" if params.get("db") is None else f", db={params.get('db')}"
        return f"redis_slowlog_get({count_str}{db_str})"

class RedisClientCount(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_client_count",
            description="""Retrieves number of client connections. You can OPTIONALLY specify the 'db' parameter.""",
            parameters = {
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                )
            },
            toolset=toolset
        )
    def _invoke(self, params: Dict[str, Any]) -> str:
        db = params.get("db")
        try:
            client = self._get_client(db=db) # Pass db to _get_client
            connected_clients = client.info("clients")["connected_clients"]
            return str(connected_clients)
        except Exception as e:
            logging.exception("Failed to get Redis client count")
            return f"Error getting Redis client count: {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f"db={params.get('db')}"
        return f"redis_client_count({db_str})"

class RedisLatencyLatest(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_latency_latest",
            description="""Retrieves the latest latency samples for various Redis events.
                           Returns a dictionary where keys are event names and values are lists of
                           [timestamp, latency_ms] pairs. You can OPTIONALLY specify the 'db' parameter.
                        """,
            parameters={
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                )
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        db = params.get("db")
        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            latency_data = client.latency_latest()
            formatted = {}
            for entry in latency_data:
                event = entry['event']
                formatted[event] = [
                    datetime.fromtimestamp(entry['time']).isoformat(),
                    entry['latency']
                ]
            return json.dumps(formatted, indent=2)

        except Exception as e:
             logging.exception("Failed to get Redis latest latency")
             return f"Error getting Redis latest latency: {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f"db={params.get('db')}"
        return f"redis_latency_latest({db_str})"
class RedisKeyspaceInfo(BaseRedisTool):
    def __init__(self, toolset: "RedisToolset"):
        super().__init__(
            name="redis_keyspace_info",
            description="""Retrieves information about the keyspace, including the number of keys,
                           average TTL, and keys with expiration set. You can OPTIONALLY specify the 'db' parameter.
                        """,
            parameters={
                "db": ToolParameter(
                    description="The database number (e.g., 0, 1, 2). If not specified, defaults to the toolset's configured db or 0.",
                    type="integer",
                    required=False,
                )
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        db = params.get("db")
        try:
            client = self._get_client(db=db)  # Pass db to _get_client
            keyspace_info = client.info("keyspace")
            # Filter and format relevant keyspace information
            formatted_info = {}
            for key, value in keyspace_info.items():
                # Check if the key represents a database (e.g., 'db0', 'db1')
                if key.startswith("db"):
                  try:
                    # Convert comma-separated string to a dictionary
                      parts = value.split(',')
                      db_info = {}
                      for part in parts:
                          k, v = part.split('=')
                          db_info[k] = int(v)  # Convert values to integers
                      formatted_info[key] = db_info
                  except:
                      formatted_info[key] = value #keep the original in case parsing failed.

            return json.dumps(formatted_info, indent=2, default=str)
        except Exception as e:
            logging.exception("Failed to get Redis keyspace info")
            return f"Error getting keyspace info: {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        db_str = "" if params.get("db") is None else f"db={params.get('db')}"
        return f"redis_keyspace_info({db_str})"

class RedisToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: Dict[str, Any] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="redis",
            description="Toolset to interact with a Redis database.",
            docs_url="https://redis.io/documentation",  # Official Redis docs
            icon_url="https://redis.io/static/images/redis-logo.svg",  # Redis logo
            prerequisites=[],
            tools=[
                RedisInfo(self),
                RedisGet(self),
                RedisKeys(self),
                RedisLLen(self),
                RedisLRange(self),
                RedisMemoryUsage(self),
                RedisSlowlogGet(self),
                RedisClientCount(self),
                RedisLatencyLatest(self),
                RedisKeyspaceInfo(self)
            ],
            tags=[ToolsetTag.CORE],
            is_default=False,
        )
        if config:
            self.config = config

    def prerequisites_callable(self, config: Dict[str, Any]) -> bool:
        return bool(config.get("redis_url"))

    def get_example_config(self) -> Dict[str, Any]:
        return {
            "redis_url": "localhost:6379",  # Default Redis URL
            "password": "your_redis_password",  # Optional password
            "db": 0,  # Optional database number
        }
