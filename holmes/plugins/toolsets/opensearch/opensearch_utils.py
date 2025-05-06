import json
import logging
from typing import List, Literal, Optional, Dict, Any, Tuple, Union
from urllib.parse import urljoin

import requests
from pydantic import BaseModel


class OpenSearchIndexConfig(BaseModel):
    opensearch_url: str
    index_pattern: str
    opensearch_auth_header: Optional[str] = None
    # Setting to None will disable the cache
    fields_ttl_seconds: Optional[int] = 14400  # 4 hours


def add_auth_header(auth_header: Optional[str]) -> Dict[str, Any]:
    results = {}
    if auth_header:
        results["Authorization"] = auth_header
    return results


def get_search_url(config: OpenSearchIndexConfig) -> str:
    return urljoin(config.opensearch_url, f"/{config.index_name}/_search")


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


def format_logs(
    logs: List[Dict[str, Any]],
    format_type: Literal["simplified", "json"] = "simplified",
    timestamp_field: str = "@timestamp",
    level_field: str = "log.level",
    message_field: str = "message",
    max_message_length: Optional[int] = 2000, # Limit message length for conciseness
    include_source_in_json: bool = True # Control if _source or the whole hit is used for JSON
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
                formatted_lines.append(f"Skipping invalid log entry (not a dict): {type(hit)}")
                continue
            source = hit.get("_source")
            if not isinstance(source, dict):
                 formatted_lines.append(f"Skipping log entry with invalid or missing '_source': {hit.get('_id', 'N/A')}")
                 continue

            # Safely get fields using .get() with a default
            timestamp = source.get(timestamp_field, "N/A")
            level = source.get(level_field, "N/A")
            message = source.get(message_field, None)

            # Ensure message is a string and truncate if necessary
            if message and not isinstance(message, str):
                message = str(message) # Convert non-strings
            if message and max_message_length is not None and len(message) > max_message_length:
                print(f"truncating \"{message}\" to \"{message[:max_message_length]}\"")
                message = message[:max_message_length] + "..."

            if message:
                formatted_lines.append(f"{timestamp} {level} {message}")

    elif format_type == "json":
        for hit in logs:
             # Ensure hit is a dictionary
            if not isinstance(hit, dict):
                formatted_lines.append(f"Skipping invalid log entry (not a dict): {type(hit)}")
                continue

            target_data = hit.get("_source") if include_source_in_json else hit
            if include_source_in_json and not isinstance(target_data, dict):
                 # If we expected _source and it's bad, note it
                 formatted_lines.append(f"Skipping log entry with invalid or missing '_source' for JSON: {hit.get('_id', 'N/A')}")
                 continue
            elif not isinstance(target_data, dict):
                 # If we are dumping the whole hit and it's not a dict (unlikely but safe)
                 formatted_lines.append(f"Skipping invalid log entry (not a dict) for JSON: {type(target_data)}")
                 continue

            try:
                # Use compact JSON separators for conciseness
                json_string = json.dumps(target_data, separators=(",", ":"))
                formatted_lines.append(json_string)
            except TypeError as e:
                # Handle potential serialization errors (e.g., non-serializable objects)
                formatted_lines.append(f"Error serializing log to JSON for ID {hit.get('_id', 'N/A')}: {e}")

    else:
        # Should not happen with Literal typing, but good practice
        raise ValueError("Invalid format_type. Choose 'simplified' or 'json'.")

    return "\n".join(formatted_lines)
