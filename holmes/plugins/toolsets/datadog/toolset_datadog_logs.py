from enum import Enum
import json
import requests  # type: ignore
import logging
import time
from typing import Any, Optional, Dict, Tuple
from holmes.core.tools import (
    CallablePrerequisite,
    ToolsetTag,
)
from pydantic import BaseModel
from holmes.core.tools import StructuredToolResult, ToolResultStatus
from holmes.plugins.toolsets.consts import TOOLSET_CONFIG_MISSING_ERROR
from holmes.plugins.toolsets.logging_utils.logging_api import DEFAULT_TIME_SPAN_SECONDS, BasePodLoggingToolset, FetchPodLogsParams, PodLoggingTool
from holmes.plugins.toolsets.utils import process_timestamps_to_int


class DataDogLabelsMapping(BaseModel):
    pod: str = "pod_name"
    namespace: str = "kube_namespace"

class DataDogStorageTier(str, Enum):
    INDEXES = "indexes"
    ONLINE_ARCHIVES = "online-archives"
    FLEX = "flex"

DEFAULT_STORAGE_TIERS = [DataDogStorageTier.INDEXES]

class DatadogConfig(BaseModel):
    dd_api_key: str
    dd_app_key: str
    indexes: list[str] = ["*"]
    site_api_url: str # e.g. https://api.us3.datadoghq.com. c.f. https://docs.datadoghq.com/getting_started/site/
    # Ordered list of storage tiers. Works as fallback. Subsequent tiers are queried only if the previous tier yielded no result 
    storage_tiers: list[DataDogStorageTier] = DEFAULT_STORAGE_TIERS
    labels: DataDogLabelsMapping = DataDogLabelsMapping()
    page_size: int = 300
    default_limit: int = 1000
    request_timeout: int = 60

class DataDogRequestError(Exception):
    payload: dict
    status_code: int
    response_text: str
    def __init__(self, payload:dict, status_code:int, response_text:str):
        super().__init__(f"HTTP error: {status_code} - {response_text}")
        self.payload = payload
        self.status_code = status_code
        self.response_text = response_text

class DataDogRequest429Error(DataDogRequestError):
    reset_time: Optional[int]
    def __init__(self, payload:dict, status_code:int, response_text:str, reset_time:Optional[int]):
        super().__init__(payload=payload, status_code=status_code, response_text=response_text)
        self.reset_time = reset_time



def _extract_cursor_for_next_paginated_api_call(data:dict) -> Optional[str]:
    return data.get("meta", {}).get("page", {}).get("after", None)


def _execute_logs_query(url:str, headers:dict, payload:dict, timeout:int) -> tuple[list[dict], Optional[str]]:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if response.status_code == 200:
        data = response.json()
        cursor = _extract_cursor_for_next_paginated_api_call(data)

        logs = data.get("data", [])
        return logs, cursor
    
    elif response.status_code == 429:
        reset_time_header = response.headers.get('X-RateLimit-Reset')
        reset_time:Optional[int] = None
        if reset_time_header:
            try:
                reset_time = int(reset_time_header)
            except ValueError:
                logging.warning(f"Invalid X-RateLimit-Reset header value: {reset_time_header}")
                reset_time = None

        raise DataDogRequest429Error(
            payload=payload,
            status_code=response.status_code,
            response_text=response.text,
            reset_time=reset_time
        )
    else:
        raise DataDogRequestError(
            payload=payload, 
            status_code=response.status_code, 
            response_text=response.text
        )  

def calculate_page_size(params:FetchPodLogsParams, dd_config:DatadogConfig, logs:list) -> int:

    logs_count = len(logs)

    max_logs_count = dd_config.default_limit
    if params.limit:
        max_logs_count =  params.limit

    return min(dd_config.page_size, max(0, max_logs_count - logs_count))

def fetch_paginated_logs(params:FetchPodLogsParams, dd_config:DatadogConfig, storage_tier:DataDogStorageTier) -> list[dict]:

    limit = params.limit or dd_config.default_limit

    (from_time, to_time) = process_timestamps_to_int(
        start=params.start_time,
        end=params.end_time,
        default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
    )

    url = f"{dd_config.site_api_url}/api/v2/logs/events/search"
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": dd_config.dd_api_key,
        "DD-APPLICATION-KEY": dd_config.dd_app_key,
    }


    query = f"{dd_config.labels.namespace}:{params.namespace}"
    query += f" {dd_config.labels.pod}:{params.pod_name}"
    if params.filter:
        filter = params.filter.replace('"','\\"')
        query += f' "{filter}"'

    payload = {
        "filter": {
            "from": from_time,
            "to": to_time,
            "query": query,
            "indexes": dd_config.indexes,
            "storage_tier": storage_tier.value,
        },
        "sort": "timestamp",
        "page": {"limit": calculate_page_size(params, dd_config, [])},
    }

    logs, cursor = _execute_logs_query(url=url, headers=headers, payload=payload, timeout=dd_config.request_timeout)

    retry_count = 0
    base_delay = 10.0  # Initial fallback delay if datadog does not return a delay
    max_delay = 60.0  # Max delay if datadog does not return a reset_time

    while cursor and len(logs) < limit:
        payload["page"]["cursor"] = cursor
        try: 
            new_logs, cursor = _execute_logs_query(url=url, headers=headers, payload=payload, timeout=dd_config.request_timeout)
            logs += new_logs
            retry_count = 0
            payload["page"]["limit"] = calculate_page_size(params, dd_config, logs)
        except DataDogRequest429Error as e:
            retry_count += 1
            if retry_count >= 3:
                # Don't retry eternally
                raise e
            wait_time = min(base_delay * (2 ** (retry_count - 1)), max_delay)
            if e.reset_time:
                wait_time = max(0, e.reset_time) + 0.1

            logging.warning(f"DataDog logs toolset is rate limited/throttled. Waiting {wait_time:.1f}s until reset time")
            time.sleep(wait_time)

    if len(logs) > limit:
        logs = logs[-limit:]
    return logs

def format_logs(raw_logs:list[dict]) -> str:
    logs = []

    for raw_log_item in raw_logs:
        message = raw_log_item.get("attributes", {}).get("message", json.dumps(raw_log_item))
        logs.append(message)
        
    return "\n".join(logs)


class DatadogToolset(BasePodLoggingToolset):
    dd_config: Optional[DatadogConfig] = None

    def __init__(self):
        super().__init__(
            name="datadog/logs",
            description="Toolset for interacting with Datadog to fetch logs",
            docs_url="https://docs.datadoghq.com/api/latest/logs/",
            icon_url="https://imgix.datadoghq.com//img/about/presskit/DDlogo.jpg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                PodLoggingTool(self),
            ],
            experimental=True,
            tags=[ToolsetTag.CORE],
        )

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:

        if not self.dd_config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=TOOLSET_CONFIG_MISSING_ERROR,
                params=params.model_dump(),
            )

        try:
            raw_logs = []
            for storage_tier in self.dd_config.storage_tiers:
                raw_logs = fetch_paginated_logs(params, self.dd_config, storage_tier=storage_tier)

                if raw_logs:
                    # no need to try other storage tiers if the current one returned data
                    break
            
            if raw_logs:

                logs_str = format_logs(raw_logs)
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=logs_str,
                    params=params.model_dump(),
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.NO_DATA,
                    params=params.model_dump(),
                )

        except DataDogRequestError as e:
            logging.exception(e, exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception while querying Datadog: {str(e)}",
                params=params.model_dump(),
                invocation=json.dumps(e.payload)
            )

        except Exception as e:
            logging.exception(f"Failed to query Datadog logs for params: {params}", exc_info=True)
        
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
                start_time="-172800"  # 48 hours in seconds
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
                "Datadog toolset is misconfigured. 'dd_api_key' and 'dd_app_key' are required.",
            )

        try:
            dd_config = DatadogConfig(**config)
            if not dd_config.storage_tiers:
                dd_config.storage_tiers = DEFAULT_STORAGE_TIERS
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
            "indexes": ["main", "*"],
            "storage_tiers": ["indexes", "online-archives"],
            "labels": {
                "pod": "pod_name",
                "namespace": "kube_namespace"
            },
            "page_size": 300,
            "default_limit": 1000,
            "request_timeout": 60
        }
