import json
import logging
import os
from typing import Optional, Any, cast
from urllib.parse import urljoin

from pydantic import BaseModel
import requests  # type: ignore

from holmes.core.tools import Toolset


class OpenSearchLoggingLabelsConfig(BaseModel):
    pod: str = "kubernetes.pod_name"
    namespace: str = "kubernetes.namespace_name"
    timestamp: str = "@timestamp"
    message: str = "message"
    log_level: str = "log.level"


class BaseOpenSearchConfig(BaseModel):
    opensearch_url: str
    index_pattern: str
    opensearch_auth_header: Optional[str] = None


class OpenSearchLoggingConfig(BaseOpenSearchConfig):
    # If True, use script-based field discovery instead of getMappings API
    use_script_for_fields_discovery: bool = False
    labels: OpenSearchLoggingLabelsConfig = OpenSearchLoggingLabelsConfig()


def add_auth_header(auth_header: Optional[str]) -> dict[str, Any]:
    results = {}
    if auth_header:
        results["Authorization"] = auth_header
    return results


def get_search_url(config: BaseOpenSearchConfig) -> str:
    return urljoin(config.opensearch_url, f"/{config.index_pattern}/_search")


def opensearch_health_check(config: BaseOpenSearchConfig) -> tuple[bool, str]:
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
    level_field = config.labels.log_level
    message_field = config.labels.message

    formatted_lines = []

    for hit in logs:
        # Ensure hit is a dictionary and has _source
        if not isinstance(hit, dict):
            formatted_lines.append(format_log_to_json(hit))
            continue
        source = hit.get("_source")
        if not isinstance(source, dict):
            formatted_lines.append(format_log_to_json(hit))
            continue

        # Safely get fields using .get() with a default
        level = source.get(level_field, "N/A")
        message = source.get(message_field, None)

        # Ensure message is a string
        if message and not isinstance(message, str):
            message = str(message)  # Convert non-strings

        if message:
            formatted_lines.append(f"{level} {message}")
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
    match: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    size = limit if limit else 5000

    pod_field = config.labels.pod
    namespace_field = config.labels.namespace
    timestamp_field = config.labels.timestamp
    message_field = config.labels.message

    must_constraints: list[dict] = [
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
    if match:
        must_constraints.append({"match_phrase": {message_field: match}})

    return query


class BaseOpenSearchToolset(Toolset):
    def get_example_config(self) -> dict[str, Any]:
        example_config = BaseOpenSearchConfig(
            opensearch_url="YOUR OPENSEARCH LOGS URL",
            index_pattern="YOUR OPENSEARCH LOGS INDEX NAME",
            opensearch_auth_header="YOUR OPENSEARCH LOGS AUTH HEADER (Optional)",
        )
        return example_config.model_dump()

    def prerequisites_callable(self, config: dict[str, Any]) -> tuple[bool, str]:
        env_url = os.environ.get("OPENSEARCH_LOGS_URL", None)
        env_index_pattern = os.environ.get("OPENSEARCH_LOGS_INDEX_NAME", "*")
        if not config and not env_url:
            return False, "Missing opensearch traces URL. Check your config"
        elif not config and env_url:
            self.config = BaseOpenSearchConfig(
                opensearch_url=env_url,
                index_pattern=env_index_pattern,
                opensearch_auth_header=os.environ.get(
                    "OPENSEARCH_LOGS_AUTH_HEADER", None
                ),
            )
            return opensearch_health_check(self.config)
        else:
            self.config = BaseOpenSearchConfig(**config)
            return opensearch_health_check(self.config)

    @property
    def opensearch_config(self) -> BaseOpenSearchConfig:
        return cast(BaseOpenSearchConfig, self.config)
