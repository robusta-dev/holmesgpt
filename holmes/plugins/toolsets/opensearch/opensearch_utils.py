import json
import logging
from typing import Optional, Any
from urllib.parse import urljoin

from pydantic import BaseModel
import requests  # type: ignore

from holmes.plugins.toolsets.logging_api import LoggingConfig


class OpenSearchLoggingLabelsConfig(BaseModel):
    pod: str = "kubernetes.pod.name"
    namespace: str = "kubernetes.namespace"
    timestamp: str = "@timestamp"
    message: str = "message"
    log_level: str = "log.level"


class OpenSearchLoggingConfig(LoggingConfig):
    opensearch_url: str
    index_pattern: str
    opensearch_auth_header: Optional[str] = None
    # If True, use script-based field discovery instead of getMappings API
    use_script_for_fields_discovery: bool = False
    labels: OpenSearchLoggingLabelsConfig = OpenSearchLoggingLabelsConfig()


def add_auth_header(auth_header: Optional[str]) -> dict[str, Any]:
    results = {}
    if auth_header:
        results["Authorization"] = auth_header
    return results


def get_search_url(config: OpenSearchLoggingConfig) -> str:
    return urljoin(config.opensearch_url, f"/{config.index_pattern}/_search")


def opensearch_health_check(config: OpenSearchLoggingConfig) -> tuple[bool, str]:
    url = get_search_url(config)
    try:
        headers = {"Content-Type": "application/json"}
        headers.update(add_auth_header(config.opensearch_auth_header))
        health_response = requests.get(
            url=url,
            verify=True,
            data=json.dumps({"size": 1}),
            headers=headers,
        )
        health_response.raise_for_status()
        return True, ""
    except Exception as e:
        logging.info("Failed to initialize opensearch toolset", exc_info=True)
        return False, f"Failed to initialize opensearch toolset. url={url}. {str(e)}"


def format_log_to_json(log_line: Any) -> str:
    try:
        return json.dumps(log_line)
    except Exception:
        # Handle potential serialization errors (e.g., non-serializable objects)
        return str(log_line)


def format_logs(
    logs: list[dict[str, Any]],
    config: OpenSearchLoggingConfig,
) -> str:
    if not logs or not isinstance(logs, list):
        return ""

    # Get field names from config or use defaults
    timestamp_field = config.labels.timestamp
    level_field = config.labels.log_level
    message_field = config.labels.message

    formatted_lines = []

    for hit in logs:
        # Ensure hit is a dictionary and has _source
        if not isinstance(hit, dict):
            formatted_lines.append(
                f"Skipping invalid log entry (not a dict): {type(hit)}"
            )
            continue
        source = hit.get("_source")
        if not isinstance(source, dict):
            formatted_lines.append(
                f"Skipping log entry with invalid or missing '_source': {hit.get('_id', 'N/A')}"
            )
            continue

        # Safely get fields using .get() with a default
        timestamp = source.get(timestamp_field, "N/A")
        level = source.get(level_field, "N/A")
        message = source.get(message_field, None)

        # Ensure message is a string and truncate if necessary
        if message and not isinstance(message, str):
            message = str(message)  # Convert non-strings

        if message:
            formatted_lines.append(f"{timestamp} {level} {message}")
        else:
            # fallback displaying the logs line as-is
            formatted_lines.append(format_log_to_json(hit))

    return "\n".join(formatted_lines)


def build_query(
    config: OpenSearchLoggingConfig,
    namespace: str,
    pod_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    filter_pattern: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    size = limit if limit else 5000

    pod_field = config.labels.pod
    namespace_field = config.labels.namespace
    timestamp_field = config.labels.timestamp
    message_field = config.labels.message

    must_constraints = [
        {"term": {f"{pod_field}.keyword": pod_name}},
        {"term": {f"{namespace_field}.keyword": namespace}},
    ]

    query = {
        "size": size,
        "sort": [{timestamp_field: {"order": "asc"}}],
        "query": {"bool": {"must": must_constraints}},
    }

    # Add timestamp range if provided
    if start_time or end_time:
        range_query: dict = {"range": {timestamp_field: {}}}
        if start_time:
            range_query["range"][timestamp_field]["gte"] = start_time
        if end_time:
            range_query["range"][timestamp_field]["lte"] = end_time

        must_constraints.append(range_query)

    # Add message filter if provided
    if filter_pattern:
        must_constraints.append({"regexp": {message_field: filter_pattern}})

    return query
