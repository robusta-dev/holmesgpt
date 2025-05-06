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
    format_logs,
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
        if not self.toolset.config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                params=params,
            )
        try:
            if not self._cache:
                self._cache = TTLCache(
                    maxsize=5, ttl=self.toolset.config.fields_ttl_seconds
                )

            cached_response = self._cache.get(LOGS_FIELDS_CACHE_KEY, None)
            if cached_response:
                logging.debug("logs fields returned from cache")
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=cached_response,
                    params=params,
                )

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
            if logs_response.status_code == 200:
                response = json.dumps(logs_response.json(), indent=2)
                self._cache[LOGS_FIELDS_CACHE_KEY] = response

                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=response,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    return_code=logs_response.status_code,
                    error=logs_response.text,
                    params=params,
                )

        except requests.Timeout:
            logging.warning("Timeout while fetching opensearch logs fields", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Request timed out while fetching opensearch logs fields",
            )
        except RequestException as e:
            logging.warning("Failed to fetch opensearch logs fields", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Network error while opensearch logs fields: {str(e)}",
            )
        except Exception as e:
            logging.warning("Failed to process opensearch logs fields", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error: {str(e)}",
            )

    def get_parameterized_one_liner(self, params) -> str:
        return "list log documents fields"


class LogsSearchQuery(BaseOpenSearchLogsTool):
    def __init__(self, toolset: "OpenSearchLogsToolset"):
        super().__init__(
            name="fetch_opensearch_logs",
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

        if not self.toolset.config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                params=params,
            )
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

            if logs_response.status_code == 200:
                response = logs_response.json()
                logs = format_logs(logs=response["hits"], format_type="simplified")
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=logs,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    return_code=logs_response.status_code,
                    error=logs_response.text,
                    params=params,
                )
        except requests.Timeout:
            logging.warning("Timeout while fetching opensearch logs search", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Request timed out while fetching opensearch logs search {err_msg}",
                params=params,
            )
        except RequestException as e:
            logging.warning("Failed to fetch opensearch logs search", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Network error while opensearch logs search {err_msg} {str(e)}",
                params=params,
            )
        except Exception as e:
            logging.warning("Failed to process opensearch logs search", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unexpected error {err_msg}: {str(e)}",
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
        env_url = os.environ.get("OPENSEARCH_LOGS_URL", None)
        env_index_pattern = os.environ.get("OPENSEARCH_LOGS_INDEX_NAME", "*")
        if not config and not env_url:
            return False, "Missing opensearch traces URL. Check your config"
        elif not config and env_url:
            self.config = OpenSearchIndexConfig(
                opensearch_url=env_url,
                index_pattern=env_index_pattern,
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
            index_pattern="YOUR OPENSEARCH LOGS INDEX NAME",
            opensearch_auth_header="YOUR OPENSEARCH LOGS AUTH HEADER (Optional)",
        )
        return example_config.model_dump()
