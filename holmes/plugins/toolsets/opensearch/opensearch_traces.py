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

TRACES_FIELDS_CACHE_KEY = "cached_traces_fields"

class OpenSearchTracesConfig(BaseModel):
    opensearch_traces_url: Union[str, None]
    opensearch_auth_header: Union[str, None]
    # Setting to None will disable the cache
    trace_fields_ttl_seconds: Union[int, None] = 14400  # 4 hours


class BaseOpenSearchTracesTool(Tool):
    toolset: "OpenSearchTracesToolset"


def add_auth_header(auth_header: Optional[str]) -> Dict[str, Any]:
    results = {}
    if auth_header:
        results["Authorization"] = auth_header
    return results

class GetTracesFields(BaseOpenSearchTracesTool):
    def __init__(self, toolset: "OpenSearchTracesToolset"):
        super().__init__(
            name="get_traces_fields",
            description="Get all the fields in the traces documents",
            parameters={},
            toolset=toolset,
        )
        self._cache = None

    def _invoke(self, params: Dict) -> str:
        try:
            if not self._cache:
                self._cache = TTLCache(maxsize=5, ttl=self.toolset.config.trace_fields_ttl_seconds)

            cached_response = self._cache.get(TRACES_FIELDS_CACHE_KEY, None)
            if cached_response :
                logging.debug("traces fields returned from cache")
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
                url=self.toolset.config.opensearch_traces_url, timeout=180, verify=True, data=json.dumps(body),
                headers=headers
            )
            logs_response.raise_for_status()
            response = json.dumps(logs_response.json())
            self._cache[TRACES_FIELDS_CACHE_KEY] = response
            return response
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch traces fields", exc_info=True)
            return "Request timed out while fetching opensearch traces fields"
        except RequestException as e:
            logging.warn("Failed to fetch opensearch traces fields", exc_info=True)
            return f"Network error while opensearch traces fields: {str(e)}"
        except Exception as e:
            logging.warn("Failed to process opensearch traces fields", exc_info=True)
            return f"Unexpected error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f'list traces documents fields'


class TracesSearchQuery(BaseOpenSearchTracesTool):
    def __init__(self, toolset: "OpenSearchTracesToolset"):
        super().__init__(
            name="traces_in_range_search",
            description="Get traces in a specified time range for an opensearch query",
            parameters={
                "query": ToolParameter(
                    description="An OpenSearch search query. It should be a stringified json, matching opensearch search syntax. "
                                "The query must contain a 'range' on the startTimeMillis field. From a given startTimeMillis, until a given startTimeMillis. This is time in milliseconds",
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
            full_query["size"] = int(os.environ.get("OPENSEARCH_TRACES_SEARCH_SIZE", "5000"))
            logging.debug(f"opensearch traces search query: {full_query}")
            headers = {
                "Content-Type": "application/json"
            }
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))

            logs_response = requests.get(
                url=self.toolset.config.opensearch_traces_url, timeout=180, verify=True, data=json.dumps(full_query),
                headers=headers
            )
            if logs_response.status_code > 300:
                err_msg = logs_response.text

            logs_response.raise_for_status()
            return json.dumps(logs_response.json())
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch traces search", exc_info=True)
            return f"Request timed out while fetching opensearch traces search {err_msg}"
        except RequestException as e:
            logging.warn("Failed to fetch opensearch traces search", exc_info=True)
            return f"Network error while opensearch traces search {err_msg} : {str(e)}"
        except Exception as e:
            logging.warn("Failed to process opensearch traces search ", exc_info=True)
            return f"Unexpected error {err_msg}: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f'search traces: query="{params.get("query")}"'


class OpenSearchTracesToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="opensearch/traces",
            description="OpenSearch integration to fetch traces",
            docs_url="",
            icon_url="",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetTracesFields(toolset=self),
                TracesSearchQuery(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
        )
        self._load_llm_instructions(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "opensearch_traces_instructions.jinja2")
            )
        )


    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config and not os.environ.get("OPENSEARCH_TRACES_URL", None):
            return False
        elif not config and os.environ.get("OPENSEARCH_TRACES_URL", None):
            self.config = OpenSearchTracesConfig(
                opensearch_traces_url=os.environ.get("OPENSEARCH_TRACES_URL"),
                opensearch_auth_header=os.environ.get("OPENSEARCH_LOGS_AUTH_HEADER", None),
            )
            return True
        else:
            self.config = OpenSearchTracesConfig(**config)
            return True
