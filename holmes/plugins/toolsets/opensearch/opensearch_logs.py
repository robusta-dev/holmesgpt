import os
import logging

from typing import Any, Dict, Tuple

import requests
from cachetools import TTLCache
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

from holmes.plugins.toolsets.opensearch.opensearch_utils import (
    opensearch_health_check,
    add_auth_header,
    OpenSearchIndexConfig,
)
from holmes.core.tools import StructuredToolResult, ToolResultStatus

LOGS_FIELDS_CACHE_KEY = "cached_logs_fields"


class BaseOpenSearchLogsTool(Tool):
    toolset: "OpenSearchLogsToolset"


class GetLogFields(BaseOpenSearchLogsTool):
    def __init__(self, toolset: "OpenSearchLogsToolset"):
        super().__init__(
            name="get_logs_fields",
            description="Get all the fields in the log documents",
            parameters={},
            toolset=toolset,
        )
        self._cache = None

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            if not self._cache:
                self._cache = TTLCache(
                    maxsize=5, ttl=self.toolset.config.fields_ttl_seconds
                )

            cached_response = self._cache.get(LOGS_FIELDS_CACHE_KEY, None)
            if cached_response:
                logging.debug("logs fields returned from cache")
                return cached_response

            body = {
                "size": 1,
                "_source": False,
                "script_fields": {
                    "all_fields": {
                        "script": {
                            "lang": "painless",
                            "source": "Map fields = new HashMap(); List stack = new ArrayList(); stack.add(['prefix': '', 'obj': params['_source']]); while (!stack.isEmpty()) { Map item = stack.remove(stack.size() - 1); String prefix = item.get('prefix'); Map obj = item.get('obj'); for (entry in obj.entrySet()) { String fullPath = prefix.isEmpty() ? entry.getKey() : prefix + '.' + entry.getKey(); fields.put(fullPath, true); if (entry.getValue() instanceof Map) { stack.add(['prefix': fullPath, 'obj': entry.getValue()]); } } } return fields.keySet();",
                        }
                    }
                },
            }
            headers = {"Content-Type": "application/json"}
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))
            url = urljoin(
                self.toolset.config.opensearch_url,
                f"/{self.toolset.config.index_name}/_search",
            )
            logs_response = requests.get(
                url=url,
                timeout=180,
                verify=True,
                data=json.dumps(body),
                headers=headers,
            )
            logs_response.raise_for_status()
            response = json.dumps(logs_response.json())
            self._cache[LOGS_FIELDS_CACHE_KEY] = response
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=response,
                return_code=0,
                params=params,
            )
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch logs fields", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                return_code=-1,
                error="Request timed out while fetching opensearch logs fields",
            )
        except RequestException as e:
            logging.warn("Failed to fetch opensearch logs fields", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                return_code=-1,
                error=f"Network error while opensearch logs fields: {str(e)}",
            )
        except Exception as e:
            logging.warn("Failed to process opensearch logs fields", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error: {str(e)}",
                return_code=-1,
            )

    def get_parameterized_one_liner(self, params) -> str:
        return "list log documents fields"


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

    def _invoke(self, params: Any) -> StructuredToolResult:
        err_msg = ""
        try:
            body = json.loads(params.get("query"))
            full_query = body
            full_query["size"] = int(
                os.environ.get("OPENSEARCH_LOGS_SEARCH_SIZE", "5000")
            )
            logging.debug(f"opensearch logs search query: {full_query}")
            headers = {"Content-Type": "application/json"}
            headers.update(add_auth_header(self.toolset.config.opensearch_auth_header))
            url = urljoin(
                self.toolset.config.opensearch_url,
                f"/{self.toolset.config.index_name}/_search",
            )
            logs_response = requests.get(
                url=url,
                timeout=180,
                verify=True,
                data=json.dumps(full_query),
                headers=headers,
            )
            if logs_response.status_code > 300:
                err_msg = logs_response.text

            logs_response.raise_for_status()
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(logs_response.json()),
                return_code=0,
                params=params,
            )
        except requests.Timeout:
            logging.warn("Timeout while fetching opensearch logs search", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Request timed out while fetching opensearch logs search {err_msg}",
                return_code=-1,
                params=params,
            )
        except RequestException as e:
            logging.warn("Failed to fetch opensearch logs search", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Network error while opensearch logs search {err_msg} {str(e)}",
                return_code=-1,
                params=params,
            )
        except Exception as e:
            logging.warn("Failed to process opensearch logs search", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error {err_msg}: {str(e)}",
                return_code=-1,
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        return f'search logs: query="{params.get("query")}"'


class OpenSearchLogsToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="opensearch/logs",
            description="OpenSearch integration to fetch logs",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/opensearch-logs.html",
            icon_url="https://opensearch.org/assets/brand/PNG/Mark/opensearch_mark_default.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetLogFields(toolset=self),
                LogsSearchQuery(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config and not os.environ.get("OPENSEARCH_LOGS_URL", None):
            return False, "Missing opensearch traces URL. Check your config"
        elif not config and os.environ.get("OPENSEARCH_LOGS_URL", None):
            self.config = OpenSearchIndexConfig(
                opensearch_url=os.environ.get("OPENSEARCH_LOGS_URL"),
                index_name=os.environ.get("OPENSEARCH_LOGS_INDEX_NAME"),
                opensearch_auth_header=os.environ.get(
                    "OPENSEARCH_LOGS_AUTH_HEADER", None
                ),
            )
            return opensearch_health_check(self.config)
        else:
            self.config = OpenSearchIndexConfig(**config)
            return opensearch_health_check(self.config)

    def get_example_config(self) -> Dict[str, Any]:
        example_config = OpenSearchIndexConfig(
            opensearch_url="YOUR OPENSEARCH LOGS URL",
            index_name="YOUR OPENSEARCH LOGS INDEX NAME",
            opensearch_auth_header="YOUR OPENSEARCH LOGS AUTH HEADER (Optional)",
        )
        return example_config.model_dump()
