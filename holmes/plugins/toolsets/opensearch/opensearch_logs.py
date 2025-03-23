import os
import logging

from typing import Any, Union, Optional, Dict

import requests
from cachetools import TTLCache
from pydantic import BaseModel
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
import json
from requests import RequestException

LOGS_FIELDS_CACHE_KEY = "cached_logs_fields"

class OpenSearchLogsConfig(BaseModel):
    opensearch_logs_url: Union[str, None]
    opensearch_auth_header: Union[str, None]
    # Setting to None will disable the cache
    logs_fields_ttl_seconds: Union[int, None] = 14400  # 4 hours


class BaseOpenSearchLogsTool(Tool):
    toolset: "OpenSearchLogsToolset"


def add_auth_header(auth_header: Optional[str]) -> Dict[str, Any]:
    results = {}
    if auth_header:
        results["Authorization"] = auth_header
    return results

class GetLogFields(BaseOpenSearchLogsTool):
    def __init__(self, toolset: "OpenSearchLogsToolset"):
        super().__init__(
            name="get_logs_fields",
            description="Get all the fields in the log documents",
            parameters={},
            toolset=toolset,
        )
        self._cache = None

    def _invoke(self, params: Dict) -> str:
        try:
            if not self._cache:
                self._cache = TTLCache(maxsize=5, ttl=self.toolset.config.logs_fields_ttl_seconds)

            cached_response = self._cache.get(LOGS_FIELDS_CACHE_KEY, None)
            if cached_response :
                logging.debug("logs fields returned from cache")
                return cached_response

            body = {
              "size": 1,
              "_source": False,
              "script_fields": {
                "all_fields": {
                  "script": {
                    "lang": "painless",
                    "source": "Map fields = new HashMap(); List stack = new ArrayList(); stack.add(['prefix': '', 'obj': params['_source']]); while (!stack.isEmpty()) { Map item = stack.remove(stack.size() - 1); String prefix = item.get('prefix'); Map obj = item.get('obj'); for (entry in obj.entrySet()) { String fullPath = prefix.isEmpty() ? entry.getKey() : prefix + '.' + entry.getKey(); fields.put(fullPath, true); if (entry.getValue() instanceof Map) { stack.add(['prefix': fullPath, 'obj': entry.getValue()]); } } } return fields.keySet();"
                  }
                }
              }
            }
            headers = {
                "Content-Type": "application/json"
            }
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))
            logs_response = requests.get(
                url=self.toolset.config.opensearch_logs_url, timeout=180, verify=True, data=json.dumps(body),
                headers=headers
            )
            logs_response.raise_for_status()
            response = json.dumps(logs_response.json())
            self._cache[LOGS_FIELDS_CACHE_KEY] = response
            return response
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch logs fields", exc_info=True)
            return "Request timed out while fetching opensearch logs fields"
        except RequestException as e:
            logging.warn("Failed to fetch opensearch logs fields", exc_info=True)
            return f"Network error while opensearch logs fields: {str(e)}"
        except Exception as e:
            logging.warn("Failed to process opensearch logs fields", exc_info=True)
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f'list log documents fields'


class LogsSearchQuery(BaseOpenSearchLogsTool):
    def __init__(self, toolset: "OpenSearchLogsToolset"):
        super().__init__(
            name="logs_in_range_search",
            description="Get logs in a specified time range for an opensearch query",
            parameters={
                "query": ToolParameter(
                    description="An OpenSearch search query. It should be a stringified json, matching opensearch search syntax. "
                                "The query must contain a 'range' on the @timestamp field. From a given timestamp, until a given timestamp",
                    type="string",
                ),
            },
            toolset=toolset,
        )
        self._cache = None

    def _invoke(self, params: Any) -> str:
        err_msg = ""
        try:
            body = json.loads(params.get("query"))
            full_query = body
            full_query["size"] = int(os.environ.get("OPENSEARCH_LOGS_SEARCH_SIZE", "5000"))
            logging.debug(f"opensearch logs search query: {full_query}")
            headers = {
                "Content-Type": "application/json"
            }
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))

            logs_response = requests.get(
                url=self.toolset.config.opensearch_logs_url, timeout=180, verify=True, data=json.dumps(full_query),
                headers=headers
            )
            if logs_response.status_code > 300:
                err_msg = logs_response.text

            logs_response.raise_for_status()
            return json.dumps(logs_response.json())
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch logs search", exc_info=True)
            return f"Request timed out while fetching opensearch logs search {err_msg}"
        except RequestException as e:
            logging.warn("Failed to fetch opensearch logs search", exc_info=True)
            return f"Network error while opensearch logs search {err_msg} {str(e)}"
        except Exception as e:
            logging.warn("Failed to process opensearch logs search", exc_info=True)
            return f"Unexpected error {err_msg}: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f'search logs: query="{params.get("query")}"'

class OpenSearchLogsToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="opensearch/logs",
            description="OpenSearch integration to fetch logs",
            docs_url="",
            icon_url="",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetLogFields(toolset=self),
                LogsSearchQuery(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config and not os.environ.get("OPENSEARCH_LOGS_URL", None):
            return False
        elif not config and os.environ.get("OPENSEARCH_LOGS_URL", None):
            self.config = OpenSearchLogsConfig(
                opensearch_logs_url=os.environ.get("OPENSEARCH_LOGS_URL"),
                opensearch_auth_header=os.environ.get("OPENSEARCH_LOGS_AUTH_HEADER", None),
            )
            return True
        else:
            self.config = OpenSearchLogsConfig(**config)
            return True
