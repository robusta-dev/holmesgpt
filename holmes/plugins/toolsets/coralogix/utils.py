from enum import Enum
import json
import logging
import urllib.parse
from datetime import datetime
from typing import Any, NamedTuple, Optional, Dict, List

from pydantic import BaseModel


class FlattenedLog(NamedTuple):
    timestamp: str
    log_message: str


class CoralogixQueryResult(BaseModel):
    logs: List[FlattenedLog]
    http_status: Optional[int]
    error: Optional[str]


class CoralogixLabelsConfig(BaseModel):
    pod: str = "resource.attributes.k8s.pod.name"
    namespace: str = "resource.attributes.k8s.namespace.name"
    log_message: str = "logRecord.body"
    timestamp: str = "logRecord.attributes.time"


class CoralogixLogsMethodology(str, Enum):
    FREQUENT_SEARCH_ONLY = "FREQUENT_SEARCH_ONLY"
    ARCHIVE_ONLY = "ARCHIVE_ONLY"
    ARCHIVE_FALLBACK = "ARCHIVE_FALLBACK"
    FREQUENT_SEARCH_FALLBACK = "FREQUENT_SEARCH_FALLBACK"
    BOTH_FREQUENT_SEARCH_AND_ARCHIVE = "BOTH_FREQUENT_SEARCH_AND_ARCHIVE"


class CoralogixConfig(BaseModel):
    team_hostname: str
    domain: str
    api_key: str
    labels: CoralogixLabelsConfig = CoralogixLabelsConfig()
    logs_retrieval_methodology: CoralogixLogsMethodology = (
        CoralogixLogsMethodology.ARCHIVE_FALLBACK
    )


def parse_json_lines(raw_text) -> List[Dict[str, Any]]:
    """Parses JSON objects from a raw text response."""
    json_objects = []
    for line in raw_text.strip().split("\n"):  # Split by newlines
        try:
            json_objects.append(json.loads(line))
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON from line: {line}")
    return json_objects


def normalize_datetime(date_str: Optional[str]) -> str:
    """takes a date string as input and attempts to convert it into a standardized ISO 8601 format with UTC timezone (“Z” suffix) and microsecond precision.
    if any error occurs during parsing or formatting, it returns the original input string.
    The method specifically handles older Python versions by removing a trailing “Z” and truncating microseconds to 6 digits before parsing.
    """
    if not date_str:
        return "UNKNOWN_TIMESTAMP"

    try:
        # older versions of python do not support `Z` appendix nor more than 6 digits of microsecond precision
        date_str_no_z = date_str.rstrip("Z")

        parts = date_str_no_z.split(".")
        if len(parts) > 1 and len(parts[1]) > 6:
            date_str_no_z = f"{parts[0]}.{parts[1][:6]}"

        date = datetime.fromisoformat(date_str_no_z)

        normalized_date_time = date.strftime("%Y-%m-%dT%H:%M:%S.%f")
        return normalized_date_time + "Z"
    except Exception:
        return date_str


def extract_field(data_obj: dict[str, Any], field: str):
    """returns a nested field from a dict
    e.g. extract_field({"parent": {"child": "value"}}, "parent.child") => value
    """
    current_object: Any = data_obj
    fields = field.split(".")

    for field in fields:
        if not current_object:
            return None
        if isinstance(current_object, dict):
            current_object = current_object.get(field)
        else:
            return None

    return current_object


def flatten_structured_log_entries(
    log_entries: List[Dict[str, Any]],
    labels_config: CoralogixLabelsConfig,
) -> List[FlattenedLog]:
    flattened_logs = []
    for log_entry in log_entries:
        try:
            userData = json.loads(log_entry.get("userData", "{}"))
            log_message = extract_field(userData, labels_config.log_message)
            timestamp = extract_field(userData, labels_config.timestamp)
            if not log_message or not timestamp:
                log_message = json.dumps(userData)
            else:
                flattened_logs.append(
                    FlattenedLog(timestamp=timestamp, log_message=log_message)
                )  # Store as tuple for sorting

        except json.JSONDecodeError:
            logging.error(f"Failed to decode userData JSON: {json.dumps(log_entry)}")
    return flattened_logs


def stringify_flattened_logs(log_entries: List[FlattenedLog]) -> str:
    formatted_logs = []
    for entry in log_entries:
        formatted_logs.append(entry.log_message)

    return "\n".join(formatted_logs) if formatted_logs else "No logs found."


def parse_json_objects(
    json_objects: List[Dict[str, Any]], labels_config: CoralogixLabelsConfig
) -> List[FlattenedLog]:
    """Extracts timestamp and log values from parsed JSON objects, sorted in ascending order (oldest first)."""
    logs: List[FlattenedLog] = []

    for data in json_objects:
        if isinstance(data, dict) and "result" in data and "results" in data["result"]:
            logs += flatten_structured_log_entries(
                log_entries=data["result"]["results"], labels_config=labels_config
            )
        elif isinstance(data, dict) and data.get("warning"):
            logging.info(
                f"Received the following warning when fetching coralogix logs: {data}"
            )
        else:
            logging.debug(f"Unrecognised partial response from coralogix logs: {data}")

    logs.sort(key=lambda x: x[0])

    return logs


def parse_logs(
    raw_logs: str,
    labels_config: CoralogixLabelsConfig,
) -> List[FlattenedLog]:
    """Processes the HTTP response and extracts only log outputs."""
    try:
        json_objects = parse_json_lines(raw_logs)
        if not json_objects:
            raise Exception("No valid JSON objects found.")
        return parse_json_objects(
            json_objects=json_objects, labels_config=labels_config
        )
    except Exception as e:
        logging.error(
            f"Unexpected error in format_logs for a coralogix API response: {str(e)}"
        )
        raise e


def build_coralogix_link_to_logs(
    config: CoralogixConfig, lucene_query: str, start: str, end: str
) -> str:
    query_param = urllib.parse.quote_plus(lucene_query)

    return f"https://{config.team_hostname}.app.{config.domain}/#/query-new/logs?query={query_param}&querySyntax=dataprime&time=from:{start},to:{end}"


def merge_log_results(
    a: CoralogixQueryResult, b: CoralogixQueryResult
) -> CoralogixQueryResult:
    """
    Merges two CoralogixQueryResult objects, deduplicating logs and sorting them by timestamp.

    """
    if a.error is None and b.error:
        return a
    elif b.error is None and a.error:
        return b
    elif a.error and b.error:
        return a

    combined_logs = a.logs + b.logs

    if not combined_logs:
        deduplicated_logs_set = set()
    else:
        deduplicated_logs_set = set(combined_logs)

    # Assumes timestamps are in a format sortable as strings (e.g., ISO 8601)
    sorted_logs = sorted(list(deduplicated_logs_set), key=lambda log: log.timestamp)

    return CoralogixQueryResult(
        logs=sorted_logs,
        http_status=a.http_status if a.http_status is not None else b.http_status,
        error=a.error,
    )
