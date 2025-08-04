import logging
from typing import Any, Dict, Optional, Tuple

import requests  # type: ignore
from requests import RequestException
from urllib.parse import urljoin
from pydantic import BaseModel, ConfigDict

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import TOOLSET_CONFIG_MISSING_ERROR


class OpenSearchSearchConfig(BaseModel):
    opensearch_url: str
    index_pattern: str
    opensearch_auth_header: Optional[str] = None
    verify_ssl: bool = False
    timeout: int = 30


class BaseOpenSearchSearchTool(Tool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    toolset: "OpenSearchSearchToolset"


class SearchDocuments(BaseOpenSearchSearchTool):
    def __init__(self, toolset: "OpenSearchSearchToolset"):
        super().__init__(
            name="opensearch_search_documents",
            description="Search for documents in OpenSearch indices matching the configured index pattern. Returns matching documents based on query criteria.",
            parameters={
                "query": ToolParameter(
                    description="Search query string. Can be a simple text search or use Lucene query syntax",
                    type="string",
                    required=False,
                ),
                "field": ToolParameter(
                    description="Specific field to search in (e.g., 'account_name', 'description'). If not specified, searches all fields",
                    type="string",
                    required=False,
                ),
                "match_type": ToolParameter(
                    description="Type of search: 'match' (partial), 'term' (exact), 'wildcard' (pattern), 'range' (for numbers/dates), 'transaction_id' (find by transaction ID)",
                    type="string",
                    required=False,
                ),
                "size": ToolParameter(
                    description="Maximum number of documents to return (default: 10, max: 100)",
                    type="integer",
                    required=False,
                ),
                "sort_field": ToolParameter(
                    description="Field to sort by (e.g., 'created_at', 'amount')",
                    type="string",
                    required=False,
                ),
                "sort_order": ToolParameter(
                    description="Sort order: 'asc' or 'desc'",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            config = self.toolset.config
            if not config:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="OpenSearch configuration not available",
                    params=params,
                )

            # Use the configured index_pattern
            index_name = config.index_pattern
            query_string = params.get("query", "*")
            field = params.get("field")
            match_type = params.get("match_type", "match")
            size = min(params.get("size", 10), 100)  # Cap at 100
            sort_field = params.get("sort_field")
            sort_order = params.get("sort_order", "desc")

            # Build the search query
            search_query = self._build_search_query(
                query_string=query_string,
                field=field,
                match_type=match_type,
                size=size,
                sort_field=sort_field,
                sort_order=sort_order,
            )

            # Make the search request
            search_url = urljoin(config.opensearch_url, f"/{index_name}/_search")
            headers = {"Content-Type": "application/json"}

            if config.opensearch_auth_header:
                headers["Authorization"] = config.opensearch_auth_header

            logging.info(f"OpenSearch query: {search_query}")
            logging.info(f"Searching URL: {search_url}")

            response = requests.post(
                search_url,
                json=search_query,
                headers=headers,
                verify=config.verify_ssl,
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json()

            # Format the response
            formatted_result = self._format_search_results(result)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=formatted_result,
                params=params,
            )

        except Exception as e:
            logging.exception("OpenSearch search failed")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Search failed: {str(e)}",
                params=params,
            )

    def _build_search_query(
        self,
        query_string: str,
        field: Optional[str],
        match_type: str,
        size: int,
        sort_field: Optional[str],
        sort_order: str,
    ) -> Dict[str, Any]:
        """Build OpenSearch query DSL"""
        query: Dict[str, Any] = {"size": size}

        # Build the main query
        if query_string == "*" or not query_string:
            # Match all documents
            query["query"] = {"match_all": {}}
        else:
            if match_type == "term":
                # Exact match - try both with and without .keyword for better compatibility
                if field:
                    # For keyword fields like transaction_id, try without .keyword first
                    if field in ["transaction_id", "account_id", "status", "currency"]:
                        query["query"] = {"term": {field: query_string}}
                    else:
                        # For text fields, use .keyword for exact match
                        query["query"] = {"term": {f"{field}.keyword": query_string}}
                else:
                    # Use multi_match for searching across all fields
                    query["query"] = {
                        "multi_match": {"query": query_string, "fields": ["*"]}
                    }
            elif match_type == "wildcard":
                # Wildcard search
                if field:
                    query["query"] = {"wildcard": {field: f"*{query_string}*"}}
                else:
                    query["query"] = {"query_string": {"query": f"*{query_string}*"}}
            elif match_type == "range":
                # Range query (for numbers/dates)
                if field:
                    try:
                        # Try to parse as number
                        value = float(query_string)
                        query["query"] = {"range": {field: {"gte": value}}}
                    except ValueError:
                        # Treat as date string
                        query["query"] = {"range": {field: {"gte": query_string}}}
                else:
                    return {"error": "Range queries require a specific field"}
            elif match_type == "transaction_id":
                # Special case for transaction ID search
                query["query"] = {"term": {"transaction_id": query_string}}
            else:
                # Default: match query
                if field:
                    query["query"] = {"match": {field: query_string}}
                else:
                    query["query"] = {
                        "multi_match": {"query": query_string, "fields": ["*"]}
                    }

        # Add sorting if specified
        if sort_field:
            query["sort"] = [{sort_field: {"order": sort_order}}]

        return query

    def _format_search_results(self, result: Dict[str, Any]) -> str:
        """Format search results for display"""
        if "error" in result:
            return f"Search error: {result['error']}"

        hits = result.get("hits", {})
        total_hits = hits.get("total", {})
        if isinstance(total_hits, dict):
            total_count = total_hits.get("value", 0)
        else:
            total_count = total_hits

        documents = hits.get("hits", [])

        if total_count == 0:
            return f"No documents found matching the search criteria in index '{self.toolset.config.index_pattern if self.toolset.config else 'unknown'}'."

        formatted_results = [
            f"Found {total_count} documents (showing {len(documents)}):\n"
        ]

        for i, doc in enumerate(documents, 1):
            source = doc.get("_source", {})
            doc_id = doc.get("_id", "N/A")
            score = doc.get("_score", "N/A")

            formatted_results.append(f"\n--- Document {i} ---")
            formatted_results.append(f"ID: {doc_id}")
            formatted_results.append(f"Score: {score}")

            # Display key fields
            for key, value in source.items():
                if isinstance(value, dict):
                    formatted_results.append(f"{key}: {value}")
                elif isinstance(value, list):
                    formatted_results.append(f"{key}: {', '.join(map(str, value))}")
                else:
                    # Truncate long values
                    str_value = str(value)
                    if len(str_value) > 200:
                        str_value = str_value[:200] + "..."
                    formatted_results.append(f"{key}: {str_value}")

        return "\n".join(formatted_results)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        query = params.get("query", "*")
        return f"opensearch_search_documents(query='{query}')"


class OpenSearchSearchToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="opensearch/search",
            enabled=False,
            description="Search and retrieve documents from any OpenSearch index. Supports various query types including text search, exact matches, wildcards, and range queries.",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/opensearch.html",
            icon_url="https://opensearch.org/assets/brand/PNG/Mark/opensearch_mark_default.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                SearchDocuments(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
        )
        self.config: Optional[OpenSearchSearchConfig] = None

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR

        try:
            self.config = OpenSearchSearchConfig(**config)

            # Test connectivity
            health_url = urljoin(self.config.opensearch_url, "/_cluster/health")
            headers = {}
            if self.config.opensearch_auth_header:
                headers["Authorization"] = self.config.opensearch_auth_header

            response = requests.get(
                health_url,
                headers=headers,
                verify=self.config.verify_ssl,
                timeout=self.config.timeout,
            )
            response.raise_for_status()

            health_data = response.json()
            if health_data.get("status") in ["green", "yellow"]:
                return True, "OpenSearch search toolset ready"
            else:
                return (
                    False,
                    f"OpenSearch cluster health is {health_data.get('status')}",
                )

        except RequestException as e:
            logging.exception("Failed to connect to OpenSearch")
            return False, f"Failed to connect to OpenSearch: {str(e)}"
        except Exception as e:
            logging.exception("Failed to set up OpenSearch search toolset")
            return False, f"Configuration error: {str(e)}"

    def get_example_config(self) -> Dict[str, Any]:
        example_config = OpenSearchSearchConfig(
            opensearch_url="http://opensearch.services.svc.cluster.local:9200",
            index_pattern="transactions",
            opensearch_auth_header="{{ env.OPENSEARCH_AUTH_HEADER }}",
            verify_ssl=False,
            timeout=30,
        )
        return example_config.model_dump()
