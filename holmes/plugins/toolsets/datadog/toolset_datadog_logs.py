from enum import Enum
import json
import logging
from typing import Any, Optional, Dict, Tuple, Set, List
from holmes.core.tools import (
    CallablePrerequisite,
    ToolsetTag,
)
from pydantic import BaseModel, Field
from holmes.core.tools import StructuredToolResult, ToolResultStatus
from holmes.plugins.toolsets.consts import TOOLSET_CONFIG_MISSING_ERROR
from holmes.plugins.toolsets.datadog.datadog_api import (
    DatadogBaseConfig,
    DataDogRequestError,
    execute_paginated_datadog_http_request,
    get_headers,
    MAX_RETRY_COUNT_ON_RATE_LIMIT,
)
from holmes.plugins.toolsets.logging_utils.logging_api import (
    DEFAULT_TIME_SPAN_SECONDS,
    DEFAULT_LOG_LIMIT,
    BasePodLoggingToolset,
    FetchPodLogsParams,
    LoggingCapability,
    PodLoggingTool,
)
from holmes.plugins.toolsets.logging_utils.shared_log_utils import (
    StructuredLog,
    format_logs_with_containers,
)
from holmes.plugins.toolsets.utils import process_timestamps_to_rfc3339, to_unix_ms


class DataDogLabelsMapping(BaseModel):
    pod: str = "pod_name"
    namespace: str = "kube_namespace"


class DataDogStorageTier(str, Enum):
    INDEXES = "indexes"
    ONLINE_ARCHIVES = "online-archives"
    FLEX = "flex"


DEFAULT_STORAGE_TIERS = [DataDogStorageTier.INDEXES]


class DatadogLogsConfig(DatadogBaseConfig):
    indexes: list[str] = ["*"]
    # Ordered list of storage tiers. Works as fallback. Subsequent tiers are queried only if the previous tier yielded no result
    storage_tiers: list[DataDogStorageTier] = Field(
        default=DEFAULT_STORAGE_TIERS, min_length=1
    )
    labels: DataDogLabelsMapping = DataDogLabelsMapping()
    page_size: int = 300
    default_limit: int = DEFAULT_LOG_LIMIT


def calculate_page_size(
    params: FetchPodLogsParams, dd_config: DatadogLogsConfig, logs: list
) -> int:
    logs_count = len(logs)

    max_logs_count = dd_config.default_limit
    if params.limit:
        max_logs_count = params.limit

    return min(dd_config.page_size, max(0, max_logs_count - logs_count))


def build_datadog_explorer_url(
    dd_config: DatadogLogsConfig, query: str, from_time: str, to_time: str
) -> str:
    """Build URL to view these logs in Datadog Log Explorer"""
    import urllib.parse

    # Extract base URL without /api path
    base_url = str(dd_config.site_api_url).replace("/api/v2", "").replace("/api", "")
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    # Build the logs explorer URL
    # Format: https://app.datadoghq.com/logs?query=...&from_ts=...&to_ts=...
    params = {"query": query, "from_ts": from_time, "to_ts": to_time, "live": "false"}

    query_string = urllib.parse.urlencode(params)
    return f"{base_url}/logs?{query_string}"


def fetch_paginated_logs(
    params: FetchPodLogsParams,
    dd_config: DatadogLogsConfig,
    storage_tier: DataDogStorageTier,
) -> Tuple[list[dict], str]:
    """Fetch logs from Datadog and return logs plus the query URL"""
    limit = params.limit or dd_config.default_limit

    (from_time, to_time) = process_timestamps_to_rfc3339(
        start_timestamp=params.start_time,
        end_timestamp=params.end_time,
        default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
    )

    url = f"{dd_config.site_api_url}/api/v2/logs/events/search"
    headers = get_headers(dd_config)

    # Build base query
    query_parts = [
        f"{dd_config.labels.namespace}:{params.namespace}",
        f"{dd_config.labels.pod}:{params.pod_name}",
    ]

    # Add filter if provided (already in Datadog query syntax)
    if params.filter:
        query_parts.append(f"({params.filter})")

    # Add exclude filter if provided
    if params.exclude_filter:
        # If it doesn't start with NOT, add it
        if not params.exclude_filter.strip().upper().startswith("NOT"):
            query_parts.append(f"NOT ({params.exclude_filter})")
        else:
            query_parts.append(params.exclude_filter)

    query = " ".join(query_parts)

    payload: Dict[str, Any] = {
        "filter": {
            "from": from_time,
            "to": to_time,
            "query": query,
            "indexes": dd_config.indexes,
            "storage_tier": storage_tier.value,
        },
        "sort": "-timestamp",
        "page": {"limit": min(dd_config.page_size, limit)},
    }

    logs, cursor = execute_paginated_datadog_http_request(
        url=url,
        headers=headers,
        payload_or_params=payload,
        timeout=dd_config.request_timeout,
    )

    while cursor and len(logs) < limit:
        payload["page"]["cursor"] = cursor
        payload["page"]["limit"] = min(dd_config.page_size, limit - len(logs))
        new_logs, cursor = execute_paginated_datadog_http_request(
            url=url,
            headers=headers,
            payload_or_params=payload,
            timeout=dd_config.request_timeout,
        )
        logs += new_logs

    # logs are fetched descending order. Unified logging API follows the pattern of kubectl logs where oldest logs are first
    logs.reverse()

    # Trim to limit if we got more
    if len(logs) > limit:
        logs = logs[-limit:]

    # Construct Datadog Explorer URL
    explorer_url = build_datadog_explorer_url(dd_config, query, from_time, to_time)

    return logs, explorer_url


def parse_datadog_logs(raw_logs: list[dict]) -> List[StructuredLog]:
    """Convert Datadog log format to StructuredLog format"""
    structured_logs = []

    for raw_log_item in raw_logs:
        attributes = raw_log_item.get("attributes", {})
        message = attributes.get("message", json.dumps(raw_log_item))

        # Extract timestamp
        timestamp_str = attributes.get("timestamp")
        timestamp_ms = None
        if timestamp_str:
            try:
                timestamp_ms = to_unix_ms(timestamp_str)
            except Exception:
                # If we can't parse timestamp, leave it as None
                pass

        # Extract container name if available
        container = attributes.get("container_name") or attributes.get(
            "docker", {}
        ).get("container_name")

        structured_logs.append(
            StructuredLog(
                timestamp_ms=timestamp_ms, container=container, content=message
            )
        )

    return structured_logs


class DatadogLogsToolset(BasePodLoggingToolset):
    dd_config: Optional[DatadogLogsConfig] = None

    @property
    def supported_capabilities(self) -> Set[LoggingCapability]:
        """Datadog supports its own query syntax, not regex"""
        return set()  # Empty since we use custom parameter descriptions

    def __init__(self):
        super().__init__(
            name="datadog/logs",
            description="Toolset for interacting with Datadog to fetch logs",
            docs_url="https://docs.datadoghq.com/api/latest/logs/",
            icon_url="https://imgix.datadoghq.com//img/about/presskit/DDlogo.jpg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                PodLoggingTool(self, toolset_name="datadog/logs"),
            ],
            experimental=True,
            tags=[ToolsetTag.CORE],
        )

    def logger_name(self) -> str:
        return "DataDog"

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        if not self.dd_config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=TOOLSET_CONFIG_MISSING_ERROR,
                params=params.model_dump(),
            )

        try:
            raw_logs: List[dict] = []
            explorer_url = ""

            for storage_tier in self.dd_config.storage_tiers:
                raw_logs, explorer_url = fetch_paginated_logs(
                    params, self.dd_config, storage_tier=storage_tier
                )

                if raw_logs:
                    # Convert to structured logs
                    structured_logs = parse_datadog_logs(raw_logs)

                    # Check if we have multiple containers
                    containers = set(
                        log.container for log in structured_logs if log.container
                    )
                    has_multiple_containers = len(containers) > 1

                    # Format logs
                    formatted_logs = format_logs_with_containers(
                        logs=structured_logs,
                        display_container_name=has_multiple_containers,
                    )

                    # Build simple metadata showing the Datadog URL
                    metadata_lines = [
                        "\n" + "=" * 80,
                        "LOG QUERY METADATA",
                        "=" * 80,
                        f"Total logs returned: {len(structured_logs):,}",
                        f"View in Datadog: {explorer_url}",
                        "=" * 80,
                    ]

                    # Put metadata at the end
                    response_data = formatted_logs + "\n" + "\n".join(metadata_lines)

                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS,
                        data=response_data,
                        params=params.model_dump(),
                    )

            # No logs found in any storage tier
            metadata_lines = [
                "=" * 80,
                "LOG QUERY METADATA",
                "=" * 80,
                "No logs found for this pod in the specified time range.",
                f"View in Datadog: {explorer_url}",
                "=" * 80,
            ]

            return StructuredToolResult(
                status=ToolResultStatus.NO_DATA,
                data="\n".join(metadata_lines),
                params=params.model_dump(),
            )

        except DataDogRequestError as e:
            logging.exception(e, exc_info=True)

            # Provide more specific error message for rate limiting failures
            if e.status_code == 429:
                error_msg = f"Datadog API rate limit exceeded. Failed after {MAX_RETRY_COUNT_ON_RATE_LIMIT} retry attempts."
            else:
                error_msg = f"Exception while querying Datadog: {str(e)}"

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=error_msg,
                params=params.model_dump(),
                invocation=json.dumps(e.payload),
            )

        except Exception as e:
            logging.exception(
                f"Failed to query Datadog logs for params: {params}", exc_info=True
            )
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception while querying Datadog: {str(e)}",
                params=params.model_dump(),
            )

    def _perform_healthcheck(self) -> Tuple[bool, str]:
        """
        Perform a healthcheck by fetching a single log from Datadog.
        Returns (success, error_message).
        """
        try:
            logging.info("Performing Datadog configuration healthcheck...")
            healthcheck_params = FetchPodLogsParams(
                namespace="*",
                pod_name="*",
                limit=1,
                start_time="-172800",  # 48 hours in seconds
            )

            result = self.fetch_pod_logs(healthcheck_params)

            if result.status == ToolResultStatus.ERROR:
                error_msg = result.error or "Unknown error during healthcheck"
                logging.error(f"Datadog healthcheck failed: {error_msg}")
                return False, f"Datadog healthcheck failed: {error_msg}"
            elif result.status == ToolResultStatus.NO_DATA:
                error_msg = "No logs were found in the last 48 hours using wildcards for pod and namespace. Is the configuration correct?"
                logging.error(f"Datadog healthcheck failed: {error_msg}")
                return False, f"Datadog healthcheck failed: {error_msg}"

            logging.info("Datadog healthcheck completed successfully")
            return True, ""

        except Exception as e:
            logging.exception("Failed during Datadog healthcheck")
            return False, f"Healthcheck failed with exception: {str(e)}"

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return (
                False,
                TOOLSET_CONFIG_MISSING_ERROR,
            )

        try:
            dd_config = DatadogLogsConfig(**config)
            self.dd_config = dd_config

            # Perform healthcheck
            success, error_msg = self._perform_healthcheck()
            return success, error_msg

        except Exception as e:
            logging.exception("Failed to set up Datadog toolset")
            return (False, f"Failed to parse Datadog configuration: {str(e)}")

    def get_example_config(self) -> Dict[str, Any]:
        return {
            "dd_api_key": "your-datadog-api-key",
            "dd_app_key": "your-datadog-application-key",
            "site_api_url": "https://api.datadoghq.com",
        }
