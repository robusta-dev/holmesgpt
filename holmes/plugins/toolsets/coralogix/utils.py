import json
import logging
import urllib.parse
from datetime import datetime
from typing import Any, NamedTuple, Optional, Dict, List

from pydantic import BaseModel


def parse_json_lines(raw_text) -> List[Dict[str, Any]]:
    """Parses JSON objects from a raw text response."""
    json_objects = []
    for line in raw_text.strip().split("\n"):  # Split by newlines
        try:
            json_objects.append(json.loads(line))
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON from line: {line}")
    return json_objects


def format_kubernetes_info(
    kubernetes: Optional[dict[str, str]], add_namespace_tag: bool, add_pod_tag: bool
):
    tags = []
    if kubernetes:
        if add_pod_tag and kubernetes.get("pod_name"):
            tags.append(f'pod_name="{kubernetes.get("pod_name")}"')
        if add_namespace_tag and kubernetes.get("namespace_name"):
            tags.append(f'namespace_name="{kubernetes.get("namespace_name")}"')
    return " ".join(tags)


def indent_multiline_log_message(indent_char_count: int, log_message: str):
    """improves human readability of logs by indenting logs that span multiple lines.
    This is important because lines for a single logs() call on a system may span multiple coralogix log lines.

    e.g.
    instead of printing this:
    ```
    2025-03-25T07:43:39.062945526Z Require stack:
         at defaultResolveImpl (node:internal/modules/cjs/loader:1061:19)
         at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1066:22)
         at Module.require (node:internal/modules/cjs/loader:1491:12)
       code: 'MODULE_NOT_FOUND',
    2025-03-25T07:43:39.062945626Z etc.
    ```

    this method will print:

    ```
    2025-03-25T07:43:39.062945526Z Require stack:
                                       at defaultResolveImpl (node:internal/modules/cjs/loader:1061:19)
                                       at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1066:22)
                                       at Module.require (node:internal/modules/cjs/loader:1491:12)
                                     code: 'MODULE_NOT_FOUND',
    2025-03-25T07:43:39.062945626Z etc.
    ```
    """
    lines = log_message.replace("\r", "\n").split("\n")
    log_message = lines.pop(0)
    while (
        not log_message and len(lines) > 0
    ):  # Some log messages start with a line feed or return carriage. Make sure the first line is not empty
        log_message = lines.pop(0)
    for new_line in lines:
        if new_line.strip():
            line = "\n" + (" " * indent_char_count) + new_line
            log_message += line
    return log_message


def normalize_datetime(date_str: str) -> str:
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


class FlattenedLog(NamedTuple):
    timestamp: str
    log_message: str
    tags: str


def flatten_structured_log_entries(
    log_entries: List[Dict[str, Any]], add_namespace_tag: bool, add_pod_tag: bool
) -> List[FlattenedLog]:
    flattened_logs = []
    for log_entry in log_entries:
        try:
            user_data = json.loads(log_entry.get("userData", "{}"))
            kubernetes = user_data.get("kubernetes", None)
            timestamp = normalize_datetime(user_data.get("time"))
            log_message = user_data.get("log", "")
            tags = format_kubernetes_info(kubernetes, add_namespace_tag, add_pod_tag)
            if log_message:
                flattened_logs.append(
                    FlattenedLog(
                        timestamp=timestamp, log_message=log_message, tags=tags
                    )
                )  # Store as tuple for sorting

        except json.JSONDecodeError:
            logging.error(
                f"Failed to decode userData JSON: {log_entry.get('userData')}"
            )
    return flattened_logs


def stringify_flattened_logs(log_entries: List[FlattenedLog]) -> str:
    formatted_logs = []
    for entry in log_entries:
        prefix = f"{entry.timestamp} "
        if entry.tags:
            prefix = f"{entry.timestamp} {entry.tags} "
        log_message = indent_multiline_log_message(
            indent_char_count=len(prefix), log_message=entry.log_message
        )
        formatted_logs.append(f"{prefix}{log_message}")

    return "\n".join(formatted_logs) if formatted_logs else "No logs found."


def parse_json_objects(
    json_objects: List[Dict[str, Any]], add_namespace_tag: bool, add_pod_tag: bool
) -> str:
    """Extracts timestamp and log values from parsed JSON objects, sorted in ascending order (oldest first)."""
    logs = []

    for data in json_objects:
        if isinstance(data, dict) and "result" in data and "results" in data["result"]:
            logs += flatten_structured_log_entries(
                log_entries=data["result"]["results"],
                add_namespace_tag=add_namespace_tag,
                add_pod_tag=add_pod_tag,
            )
        elif isinstance(data, dict) and data.get("warning"):
            logging.info(
                f"Received the following warning when fetching coralogix logs: {data}"
            )
        else:
            logging.debug(f"Unrecognised partial response from coralogix logs: {data}")

    logs.sort(key=lambda x: x[0])

    return stringify_flattened_logs(logs)


def format_logs(raw_logs: str, add_namespace_tag: bool, add_pod_tag: bool) -> str:
    """Processes the HTTP response and extracts only log outputs."""
    try:
        json_objects = parse_json_lines(raw_logs)
        if not json_objects:
            raise Exception("No valid JSON objects found.")
        return parse_json_objects(json_objects, add_namespace_tag, add_pod_tag)
    except Exception as e:
        logging.error(
            f"Unexpected error in format_logs for a coralogix API response: {str(e)}"
        )
        raise e


class CoralogixLabelsConfig(BaseModel):
    pod: str = "kubernetes.pod_name"
    namespace: str = "kubernetes.namespace_name"
    app: str = "kubernetes.labels.app"


class CoralogixConfig(BaseModel):
    team_hostname: str
    domain: str
    api_key: str
    labels: CoralogixLabelsConfig = CoralogixLabelsConfig()


def get_resource_label(params: Dict, config: CoralogixConfig):
    resource_type = params.get("resource_type", "pod")
    label = None
    if resource_type == "pod":
        label = config.labels.pod
    else:
        return f'Error: unsupported resource type "{resource_type}". resource_type must be "pod"'
    return label


def build_coralogix_link_to_logs(
    config: CoralogixConfig, lucene_query: str, start: str, end: str
) -> str:
    query_param = urllib.parse.quote_plus(lucene_query)

    return f"https://{config.team_hostname}.app.{config.domain}/#/query-new/logs?query={query_param}&querySyntax=dataprime&time=from:{start},to:{end}"
