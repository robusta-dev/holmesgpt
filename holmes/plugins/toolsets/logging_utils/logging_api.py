from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
from typing import Optional

from pydantic import BaseModel
from datetime import timezone
from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    Toolset,
)
from holmes.plugins.toolsets.utils import get_param_or_raise

# Default values for log fetching
DEFAULT_LOG_LIMIT = 2000
DEFAULT_TIME_SPAN_SECONDS = 3600


class LoggingConfig(BaseModel):
    """Base configuration for all logging backends"""

    pass


class FetchPodLogsParams(BaseModel):
    namespace: str
    pod_name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    filter: Optional[str] = None
    limit: Optional[int] = None


class BasePodLoggingToolset(Toolset, ABC):
    """Base class for all logging toolsets"""

    @abstractmethod
    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        pass


class PodLoggingTool(Tool):
    """Common tool for fetching pod logs across different logging backends"""

    def __init__(self, toolset: BasePodLoggingToolset):
        super().__init__(
            name="fetch_pod_logs",
            description="Fetch logs for a Kubernetes pod",
            parameters={
                "pod_name": ToolParameter(
                    description="The exact kubernetes pod name",
                    type="string",
                    required=True,
                ),
                "namespace": ToolParameter(
                    description="Kubernetes namespace", type="string", required=True
                ),
                "start_time": ToolParameter(
                    description="Start time for logs. Can be an RFC3339 formatted timestamp (e.g. '2023-03-01T10:30:00Z') for absolute time or a negative integer (e.g. -3600) for relative seconds before end_time.",
                    type="string",
                    required=False,
                ),
                "end_time": ToolParameter(
                    description="End time for logs. Must be an RFC3339 formatted timestamp (e.g. '2023-03-01T12:30:00Z'). If not specified, defaults to current time.",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of logs to return",
                    type="integer",
                    required=False,
                ),
                "filter": ToolParameter(
                    description="An optional keyword or sentence to filter the logs",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: dict) -> StructuredToolResult:
        structured_params = FetchPodLogsParams(
            namespace=get_param_or_raise(params, "namespace"),
            pod_name=get_param_or_raise(params, "pod_name"),
            start_time=params.get("start_time"),
            end_time=params.get("end_time"),
            filter=params.get("filter"),
            limit=params.get("limit"),
        )

        result = self._toolset.fetch_pod_logs(
            params=structured_params,
        )

        return result

    def get_parameterized_one_liner(self, params: dict) -> str:
        """Generate a one-line description of this tool invocation"""
        namespace = params.get("namespace", "unknown-namespace")
        pod_name = params.get("pod_name", "unknown-pod")
        return f"Fetching logs for pod {pod_name} in namespace {namespace}"


def process_time_parameters(
    start_time: Optional[str],
    end_time: Optional[str],
    default_span_seconds: int = DEFAULT_TIME_SPAN_SECONDS,
) -> tuple[Optional[str], Optional[str]]:
    """
    Convert time parameters to standard RFC3339 format

    Args:
        start_time: Either RFC3339 timestamp or negative integer (seconds before end)
        end_time: RFC3339 timestamp or None (defaults to now)
        default_span_seconds: Default time span if start_time not provided

    Returns:
        Tuple of (start_time, end_time) both in RFC3339 format or None
    """
    # Process end time first (as start might depend on it)
    now = datetime.now(timezone.utc)

    # Handle end_time
    processed_end_time = None
    if end_time:
        try:
            # Check if it's already in RFC3339 format
            processed_end_time = end_time
            datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            # If not a valid RFC3339, log the error and use current time
            logging.warning(f"Invalid end_time format: {end_time}, using current time")
            processed_end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        # Default to current time
        processed_end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Handle start_time
    processed_start_time = None
    if start_time:
        try:
            # Check if it's a negative integer (relative time)
            if isinstance(start_time, int) or (
                isinstance(start_time, str)
                and start_time.startswith("-")
                and start_time[1:].isdigit()
            ):
                # Convert to seconds before end_time
                seconds_before = abs(int(start_time))

                # Parse end_time
                if processed_end_time:
                    end_datetime = datetime.fromisoformat(
                        processed_end_time.replace("Z", "+00:00")
                    )
                else:
                    end_datetime = now

                # Calculate start_time
                start_datetime = end_datetime - timedelta(seconds=seconds_before)
                processed_start_time = start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                # Assume it's RFC3339
                processed_start_time = start_time
                datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            # If not a valid format, use default
            logging.warning(
                f"Invalid start_time format: {start_time}, using default time span"
            )
            if processed_end_time:
                end_datetime = datetime.fromisoformat(
                    processed_end_time.replace("Z", "+00:00")
                )
            else:
                end_datetime = now

            start_datetime = end_datetime - timedelta(seconds=default_span_seconds)
            processed_start_time = start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        # Default to default_span_seconds before end_time
        if processed_end_time:
            end_datetime = datetime.fromisoformat(
                processed_end_time.replace("Z", "+00:00")
            )
        else:
            end_datetime = now

        start_datetime = end_datetime - timedelta(seconds=default_span_seconds)
        processed_start_time = start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")

    return processed_start_time, processed_end_time
