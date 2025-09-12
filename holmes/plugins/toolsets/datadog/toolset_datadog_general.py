"""General-purpose Datadog API toolset for read-only operations."""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    StructuredToolResult,
    StructuredToolResultStatus,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import TOOLSET_CONFIG_MISSING_ERROR
from holmes.plugins.toolsets.datadog.datadog_api import (
    DatadogBaseConfig,
    DataDogRequestError,
    execute_datadog_http_request,
    get_headers,
    MAX_RETRY_COUNT_ON_RATE_LIMIT,
)
from holmes.plugins.toolsets.utils import toolset_name_for_one_liner

# Maximum response size in bytes (10MB)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024

# Whitelisted API endpoint patterns - READ ONLY operations
WHITELISTED_ENDPOINTS = [
    # Monitors
    r"^/api/v\d+/monitor(/search)?$",
    r"^/api/v\d+/monitor/\d+(/downtimes)?$",
    r"^/api/v\d+/monitor/groups/search$",
    # Dashboards
    r"^/api/v\d+/dashboard(/lists)?$",
    r"^/api/v\d+/dashboard/[^/]+$",
    r"^/api/v\d+/dashboard/public/[^/]+$",
    # SLOs (Service Level Objectives)
    r"^/api/v\d+/slo(/search)?$",
    r"^/api/v\d+/slo/[^/]+(/history)?$",
    r"^/api/v\d+/slo/[^/]+/corrections$",
    # Events
    r"^/api/v\d+/events$",
    r"^/api/v\d+/events/\d+$",
    # Incidents
    r"^/api/v\d+/incidents(/search)?$",
    r"^/api/v\d+/incidents/[^/]+$",
    r"^/api/v\d+/incidents/[^/]+/attachments$",
    r"^/api/v\d+/incidents/[^/]+/connected_integrations$",
    r"^/api/v\d+/incidents/[^/]+/relationships$",
    r"^/api/v\d+/incidents/[^/]+/timeline$",
    # Synthetics
    r"^/api/v\d+/synthetics/tests(/search)?$",
    r"^/api/v\d+/synthetics/tests/[^/]+$",
    r"^/api/v\d+/synthetics/tests/[^/]+/results$",
    r"^/api/v\d+/synthetics/tests/browser/[^/]+/results$",
    r"^/api/v\d+/synthetics/tests/api/[^/]+/results$",
    r"^/api/v\d+/synthetics/locations$",
    # Security Monitoring
    r"^/api/v\d+/security_monitoring/rules(/search)?$",
    r"^/api/v\d+/security_monitoring/rules/[^/]+$",
    r"^/api/v\d+/security_monitoring/signals(/search)?$",
    r"^/api/v\d+/security_monitoring/signals/[^/]+$",
    # Service Map / APM Services
    r"^/api/v\d+/services$",
    r"^/api/v\d+/services/[^/]+$",
    r"^/api/v\d+/services/[^/]+/dependencies$",
    # Hosts
    r"^/api/v\d+/hosts$",
    r"^/api/v\d+/hosts/totals$",
    r"^/api/v\d+/hosts/[^/]+$",
    # Usage & Cost
    r"^/api/v\d+/usage/[^/]+$",
    r"^/api/v\d+/usage/summary$",
    r"^/api/v\d+/usage/billable-summary$",
    r"^/api/v\d+/usage/cost_by_org$",
    r"^/api/v\d+/usage/estimated_cost$",
    # Processes
    r"^/api/v\d+/processes$",
    # Tags
    r"^/api/v\d+/tags/hosts(/[^/]+)?$",
    # Notebooks
    r"^/api/v\d+/notebooks$",
    r"^/api/v\d+/notebooks/\d+$",
    # Service Dependencies
    r"^/api/v\d+/service_dependencies$",
    # Organization
    r"^/api/v\d+/org$",
    r"^/api/v\d+/org/[^/]+$",
    # Users (read only)
    r"^/api/v\d+/users$",
    r"^/api/v\d+/users/[^/]+$",
    # Teams (read only)
    r"^/api/v\d+/teams$",
    r"^/api/v\d+/teams/[^/]+$",
    # Audit logs
    r"^/api/v\d+/audit/events$",
    # Service Accounts (read only)
    r"^/api/v\d+/service_accounts$",
    r"^/api/v\d+/service_accounts/[^/]+$",
]

# Blacklisted path segments that indicate write operations
BLACKLISTED_SEGMENTS = [
    "/create",
    "/update",
    "/delete",
    "/patch",
    "/remove",
    "/add",
    "/revoke",
    "/cancel",
    "/mute",
    "/unmute",
    "/enable",
    "/disable",
    "/archive",
    "/unarchive",
    "/assign",
    "/unassign",
    "/invite",
    "/bulk",
    "/import",
    "/export",
    "/trigger",
    "/validate",
    "/execute",
    "/run",
    "/start",
    "/stop",
    "/restart",
]

# POST endpoints that are allowed (search/query operations only)
WHITELISTED_POST_ENDPOINTS = [
    r"^/api/v\d+/monitor/search$",
    r"^/api/v\d+/dashboard/lists$",
    r"^/api/v\d+/slo/search$",
    r"^/api/v\d+/events/search$",
    r"^/api/v\d+/incidents/search$",
    r"^/api/v\d+/synthetics/tests/search$",
    r"^/api/v\d+/security_monitoring/rules/search$",
    r"^/api/v\d+/security_monitoring/signals/search$",
    r"^/api/v\d+/logs/events/search$",
    r"^/api/v\d+/spans/events/search$",
    r"^/api/v\d+/rum/events/search$",
    r"^/api/v\d+/audit/events/search$",
]


class DatadogGeneralConfig(DatadogBaseConfig):
    """Configuration for general-purpose Datadog toolset."""

    max_response_size: int = MAX_RESPONSE_SIZE
    allow_custom_endpoints: bool = (
        False  # If True, allows endpoints not in whitelist (still filtered for safety)
    )


class DatadogGeneralToolset(Toolset):
    """General-purpose Datadog API toolset for read-only operations not covered by specialized toolsets."""

    dd_config: Optional[DatadogGeneralConfig] = None

    def __init__(self):
        super().__init__(
            name="datadog/general",
            description="General-purpose Datadog API access for read-only operations including monitors, dashboards, SLOs, incidents, synthetics, and more",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/datadog/",
            icon_url="https://imgix.datadoghq.com//img/about/presskit/DDlogo.jpg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                DatadogAPIGet(toolset=self),
                DatadogAPIPostSearch(toolset=self),
                ListDatadogAPIResources(toolset=self),
            ],
            tags=[ToolsetTag.CORE],
        )
        template_file_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "datadog_general_instructions.jinja2"
            )
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        """Check prerequisites with configuration."""
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR

        try:
            dd_config = DatadogGeneralConfig(**config)
            self.dd_config = dd_config
            success, error_msg = self._perform_healthcheck(dd_config)
            return success, error_msg
        except Exception as e:
            logging.exception("Failed to set up Datadog general toolset")
            return False, f"Failed to parse Datadog configuration: {str(e)}"

    def _perform_healthcheck(self, dd_config: DatadogGeneralConfig) -> Tuple[bool, str]:
        """Perform health check on Datadog API."""
        try:
            logging.info("Performing Datadog general API configuration healthcheck...")
            url = f"{dd_config.site_api_url}/api/v1/validate"
            headers = get_headers(dd_config)

            data = execute_datadog_http_request(
                url=url,
                headers=headers,
                payload_or_params={},
                timeout=dd_config.request_timeout,
                method="GET",
            )

            if data.get("valid", False):
                logging.info("Datadog general API healthcheck completed successfully")
                return True, ""
            else:
                error_msg = "Datadog API key validation failed"
                logging.error(f"Datadog general API healthcheck failed: {error_msg}")
                return False, f"Datadog general API healthcheck failed: {error_msg}"

        except Exception as e:
            logging.exception("Failed during Datadog general API healthcheck")
            return False, f"Healthcheck failed with exception: {str(e)}"

    def get_example_config(self) -> Dict[str, Any]:
        """Get example configuration for this toolset."""
        return {
            "dd_api_key": "your-datadog-api-key",
            "dd_app_key": "your-datadog-application-key",
            "site_api_url": "https://api.datadoghq.com",
            "max_response_size": MAX_RESPONSE_SIZE,
            "allow_custom_endpoints": False,
        }


def is_endpoint_allowed(
    endpoint: str, method: str = "GET", allow_custom: bool = False
) -> Tuple[bool, str]:
    """
    Check if an endpoint is allowed based on whitelist and safety rules.

    Returns:
        Tuple of (is_allowed, error_message)
    """
    # Parse the endpoint
    parsed = urlparse(endpoint)
    path = parsed.path

    # Check for blacklisted segments
    path_lower = path.lower()
    for segment in BLACKLISTED_SEGMENTS:
        if segment in path_lower:
            return False, f"Endpoint contains blacklisted operation '{segment}'"

    # Check method-specific whitelists
    if method == "POST":
        for pattern in WHITELISTED_POST_ENDPOINTS:
            if re.match(pattern, path):
                return True, ""
        return False, f"POST method not allowed for endpoint: {path}"

    elif method == "GET":
        for pattern in WHITELISTED_ENDPOINTS:
            if re.match(pattern, path):
                return True, ""

        # If custom endpoints are allowed and no blacklisted segments found
        if allow_custom:
            return True, ""

        return False, f"Endpoint not in whitelist: {path}"

    else:
        return False, f"HTTP method {method} not allowed for {path}"


class BaseDatadogGeneralTool(Tool):
    """Base class for general Datadog API tools."""

    toolset: "DatadogGeneralToolset"


class DatadogAPIGet(BaseDatadogGeneralTool):
    """Tool for making GET requests to Datadog API."""

    def __init__(self, toolset: "DatadogGeneralToolset"):
        super().__init__(
            name="datadog_api_get",
            description="Make a GET request to a Datadog API endpoint for read-only operations",
            parameters={
                "endpoint": ToolParameter(
                    description="The API endpoint path (e.g., '/api/v1/monitors', '/api/v2/events')",
                    type="string",
                    required=True,
                ),
                "query_params": ToolParameter(
                    description="Query parameters as a dictionary (e.g., {'from': '2024-01-01', 'to': '2024-01-02'})",
                    type="object",
                    required=False,
                ),
                "description": ToolParameter(
                    description="Brief description of what this API call is retrieving",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def get_parameterized_one_liner(self, params: dict) -> str:
        """Get a one-liner description of the tool invocation."""
        description = params.get("description", "API call")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: {description}"

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        """Execute the GET request."""
        logging.info("=" * 60)
        logging.info("DatadogAPIGet Tool Invocation:")
        logging.info(f"  Description: {params.get('description', 'No description')}")
        logging.info(f"  Endpoint: {params.get('endpoint', '')}")
        logging.info(
            f"  Query Params: {json.dumps(params.get('query_params', {}), indent=2)}"
        )
        logging.info("=" * 60)

        if not self.toolset.dd_config:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=TOOLSET_CONFIG_MISSING_ERROR,
                params=params,
            )

        endpoint = params.get("endpoint", "")
        query_params = params.get("query_params", {})

        # Validate endpoint
        is_allowed, error_msg = is_endpoint_allowed(
            endpoint,
            method="GET",
            allow_custom=self.toolset.dd_config.allow_custom_endpoints,
        )
        if not is_allowed:
            logging.error(f"Endpoint validation failed: {error_msg}")
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Endpoint validation failed: {error_msg}",
                params=params,
            )

        url = None
        try:
            # Build full URL (ensure no double slashes)
            base_url = str(self.toolset.dd_config.site_api_url).rstrip("/")
            endpoint = endpoint.lstrip("/")
            url = f"{base_url}/{endpoint}"
            headers = get_headers(self.toolset.dd_config)

            logging.info(f"Full API URL: {url}")

            # Execute request
            response = execute_datadog_http_request(
                url=url,
                headers=headers,
                payload_or_params=query_params,
                timeout=self.toolset.dd_config.request_timeout,
                method="GET",
            )

            # Check response size
            response_str = json.dumps(response, indent=2)
            if (
                len(response_str.encode("utf-8"))
                > self.toolset.dd_config.max_response_size
            ):
                return StructuredToolResult(
                    status=StructuredToolResultStatus.ERROR,
                    error=f"Response too large (>{self.toolset.dd_config.max_response_size} bytes)",
                    params=params,
                )

            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=response_str,
                params=params,
            )

        except DataDogRequestError as e:
            logging.exception(e, exc_info=True)

            if e.status_code == 429:
                error_msg = f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts."
            elif e.status_code == 403:
                error_msg = (
                    f"Permission denied. Check API key permissions. Error: {str(e)}"
                )
            elif e.status_code == 404:
                error_msg = f"Endpoint not found: {endpoint}"
            else:
                error_msg = f"API error {e.status_code}: {str(e)}"

            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=error_msg,
                params=params,
                invocation=json.dumps({"url": url, "params": query_params})
                if url
                else None,
            )

        except Exception as e:
            logging.exception(f"Failed to query Datadog API: {params}", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Unexpected error: {str(e)}",
                params=params,
            )


class DatadogAPIPostSearch(BaseDatadogGeneralTool):
    """Tool for making POST requests to Datadog search/query endpoints."""

    def __init__(self, toolset: "DatadogGeneralToolset"):
        super().__init__(
            name="datadog_api_post_search",
            description="Make a POST request to Datadog search/query endpoints for complex filtering",
            parameters={
                "endpoint": ToolParameter(
                    description="The search API endpoint (e.g., '/api/v2/monitor/search', '/api/v2/events/search')",
                    type="string",
                    required=True,
                ),
                "body": ToolParameter(
                    description="Request body for the search/filter operation",
                    type="object",
                    required=True,
                ),
                "description": ToolParameter(
                    description="Brief description of what this search is looking for",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def get_parameterized_one_liner(self, params: dict) -> str:
        """Get a one-liner description of the tool invocation."""
        description = params.get("description", "Search")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: {description}"

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        """Execute the POST search request."""
        logging.info("=" * 60)
        logging.info("DatadogAPIPostSearch Tool Invocation:")
        logging.info(f"  Description: {params.get('description', 'No description')}")
        logging.info(f"  Endpoint: {params.get('endpoint', '')}")
        logging.info(f"  Body: {json.dumps(params.get('body', {}), indent=2)}")
        logging.info("=" * 60)

        if not self.toolset.dd_config:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=TOOLSET_CONFIG_MISSING_ERROR,
                params=params,
            )

        endpoint = params.get("endpoint", "")
        body = params.get("body", {})

        # Validate endpoint
        is_allowed, error_msg = is_endpoint_allowed(
            endpoint,
            method="POST",
            allow_custom=self.toolset.dd_config.allow_custom_endpoints,
        )
        if not is_allowed:
            logging.error(f"Endpoint validation failed: {error_msg}")
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Endpoint validation failed: {error_msg}",
                params=params,
            )

        url = None
        try:
            # Build full URL (ensure no double slashes)
            base_url = str(self.toolset.dd_config.site_api_url).rstrip("/")
            endpoint = endpoint.lstrip("/")
            url = f"{base_url}/{endpoint}"
            headers = get_headers(self.toolset.dd_config)

            logging.info(f"Full API URL: {url}")

            # Execute request
            response = execute_datadog_http_request(
                url=url,
                headers=headers,
                payload_or_params=body,
                timeout=self.toolset.dd_config.request_timeout,
                method="POST",
            )

            # Check response size
            response_str = json.dumps(response, indent=2)
            if (
                len(response_str.encode("utf-8"))
                > self.toolset.dd_config.max_response_size
            ):
                return StructuredToolResult(
                    status=StructuredToolResultStatus.ERROR,
                    error=f"Response too large (>{self.toolset.dd_config.max_response_size} bytes)",
                    params=params,
                )

            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=response_str,
                params=params,
            )

        except DataDogRequestError as e:
            logging.exception(e, exc_info=True)

            if e.status_code == 429:
                error_msg = f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts."
            elif e.status_code == 403:
                error_msg = (
                    f"Permission denied. Check API key permissions. Error: {str(e)}"
                )
            elif e.status_code == 404:
                error_msg = f"Endpoint not found: {endpoint}"
            else:
                error_msg = f"API error {e.status_code}: {str(e)}"

            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=error_msg,
                params=params,
                invocation=json.dumps({"url": url, "body": body}) if url else None,
            )

        except Exception as e:
            logging.exception(f"Failed to query Datadog API: {params}", exc_info=True)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Unexpected error: {str(e)}",
                params=params,
            )


class ListDatadogAPIResources(BaseDatadogGeneralTool):
    """Tool for listing available Datadog API resources and endpoints."""

    def __init__(self, toolset: "DatadogGeneralToolset"):
        super().__init__(
            name="list_datadog_api_resources",
            description="List available Datadog API resources and endpoints that can be accessed",
            parameters={
                "category": ToolParameter(
                    description="Filter by category (e.g., 'monitors', 'dashboards', 'slos', 'incidents', 'synthetics', 'security', 'hosts', 'all')",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def get_parameterized_one_liner(self, params: dict) -> str:
        """Get a one-liner description of the tool invocation."""
        category = params.get("category", "all")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: List API Resources ({category})"

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        """List available API resources."""
        category = params.get("category", "all").lower()

        logging.info("=" * 60)
        logging.info("ListDatadogAPIResources Tool Invocation:")
        logging.info(f"  Category: {category}")
        logging.info("=" * 60)

        # Define categories and their endpoints
        resources = {
            "monitors": {
                "description": "Monitor management and alerting",
                "endpoints": [
                    "GET /api/v1/monitor - List all monitors",
                    "GET /api/v1/monitor/{id} - Get a monitor by ID",
                    "POST /api/v1/monitor/search - Search monitors",
                    "GET /api/v1/monitor/groups/search - Search monitor groups",
                ],
            },
            "dashboards": {
                "description": "Dashboard and visualization management",
                "endpoints": [
                    "GET /api/v1/dashboard - List all dashboards",
                    "GET /api/v1/dashboard/{id} - Get a dashboard by ID",
                    "POST /api/v1/dashboard/lists - List dashboard lists",
                    "GET /api/v1/dashboard/public/{token} - Get public dashboard",
                ],
            },
            "slos": {
                "description": "Service Level Objectives",
                "endpoints": [
                    "GET /api/v1/slo - List all SLOs",
                    "GET /api/v1/slo/{id} - Get an SLO by ID",
                    "GET /api/v1/slo/{id}/history - Get SLO history",
                    "POST /api/v1/slo/search - Search SLOs",
                    "GET /api/v1/slo/{id}/corrections - Get SLO corrections",
                ],
            },
            "incidents": {
                "description": "Incident management",
                "endpoints": [
                    "GET /api/v2/incidents - List incidents",
                    "GET /api/v2/incidents/{id} - Get incident details",
                    "POST /api/v2/incidents/search - Search incidents",
                    "GET /api/v2/incidents/{id}/timeline - Get incident timeline",
                    "GET /api/v2/incidents/{id}/attachments - Get incident attachments",
                ],
            },
            "synthetics": {
                "description": "Synthetic monitoring and testing",
                "endpoints": [
                    "GET /api/v1/synthetics/tests - List synthetic tests",
                    "GET /api/v1/synthetics/tests/{id} - Get test details",
                    "POST /api/v1/synthetics/tests/search - Search tests",
                    "GET /api/v1/synthetics/tests/{id}/results - Get test results",
                    "GET /api/v1/synthetics/locations - List test locations",
                ],
            },
            "security": {
                "description": "Security monitoring and detection",
                "endpoints": [
                    "GET /api/v2/security_monitoring/rules - List security rules",
                    "GET /api/v2/security_monitoring/rules/{id} - Get rule details",
                    "POST /api/v2/security_monitoring/rules/search - Search rules",
                    "POST /api/v2/security_monitoring/signals/search - Search security signals",
                ],
            },
            "hosts": {
                "description": "Host and infrastructure monitoring",
                "endpoints": [
                    "GET /api/v1/hosts - List all hosts",
                    "GET /api/v1/hosts/{name} - Get host details",
                    "GET /api/v1/hosts/totals - Get host totals",
                    "GET /api/v1/tags/hosts - Get host tags",
                ],
            },
            "events": {
                "description": "Event stream and management",
                "endpoints": [
                    "GET /api/v1/events - Query event stream",
                    "GET /api/v1/events/{id} - Get event details",
                    "POST /api/v2/events/search - Search events",
                ],
            },
            "usage": {
                "description": "Usage and billing information",
                "endpoints": [
                    "GET /api/v1/usage/summary - Get usage summary",
                    "GET /api/v1/usage/billable-summary - Get billable summary",
                    "GET /api/v1/usage/estimated_cost - Get estimated costs",
                    "GET /api/v2/usage/cost_by_org - Get costs by organization",
                ],
            },
            "services": {
                "description": "APM service information",
                "endpoints": [
                    "GET /api/v2/services - List services",
                    "GET /api/v2/services/{service} - Get service details",
                    "GET /api/v2/services/{service}/dependencies - Get service dependencies",
                ],
            },
        }

        # Filter by category if specified
        if category != "all":
            matching_categories = {k: v for k, v in resources.items() if category in k}
            if not matching_categories:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.ERROR,
                    error=f"Unknown category: {category}. Available: {', '.join(resources.keys())}",
                    params=params,
                )
            resources = matching_categories

        # Format output
        output = ["Available Datadog API Resources", "=" * 40, ""]

        for cat_name, cat_info in resources.items():
            output.append(f"## {cat_name.upper()}")
            output.append(f"Description: {cat_info['description']}")
            output.append("")
            output.append("Endpoints:")
            for endpoint in cat_info["endpoints"]:
                output.append(f"  • {endpoint}")
            output.append("")

        output.append(
            "Note: All endpoints are read-only. Use the appropriate tool with the endpoint path."
        )
        output.append("Example: datadog_api_get with endpoint='/api/v1/monitors'")

        return StructuredToolResult(
            status=StructuredToolResultStatus.SUCCESS,
            data="\n".join(output),
            params=params,
        )
