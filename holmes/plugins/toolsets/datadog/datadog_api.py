import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict, Union, Tuple
import requests  # type: ignore
from pydantic import AnyUrl, BaseModel
from requests.structures import CaseInsensitiveDict  # type: ignore
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_incrementing
from tenacity.wait import wait_base


START_RETRY_DELAY = (
    5.0  # Initial fallback delay if datadog does not return a reset_time
)
INCREMENT_RETRY_DELAY = 5.0  # Delay increment after each rate limit, if datadog does not return a reset_time
MAX_RETRY_COUNT_ON_RATE_LIMIT = 5

RATE_LIMIT_REMAINING_SECONDS_HEADER = "X-RateLimit-Reset"

# Cache for OpenAPI spec
_openapi_spec_cache: Dict[str, Any] = {}

# Relative time pattern
RELATIVE_TIME_PATTERN = re.compile(r"^-?(\d+)([hdwmsy]|min)$|^now$", re.IGNORECASE)


class DatadogBaseConfig(BaseModel):
    """Base configuration for all Datadog toolsets"""

    dd_api_key: str
    dd_app_key: str
    site_api_url: AnyUrl
    request_timeout: int = 60


class DataDogRequestError(Exception):
    payload: dict
    status_code: int
    response_text: str
    response_headers: CaseInsensitiveDict[str]

    def __init__(
        self,
        payload: dict,
        status_code: int,
        response_text: str,
        response_headers: CaseInsensitiveDict[str],
    ):
        super().__init__(f"HTTP error: {status_code} - {response_text}")
        self.payload = payload
        self.status_code = status_code
        self.response_text = response_text
        self.response_headers = response_headers


def get_headers(dd_config: DatadogBaseConfig) -> Dict[str, str]:
    """Get standard headers for Datadog API requests.

    Args:
        dd_config: Datadog configuration object

    Returns:
        Dictionary of headers for Datadog API requests
    """
    return {
        "Content-Type": "application/json",
        "DD-API-KEY": dd_config.dd_api_key,
        "DD-APPLICATION-KEY": dd_config.dd_app_key,
    }


def extract_cursor(data: dict) -> Optional[str]:
    """Extract cursor for paginating through Datadog logs API responses."""
    if data is None:
        return None
    meta = data.get("meta", {})
    if meta is None:
        return None
    page = meta.get("page", {})
    if page is None:
        return None
    return page.get("after", None)


class retry_if_http_429_error(retry_if_exception):
    def __init__(self):
        def is_http_429_error(exception):
            return (
                isinstance(exception, DataDogRequestError)
                and exception.status_code == 429
            )

        super().__init__(predicate=is_http_429_error)


class wait_for_retry_after_header(wait_base):
    def __init__(self, fallback):
        self.fallback = fallback

    def __call__(self, retry_state):
        if retry_state.outcome:
            exc = retry_state.outcome.exception()

            if isinstance(exc, DataDogRequestError) and exc.response_headers.get(
                RATE_LIMIT_REMAINING_SECONDS_HEADER
            ):
                reset_time_header = exc.response_headers.get(
                    RATE_LIMIT_REMAINING_SECONDS_HEADER
                )
                if reset_time_header:
                    try:
                        reset_time = int(reset_time_header)
                        wait_time = max(0, reset_time) + 0.1
                        return wait_time
                    except ValueError:
                        logging.warning(
                            f"Received invalid {RATE_LIMIT_REMAINING_SECONDS_HEADER} header value from datadog: {reset_time_header}"
                        )

        return self.fallback(retry_state)


@retry(
    retry=retry_if_http_429_error(),
    wait=wait_for_retry_after_header(
        fallback=wait_incrementing(
            start=START_RETRY_DELAY, increment=INCREMENT_RETRY_DELAY
        )
    ),
    stop=stop_after_attempt(MAX_RETRY_COUNT_ON_RATE_LIMIT),
    before_sleep=lambda retry_state: logging.warning(
        f"DataDog API rate limited. Retrying... "
        f"(attempt {retry_state.attempt_number}/{MAX_RETRY_COUNT_ON_RATE_LIMIT})"
    ),
    reraise=True,
)
def execute_paginated_datadog_http_request(
    url: str,
    headers: dict,
    payload_or_params: dict,
    timeout: int,
    method: str = "POST",
) -> tuple[Any, Optional[str]]:
    response_data = execute_datadog_http_request(
        url=url,
        headers=headers,
        payload_or_params=payload_or_params,
        timeout=timeout,
        method=method,
    )
    cursor = extract_cursor(response_data)
    data = response_data.get("data", [])
    return data, cursor


def sanitize_headers(headers: Union[dict, CaseInsensitiveDict]) -> dict:
    try:
        return {
            k: v
            if ("key" not in k.lower() and "key" not in v.lower())
            else "[REDACTED]"
            for k, v in headers.items()
        }
    except (AttributeError, TypeError):
        # Return empty dict for mock objects or other non-dict types
        return {}


def execute_datadog_http_request(
    url: str,
    headers: dict,
    payload_or_params: dict,
    timeout: int,
    method: str = "POST",
) -> Any:
    # Log the request details
    logging.info("Datadog API Request:")
    logging.info(f"  Method: {method}")
    logging.info(f"  URL: {url}")
    logging.info(f"  Headers: {json.dumps(sanitize_headers(headers), indent=2)}")
    logging.info(
        f"  {'Params' if method == 'GET' else 'Payload'}: {json.dumps(payload_or_params, indent=2)}"
    )
    logging.info(f"  Timeout: {timeout}s")

    if method == "GET":
        response = requests.get(
            url, headers=headers, params=payload_or_params, timeout=timeout
        )
    else:
        response = requests.post(
            url, headers=headers, json=payload_or_params, timeout=timeout
        )

    # Log the response details
    logging.info("Datadog API Response:")
    logging.info(f"  Status Code: {response.status_code}")
    logging.info(f"  Response Headers: {dict(sanitize_headers(response.headers))}")

    if response.status_code == 200:
        response_data = response.json()
        # Log response size but not full content (could be large)
        if isinstance(response_data, dict):
            logging.info(f"  Response Keys: {list(response_data.keys())}")
            if "data" in response_data:
                data_len = (
                    len(response_data["data"])
                    if isinstance(response_data["data"], list)
                    else 1
                )
                logging.info(f"  Data Items Count: {data_len}")
        else:
            logging.info(f"  Response Type: {type(response_data).__name__}")
        return response_data

    else:
        logging.error(f"  Error Response Body: {response.text}")
        raise DataDogRequestError(
            payload=payload_or_params,
            status_code=response.status_code,
            response_text=response.text,
            response_headers=response.headers,
        )


def fetch_openapi_spec(
    site_api_url: Optional[str] = None, version: str = "both"
) -> Optional[Dict[str, Any]]:
    """Fetch and cache the Datadog OpenAPI specification.

    Args:
        site_api_url: Base URL for Datadog API (not used, kept for compatibility)
        version: Which version to fetch ('v1', 'v2', or 'both')

    Returns:
        OpenAPI spec as dictionary (combined if 'both'), or None if fetch fails
    """
    global _openapi_spec_cache

    # Use version as cache key
    cache_key = f"openapi_{version}"

    # Check cache first
    if cache_key in _openapi_spec_cache:
        return _openapi_spec_cache[cache_key]

    try:
        import yaml

        # GitHub raw URLs for Datadog's official OpenAPI specs
        spec_urls = {
            "v1": "https://raw.githubusercontent.com/DataDog/datadog-api-client-python/master/.generator/schemas/v1/openapi.yaml",
            "v2": "https://raw.githubusercontent.com/DataDog/datadog-api-client-python/master/.generator/schemas/v2/openapi.yaml",
        }

        combined_spec: Dict[str, Any] = {
            "openapi": "3.0.0",
            "paths": {},
            "components": {},
        }

        versions_to_fetch = []
        if version == "both":
            versions_to_fetch = ["v1", "v2"]
        elif version in spec_urls:
            versions_to_fetch = [version]
        else:
            logging.error(f"Invalid version: {version}")
            return None

        for ver in versions_to_fetch:
            try:
                logging.info(f"Fetching Datadog OpenAPI spec for {ver}...")
                response = requests.get(spec_urls[ver], timeout=30)
                if response.status_code == 200:
                    # Parse YAML to dict
                    spec = yaml.safe_load(response.text)

                    if version == "both":
                        # Merge specs
                        if "paths" in spec:
                            # Prefix v1 paths with /api/v1 and v2 with /api/v2
                            for path, methods in spec.get("paths", {}).items():
                                prefixed_path = (
                                    f"/api/{ver}{path}"
                                    if not path.startswith("/api/")
                                    else path
                                )
                                paths_dict = combined_spec.get("paths", {})
                                if isinstance(paths_dict, dict):
                                    paths_dict[prefixed_path] = methods

                        # Merge components
                        if "components" in spec:
                            for comp_type, components in spec.get(
                                "components", {}
                            ).items():
                                components_dict = combined_spec.get("components", {})
                                if isinstance(components_dict, dict):
                                    if comp_type not in components_dict:
                                        components_dict[comp_type] = {}
                                    components_dict[comp_type].update(components)
                    else:
                        combined_spec = spec

                    logging.info(f"Successfully fetched OpenAPI spec for {ver}")
                else:
                    logging.warning(
                        f"Failed to fetch spec for {ver}: HTTP {response.status_code}"
                    )
            except Exception as e:
                logging.error(f"Failed to fetch spec for {ver}: {e}")
                if version != "both":
                    return None

        if combined_spec["paths"]:
            _openapi_spec_cache[cache_key] = combined_spec
            logging.info(
                f"Cached OpenAPI spec with {len(combined_spec['paths'])} endpoints"
            )
            return combined_spec
        else:
            logging.warning("No endpoints found in OpenAPI spec")
            return None

    except Exception as e:
        logging.error(f"Error fetching OpenAPI spec: {e}")
        return None


def get_endpoint_requirements(
    spec: Dict[str, Any], endpoint: str, method: str
) -> Optional[Dict[str, Any]]:
    """Extract parameter requirements for a specific endpoint from OpenAPI spec.

    Args:
        spec: OpenAPI specification
        endpoint: API endpoint path
        method: HTTP method

    Returns:
        Dictionary with parameter requirements, or None if not found
    """
    if not spec or "paths" not in spec:
        return None

    # Normalize endpoint path
    endpoint = endpoint.strip("/")
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    # Find the endpoint in the spec
    paths = spec.get("paths", {})
    if endpoint not in paths:
        # Try to find a matching pattern (e.g., /api/v2/logs/events/search)
        for path_pattern in paths.keys():
            if (
                path_pattern == endpoint
                or path_pattern.replace("{", "").replace("}", "") in endpoint
            ):
                endpoint = path_pattern
                break
        else:
            return None

    # Get method requirements
    endpoint_spec = paths.get(endpoint, {})
    method_spec = endpoint_spec.get(method.lower(), {})

    if not method_spec:
        return None

    requirements = {
        "description": method_spec.get("description", ""),
        "parameters": [],
        "requestBody": None,
    }

    # Extract parameters
    for param in method_spec.get("parameters", []):
        param_info = {
            "name": param.get("name"),
            "in": param.get("in"),  # query, path, header
            "required": param.get("required", False),
            "description": param.get("description", ""),
            "schema": param.get("schema", {}),
        }
        requirements["parameters"].append(param_info)

    # Extract request body schema
    if "requestBody" in method_spec:
        body = method_spec["requestBody"]
        content = body.get("content", {})
        json_content = content.get("application/json", {})
        requirements["requestBody"] = {
            "required": body.get("required", False),
            "schema": json_content.get("schema", {}),
            "description": body.get("description", ""),
        }

    return requirements


def convert_relative_time(time_str: str) -> Tuple[str, str]:
    """Convert relative time strings to RFC3339 format.

    Args:
        time_str: Time string (e.g., '-24h', 'now', '-7d', '2024-01-01T00:00:00Z')

    Returns:
        Tuple of (converted_time, format_type) where format_type is 'relative', 'rfc3339', or 'unix'
    """
    # Check if already in RFC3339 format
    try:
        # Try parsing as RFC3339
        if "T" in time_str and (
            time_str.endswith("Z") or "+" in time_str or "-" in time_str[-6:]
        ):
            datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return time_str, "rfc3339"
    except (ValueError, AttributeError):
        pass

    # Check if Unix timestamp
    try:
        timestamp = float(time_str)
        if 1000000000 < timestamp < 2000000000:  # Reasonable Unix timestamp range
            return time_str, "unix"
    except (ValueError, TypeError):
        pass

    # Check for relative time
    match = RELATIVE_TIME_PATTERN.match(time_str.strip())
    if not match:
        # Return as-is if not recognized
        return time_str, "unknown"

    now = datetime.now(timezone.utc)

    if time_str.lower() == "now":
        return now.isoformat().replace("+00:00", "Z"), "relative"

    # Parse relative time
    groups = match.groups()
    if groups[0] is None:
        return time_str, "unknown"

    amount = int(groups[0])
    unit = groups[1].lower()

    # Convert to timedelta
    if unit == "s":
        delta = timedelta(seconds=amount)
    elif unit == "min":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    elif unit == "d":
        delta = timedelta(days=amount)
    elif unit == "w":
        delta = timedelta(weeks=amount)
    elif unit == "m":
        delta = timedelta(days=amount * 30)  # Approximate
    elif unit == "y":
        delta = timedelta(days=amount * 365)  # Approximate
    else:
        return time_str, "unknown"

    # Apply delta (subtract if negative relative time)
    if time_str.startswith("-"):
        result_time = now - delta
    else:
        result_time = now + delta

    return result_time.isoformat().replace("+00:00", "Z"), "relative"


def preprocess_time_fields(payload: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
    """Preprocess time fields in payload, converting relative times to appropriate format.

    Args:
        payload: Request payload
        endpoint: API endpoint

    Returns:
        Modified payload with converted time fields
    """
    # Deep copy to avoid modifying original
    import copy

    processed = copy.deepcopy(payload)

    # Common time field paths to check
    time_fields = [
        ["filter", "from"],
        ["filter", "to"],
        ["from"],
        ["to"],
        ["start"],
        ["end"],
        ["start_time"],
        ["end_time"],
    ]

    def get_nested(d, path):
        """Get nested dictionary value."""
        for key in path:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                return None
        return d

    def set_nested(d, path, value):
        """Set nested dictionary value."""
        for key in path[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[path[-1]] = value

    conversions = []

    for field_path in time_fields:
        value = get_nested(processed, field_path)
        if value and isinstance(value, str):
            converted, format_type = convert_relative_time(value)
            if format_type == "relative":
                set_nested(processed, field_path, converted)
                conversions.append(
                    f"{'.'.join(field_path)}: '{value}' -> '{converted}'"
                )

    if conversions:
        logging.info(f"Converted relative time fields: {', '.join(conversions)}")

    return processed


def enhance_error_message(
    error: DataDogRequestError, endpoint: str, method: str, site_api_url: str
) -> str:
    """Enhance error message with OpenAPI spec details and format examples.

    Args:
        error: Original DataDog request error
        endpoint: API endpoint
        method: HTTP method
        site_api_url: Base API URL

    Returns:
        Enhanced error message
    """
    base_msg = f"HTTP error: {error.status_code} - {error.response_text}"

    # For 400 errors, try to provide more context
    if error.status_code == 400:
        enhanced_parts = [base_msg]

        # Try to parse error details
        try:
            error_body = json.loads(error.response_text)
            if "errors" in error_body:
                enhanced_parts.append(f"\nErrors: {error_body['errors']}")

                # Check for specific field validation errors
                for err in error_body.get("errors", []):
                    if "input_validation_error" in str(err):
                        enhanced_parts.append("\n⚠️ Input validation error detected.")

                        # Add time format help
                        if any(
                            field in str(err).lower()
                            for field in ["from", "to", "time", "date"]
                        ):
                            enhanced_parts.append(
                                "\nTime format requirements:\n"
                                "  - v1 API: Unix timestamps (e.g., 1704067200)\n"
                                "  - v2 API: RFC3339 format (e.g., '2024-01-01T00:00:00Z')\n"
                                "  - NOT supported: Relative times like '-24h', 'now', '-7d'"
                            )
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to fetch OpenAPI spec for more details
        spec = fetch_openapi_spec(version="both")
        if spec:
            requirements = get_endpoint_requirements(spec, endpoint, method)
            if requirements:
                enhanced_parts.append(f"\nEndpoint: {method} {endpoint}")
                if requirements["description"]:
                    enhanced_parts.append(f"Description: {requirements['description']}")

                # Add parameter requirements
                if requirements["parameters"]:
                    enhanced_parts.append("\nRequired parameters:")
                    for param in requirements["parameters"]:
                        if param["required"]:
                            enhanced_parts.append(
                                f"  - {param['name']} ({param['in']}): {param['description']}"
                            )

                # Add request body schema hints
                if (
                    requirements["requestBody"]
                    and requirements["requestBody"]["required"]
                ):
                    enhanced_parts.append("\nRequest body is required")
                    if requirements["requestBody"]["description"]:
                        enhanced_parts.append(
                            f"Body: {requirements['requestBody']['description']}"
                        )

        # Add example for common endpoints
        if "/logs/events/search" in endpoint:
            enhanced_parts.append(
                "\nExample request body for logs search:\n"
                "```json\n"
                "{\n"
                '  "filter": {\n'
                '    "from": "2024-01-01T00:00:00Z",\n'
                '    "to": "2024-01-02T00:00:00Z",\n'
                '    "query": "*"\n'
                "  },\n"
                '  "sort": "-timestamp",\n'
                '  "page": {"limit": 50}\n'
                "}\n"
                "```"
            )

        return "\n".join(enhanced_parts)

    return base_msg
