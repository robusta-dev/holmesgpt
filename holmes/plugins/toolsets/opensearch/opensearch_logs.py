import os
import logging

from typing import Any, Dict

import requests  # type: ignore
from cachetools import TTLCache  # type: ignore
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    ToolsetTag,
)
import json
from requests import RequestException  # type: ignore
from urllib.parse import urljoin

from holmes.plugins.toolsets.opensearch.opensearch_utils import (
    BaseOpenSearchToolset,
    format_logs,
    add_auth_header,
)
from holmes.core.tools import StructuredToolResult, ToolResultStatus

LOGS_FIELDS_CACHE_KEY = "cached_logs_fields"


class GetLogFields(Tool):
    def __init__(self, toolset: "OpenSearchLogsToolset"):
        super().__init__(
            name="describe_opensearch_logs_fields",
            description="List all possible opensearch fields and their types. Useful for querying logs as it describes what fields can be used",
            parameters={},
        )
        self._toolset = toolset
        self._cache = None

    def _invoke(self, params: Dict) -> StructuredToolResult:
        if not self._toolset.opensearch_config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                params=params,
            )
        try:
            if not self._cache and self._toolset.opensearch_config.fields_ttl_seconds:
                self._cache = TTLCache(
                    maxsize=5, ttl=self._toolset.opensearch_config.fields_ttl_seconds
                )
            if self._cache:
                cached_response = self._cache.get(LOGS_FIELDS_CACHE_KEY, None)
                if cached_response:
                    logging.debug("logs fields returned from cache")
                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS,
                        data=cached_response,
                        params=params,
                    )

            headers = {"Content-Type": "application/json"}
            headers.update(
                add_auth_header(self._toolset.opensearch_config.opensearch_auth_header)
            )

            # Use script-based field discovery if configured, otherwise use getMappings API
            if self._toolset.opensearch_config.use_script_for_fields_discovery:
                return self._get_fields_using_script(headers, params)
            else:
                return self._get_fields_using_mappings(headers, params)

        except requests.Timeout:
            logging.warning(
                "Timeout while fetching opensearch logs fields", exc_info=True
            )
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

    def _get_fields_using_script(
        self, headers: Dict, params: Dict
    ) -> StructuredToolResult:
        """Use the script-based approach to get fields (original implementation)"""
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

        url = urljoin(
            self._toolset.opensearch_config.opensearch_url,
            f"/{self._toolset.opensearch_config.index_pattern}/_search",
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
            if self._cache:
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

    def _get_fields_using_mappings(
        self, headers: Dict, params: Dict
    ) -> StructuredToolResult:
        """Use the OpenSearch getMappings API to retrieve fields (new implementation)"""
        url = urljoin(
            self._toolset.opensearch_config.opensearch_url,
            f"/{self._toolset.opensearch_config.index_pattern}/_mapping",
        )

        mapping_response = requests.get(
            url=url,
            timeout=180,
            verify=True,
            headers=headers,
        )

        if mapping_response.status_code == 200:
            mapping_data = mapping_response.json()

            # Extract field names, types, and indexes from mapping response
            field_details: Dict = {}  # Dictionary to store field details

            # Process all indices in the response
            for index_name, index_data in mapping_data.items():
                mappings = index_data.get("mappings", {})
                properties = mappings.get("properties", {})

                # Extract fields and add them to the dict with their types and indices
                self._extract_fields_from_properties(
                    properties, "", field_details, index_name
                )

            # Format the response - fields with their types and indexes that use them
            formatted_fields = []
            for field_name, details in field_details.items():
                formatted_fields.append(
                    {
                        "name": field_name,
                        "type": details["type"],
                        "indexes": sorted(details["indexes"]),
                    }
                )

            # Sort fields by name for consistent output
            formatted_fields.sort(key=lambda x: x["name"])

            response = json.dumps({"fields": formatted_fields}, indent=2)
            if self._cache:
                self._cache[LOGS_FIELDS_CACHE_KEY] = response

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=response,
                params=params,
            )
        else:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                return_code=mapping_response.status_code,
                error=mapping_response.text,
                params=params,
            )

    def _extract_fields_from_properties(
        self, properties: Dict, prefix: str, field_details: Dict, index_name: str
    ) -> None:
        """
        Recursively extract field names, types, and indexes from the properties section of the mapping

        Args:
            properties: Properties dictionary from the mapping
            prefix: Current field path prefix
            field_details: Dictionary to store field details in the format {field_name: {"type": type, "indexes": [index1, index2, ...]}}
            index_name: Name of the current index being processed
        """
        for field_name, field_config in properties.items():
            full_path = f"{prefix}{field_name}" if prefix else field_name

            # Get field type - OpenSearch has "type" at the root level of field_config
            field_type = field_config.get(
                "type", "object"
            )  # Default to "object" if type not specified

            # Add or update field details
            if full_path not in field_details:
                field_details[full_path] = {"type": field_type, "indexes": [index_name]}
            else:
                # Field already exists, add this index to the list
                field_details[full_path]["indexes"].append(index_name)
                # We assume the type is the same across indexes

            # Handle nested fields
            nested_properties = field_config.get("properties", {})
            if nested_properties:
                self._extract_fields_from_properties(
                    nested_properties, f"{full_path}.", field_details, index_name
                )

    def get_parameterized_one_liner(self, params) -> str:
        return "list log documents fields"


class LogsSearchQuery(Tool):
    def __init__(self, toolset: "OpenSearchLogsToolset"):
        super().__init__(
            name="fetch_opensearch_logs",
            description="Get logs of any app, pod, deployment etc. in the system by querying opensearch for logs.",
            parameters={
                "query": ToolParameter(
                    description="An OpenSearch search query. It should be a stringified json, matching opensearch search syntax. "
                    "The query must contain a 'range' on the @timestamp field. From a given timestamp, until a given timestamp",
                    type="string",
                ),
            },
        )
        self._toolset = toolset
        self._cache = None

    def _invoke(self, params: Any) -> StructuredToolResult:
        if not self._toolset.opensearch_config:
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
            headers.update(
                add_auth_header(self._toolset.opensearch_config.opensearch_auth_header)
            )
            url = urljoin(
                self._toolset.opensearch_config.opensearch_url,
                f"/{self._toolset.opensearch_config.index_pattern}/_search",
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
                logs = format_logs(
                    logs=response.get("hits", {}).get("hits", []),
                    format_type="simplified",
                )
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
            logging.warning(
                "Timeout while fetching opensearch logs search", exc_info=True
            )
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
        return f'search logs: {params.get("query")}'


class OpenSearchLogsToolset(BaseOpenSearchToolset):
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
