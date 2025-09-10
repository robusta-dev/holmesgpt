import os
from enum import Enum
import json
import logging
from typing import Any, Optional, Dict, Tuple, Set
from holmes.core.tools import (
    CallablePrerequisite,
    ToolsetTag,
)
from pydantic import BaseModel, Field
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
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
from holmes.plugins.toolsets.utils import process_timestamps_to_rfc3339


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


def fetch_paginated_logs(
    params: FetchPodLogsParams,
    dd_config: DatadogLogsConfig,
    storage_tier: DataDogStorageTier,
) -> list[dict]:
    limit = params.limit or dd_config.default_limit

    (from_time, to_time) = process_timestamps_to_rfc3339(
        start_timestamp=params.start_time,
        end_timestamp=params.end_time,
        default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
    )

    url = f"{dd_config.site_api_url}/api/v2/logs/events/search"
    headers = get_headers(dd_config)

    query = f"{dd_config.labels.namespace}:{params.namespace}"
    query += f" {dd_config.labels.pod}:{params.pod_name}"
    if params.filter:
        filter = params.filter.replace('"', '\\"')
        query += f' "{filter}"'

    payload: Dict[str, Any] = {
        "filter": {
            "from": from_time,
            "to": to_time,
            "query": query,
            "indexes": dd_config.indexes,
            "storage_tier": storage_tier.value,
        },
        "sort": "-timestamp",
        "page": {"limit": calculate_page_size(params, dd_config, [])},
    }

    logs, cursor = execute_paginated_datadog_http_request(
        url=url,
        headers=headers,
        payload_or_params=payload,
        timeout=dd_config.request_timeout,
    )

    while cursor and len(logs) < limit:
        payload["page"]["cursor"] = cursor
        new_logs, cursor = execute_paginated_datadog_http_request(
            url=url,
            headers=headers,
            payload_or_params=payload,
            timeout=dd_config.request_timeout,
        )
        logs += new_logs
        payload["page"]["limit"] = calculate_page_size(params, dd_config, logs)

    # logs are fetched descending order. Unified logging API follows the pattern of kubectl logs where oldest logs are first
    logs.reverse()

    if len(logs) > limit:
        logs = logs[-limit:]
    return logs


def format_logs(raw_logs: list[dict]) -> str:
    logs = []

    for raw_log_item in raw_logs:
        message = raw_log_item.get("attributes", {}).get(
            "message", json.dumps(raw_log_item)
        )
        logs.append(message)

    return "\n".join(logs)


class DatadogLogsToolset(BasePodLoggingToolset):
    dd_config: Optional[DatadogLogsConfig] = None

    @property
    def supported_capabilities(self) -> Set[LoggingCapability]:
        """Datadog logs API supports historical data and substring matching"""
        return {
            LoggingCapability.HISTORICAL_DATA
        }  # No regex support, no exclude filter, but supports historical data

    def __init__(self):
        super().__init__(
            name="datadog/logs",
            description="Toolset for fetching logs from Datadog, including historical data for pods no longer in the cluster",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/datadog/",
            icon_url="https://imgix.datadoghq.com//img/about/presskit/DDlogo.jpg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[],  # Initialize with empty tools first
            tags=[ToolsetTag.CORE],
        )
        # Now that parent is initialized and self.name exists, create the tool
        self.tools = [PodLoggingTool(self)]
        self._reload_instructions()

    def logger_name(self) -> str:
        return "DataDog"

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        if not self.dd_config:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                data=TOOLSET_CONFIG_MISSING_ERROR,
                params=params.model_dump(),
            )

        try:
            raw_logs = []
            for storage_tier in self.dd_config.storage_tiers:
                raw_logs = fetch_paginated_logs(
                    params, self.dd_config, storage_tier=storage_tier
                )

                if raw_logs:
                    logs_str = format_logs(raw_logs)
                    return StructuredToolResult(
                        status=StructuredToolResultStatus.SUCCESS,
                        data=logs_str,
                        params=params.model_dump(),
                    )

            return StructuredToolResult(
                status=StructuredToolResultStatus.NO_DATA,
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
                status=StructuredToolResultStatus.ERROR,
                error=error_msg,
                params=params.model_dump(),
                invocation=json.dumps(e.payload),
            )

        except Exception as e:
            logging.exception(
                f"Failed to query Datadog logs for params: {params}", exc_info=True
            )
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
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

            if result.status == StructuredToolResultStatus.ERROR:
                error_msg = result.error or "Unknown error during healthcheck"
                logging.error(f"Datadog healthcheck failed: {error_msg}")
                return False, f"Datadog healthcheck failed: {error_msg}"
            elif result.status == StructuredToolResultStatus.NO_DATA:
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

    def _reload_instructions(self):
        """Load Datadog logs specific troubleshooting instructions."""
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "datadog_logs_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
