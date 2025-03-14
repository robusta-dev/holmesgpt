import os
import re
import logging
import random
import string
import time

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

from urllib.parse import urljoin

LOGS_FIELDS_CACHE_KEY = "cached_logs_fields"

class OpenSearchConfig(BaseModel):
    opensearch_url: Union[str, None]
    opensearch_auth_header: Union[str, None]
    # Setting to None will disable the cache
    logs_fields_ttl_seconds: Union[int, None] = 14400  # 4 hours


class BaseOpenSearchLogsTool(Tool):
    toolset: "OpenSearchLogsToolset"


def generate_random_key():
    return "".join(random.choices(string.ascii_letters + string.digits, k=4))


def result_has_data(result: dict) -> bool:
    data = result.get("data", {})
    if len(data.get("result", [])) > 0:
        return True
    return False

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
                logging.info("### logs fields returned from cache")
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
            logs_url = urljoin(self.toolset.config.opensearch_url, "/freshservice/_search")
            headers = {
                "Content-Type": "application/json"
            }
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))
            logs_response = requests.get(
                url=logs_url, timeout=180, verify=True, data=json.dumps(body),
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


class GetPodLogs(BaseOpenSearchLogsTool):
    def __init__(self, toolset: "OpenSearchLogsToolset"):
        super().__init__(
            name="get_pod_logs_in_range",
            description="Get pod logs in a specified time range",
            parameters={
                "pod": ToolParameter(
                    description="Pod name. Get the logs of this pod",
                    type="string",
                ),
                "from": ToolParameter(
                    description="From timestamp in zulu format (For example: '2025-02-22T22:00:00.000Z'). Get logs starting at this time",
                    type="string",
                ),
                "to": ToolParameter(
                    description="To timestamp in zulu format (For example: '2025-02-22T22:00:00.000Z'). Get logs until at this time",
                    type="string",
                ),
            },
            toolset=toolset,
        )
        self._cache = None

    def _invoke(self, params: Any) -> str:
        try:
            logs_url = urljoin(self.toolset.config.opensearch_url, "/freshservice/_search")
            body = {
              "query": {
                "bool": {
                  "must": [
                    {
                        "range": {
                          "@timestamp": {
                            "gte": params.get("from"),
                            "lte": params.get("to"),
                            "format": "strict_date_optional_time"
                          }
                        }
                    },
                    {
                      "term": {
                        "kubernetes.pod.name.keyword": params.get("pod")
                      }
                    }
                  ]
                }
              }
            }
            headers = {
                "Content-Type": "application/json"
            }
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))

            logs_response = requests.get(
                url=logs_url, timeout=180, verify=True, data=json.dumps(body),
                headers=headers
            )
            logs_response.raise_for_status()
            return json.dumps(logs_response.json())
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch logs", exc_info=True)
            return "Request timed out while fetching rules"
        except RequestException as e:
            logging.warn("Failed to fetch opensearch logs", exc_info=True)
            return f"Network error while opensearch logs: {str(e)}"
        except Exception as e:
            logging.warn("Failed to process opensearch logs", exc_info=True)
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f'get pod logs: pod="{params.get("pod")}", from="{params.get("from")}, to="{params.get("to")}"'

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
        try:
            logs_url = urljoin(self.toolset.config.opensearch_url, "/freshservice/_search")
            body = json.loads(params.get("query"))
            full_query = body
            full_query["size"] = int(os.environ.get("OS_LOGS_SEARCH_SIZE", "5000"))
            # full_query = {
            #     "query": body,
            #     "size": int(os.environ.get("OS_LOGS_SEARCH_SIZE", "5000"))
            # }
            logging.info(f"os logs search query: {full_query}")
            headers = {
                "Content-Type": "application/json"
            }
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))

            logs_response = requests.get(
                url=logs_url, timeout=180, verify=True, data=json.dumps(full_query),
                headers=headers
            )
            logs_response.raise_for_status()
            return json.dumps(logs_response.json())
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch logs search", exc_info=True)
            return "Request timed out while fetching opensearch logs search"
        except RequestException as e:
            logging.warn("Failed to fetch opensearch logs search", exc_info=True)
            return f"Network error while opensearch logs search: {str(e)}"
        except Exception as e:
            logging.warn("Failed to process opensearch logs search", exc_info=True)
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return (f'search logs: query="{params.get("query")}"')


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
        if not config and not os.environ.get("OS_LOGS_URL", None):
            return False
        elif not config and os.environ.get("OS_LOGS_URL", None):
            self.config = OpenSearchConfig(
                opensearch_url=os.environ.get("OS_LOGS_URL"),
                opensearch_auth_header=os.environ.get("OS_LOGS_AUTH_HEADER", None),
            )
            return True
        else:
            self.config = OpenSearchConfig(**config)
            return True
