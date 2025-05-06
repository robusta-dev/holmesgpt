import json
import logging
import os
from typing import List, Literal, Optional, Dict, Any, Tuple, cast
from urllib.parse import urljoin

import requests
from holmes.core.tools import Toolset
from pydantic import BaseModel


class OpenSearchIndexConfig(BaseModel):
    opensearch_url: str
    index_pattern: str
    opensearch_auth_header: Optional[str] = None
    # Setting to None will disable the cache
    fields_ttl_seconds: Optional[int] = 14400  # 4 hours
    # If True, use script-based field discovery instead of getMappings API
    use_script_for_fields_discovery: bool = False


class BaseOpenSearchToolset(Toolset):
    def get_example_config(self) -> Dict[str, Any]:
        example_config = OpenSearchIndexConfig(
            opensearch_url="YOUR OPENSEARCH LOGS URL",
            index_pattern="YOUR OPENSEARCH LOGS INDEX NAME",
            opensearch_auth_header="YOUR OPENSEARCH LOGS AUTH HEADER (Optional)",
        )
        return example_config.model_dump()

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

    @property
    def opensearch_config(self) -> OpenSearchIndexConfig:
        return cast(OpenSearchIndexConfig, self.config)


def add_auth_header(auth_header: Optional[str]) -> Dict[str, Any]:
    results = {}
    if auth_header:
        results["Authorization"] = auth_header
    return results


def get_search_url(config: OpenSearchIndexConfig) -> str:
    return urljoin(config.opensearch_url, f"/{config.index_pattern}/_search")


def opensearch_health_check(config: OpenSearchIndexConfig) -> Tuple[bool, str]:
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
    logs: List[Dict[str, Any]],
    format_type: Literal["simplified", "json"] = "simplified",
    timestamp_field: str = "@timestamp",
    level_field: str = "log.level",
    message_field: str = "message",
    max_message_length: Optional[int] = 2000,  # Limit message length for conciseness
    include_source_in_json: bool = True,  # Control if _source or the whole hit is used for JSON
) -> str:
    """
    Formats a list of OpenSearch log hits for display, prioritizing conciseness.

    Each log entry is placed on a new line.

    Args:
        logs: A list of log documents, typically from OpenSearch response `hits['hits']`.
              It's expected that each item in the list is a dictionary representing
              a single log hit.
        format_type: The desired output format:
            - "simplified": Formats as "<timestamp> <level> <message>".
                           Fields that are missing will be represented as 'N/A'.
                           Message field length is controlled by max_message_length.
            - "json": Formats each log's source document (`_source` by default) as a
                      compact JSON string on its own line. Use include_source_in_json=False
                      to dump the entire hit object (including _id, _index etc.),
                      which is less concise.
        timestamp_field: The field name within `_source` containing the log timestamp
                         (used in 'simplified' format).
        level_field: The field name within `_source` containing the log level/severity
                     (used in 'simplified' format).
        message_field: The field name within `_source` containing the main log message
                       (used in 'simplified' format).
        max_message_length: Maximum characters for the message field in 'simplified' format.
                            Truncates with '...' if exceeded. Set to None for no truncation.
        include_source_in_json: If True and format_type is 'json', dumps only the '_source'.
                                If False, dumps the entire hit dictionary.

    Returns:
        A single string with formatted logs, separated by newlines.
        Returns an empty string if the input list is empty or invalid.
    """
    if not logs or not isinstance(logs, list):
        return ""

    formatted_lines = []

    if format_type == "simplified":
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
            if (
                message
                and max_message_length is not None
                and len(message) > max_message_length
            ):
                message = message[:max_message_length] + "..."

            if message:
                formatted_lines.append(f"{timestamp} {level} {message}")
            else:
                # fallback displaying the logs line as-is
                formatted_lines.append(format_log_to_json(hit))

    elif format_type == "json":
        for hit in logs:
            formatted_lines.append(format_log_to_json(hit))

    else:
        # Should not happen with Literal typing, but good practice
        raise ValueError("Invalid format_type. Choose 'simplified' or 'json'.")

    return "\n".join(formatted_lines)
