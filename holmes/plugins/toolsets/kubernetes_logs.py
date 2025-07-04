import logging
import re
import subprocess
from typing import Optional, List, Tuple
from pydantic import BaseModel

from holmes.common.env_vars import KUBERNETES_LOGS_TIMEOUT_SECONDS
from holmes.core.tools import (
    StaticPrerequisite,
    StructuredToolResult,
    ToolResultStatus,
    ToolsetTag,
)
from holmes.plugins.toolsets.logging_utils.logging_api import (
    BasePodLoggingToolset,
    FetchPodLogsParams,
    LoggingConfig,
    PodLoggingTool,
)
from holmes.plugins.toolsets.utils import process_timestamps_to_int, to_unix_ms


# match ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.fffffffff]Z) or (YYYY-MM-DDTHH:MM:SS[.fffffffff]+/-XX:XX)
timestamp_pattern = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))"
)


class Pod(BaseModel):
    containers: list[str]


class StructuredLog(BaseModel):
    timestamp_ms: Optional[int]
    container: Optional[str]
    content: str


class KubernetesLogsToolset(BasePodLoggingToolset):
    """Implementation of the unified logging API for Kubernetes logs using kubectl commands"""

    def __init__(self):
        prerequisite = StaticPrerequisite(enabled=False, disabled_reason="Initializing")
        super().__init__(
            name="kubernetes/logs",
            description="Read Kubernetes pod logs using a unified API",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/kubernetes.html#logs",
            icon_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRPKA-U9m5BxYQDF1O7atMfj9EMMXEoGu4t0Q&s",
            prerequisites=[prerequisite],
            is_default=True,
            tools=[
                PodLoggingTool(self),
            ],
            tags=[ToolsetTag.CORE],
        )
        enabled, disabled_reason = self.health_check()
        prerequisite.enabled = enabled
        prerequisite.disabled_reason = disabled_reason

    def health_check(self) -> Tuple[bool, str]:
        try:
            # Check if kubectl is available
            result = subprocess.run(
                ["kubectl", "version", "--client"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, ""
            else:
                return False, f"kubectl command failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "kubectl command timed out"
        except FileNotFoundError:
            return False, "kubectl command not found"
        except Exception as e:
            return False, f"kubectl health check error: {str(e)}"

    def get_example_config(self):
        return LoggingConfig().model_dump()

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        try:
            all_logs: list[StructuredLog] = []

            # Fetch previous logs
            logs_previous, error_previous = self._fetch_kubectl_logs(
                params=params,
                previous=True,
            )

            # Fetch current logs
            logs_current, error_current = self._fetch_kubectl_logs(
                params=params,
                previous=False,
            )

            # Combine logs
            if logs_previous:
                all_logs.extend(logs_previous)
            if logs_current:
                all_logs.extend(logs_current)

            # Check if both commands failed
            if not all_logs and error_current and error_previous:
                # Both commands failed - return error from current logs
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=error_current,
                    params=params.model_dump(),
                )

            # If we have no logs but no errors, it means the pod exists but has no logs
            if not all_logs:
                return StructuredToolResult(
                    status=ToolResultStatus.NO_DATA,
                    params=params.model_dump(),
                )

            # Filter logs based on parameters
            all_logs = filter_logs(all_logs, params)

            # Check if there are multiple containers
            containers = set(log.container for log in all_logs if log.container)
            multi_containers = len(containers) > 1

            # Format logs
            formatted_logs = format_logs(
                logs=all_logs, display_container_name=multi_containers
            )

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS
                if formatted_logs
                else ToolResultStatus.NO_DATA,
                data=formatted_logs,
                params=params.model_dump(),
            )
        except Exception as e:
            logging.exception(f"Error fetching logs for pod {params.pod_name}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching logs: {str(e)}",
                params=params.model_dump(),
            )

    def _fetch_kubectl_logs(
        self,
        params: FetchPodLogsParams,
        previous: bool = False,
    ) -> Tuple[List[StructuredLog], Optional[str]]:
        """Fetch logs using kubectl command

        Returns:
            Tuple of (logs, error_message)
        """
        cmd = [
            "kubectl",
            "logs",
            params.pod_name,
            "-n",
            params.namespace,
            "--all-containers=true",
            "--timestamps=true",
            "--prefix=true",
        ]

        if previous:
            cmd.append("--previous")

        try:
            result = subprocess.run(
                cmd,
                text=True,
                timeout=KUBERNETES_LOGS_TIMEOUT_SECONDS,
                check=False,  # do not throw error, we just return the error code
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            if result.returncode == 0:
                # Parse the logs - kubectl with --all-containers prefixes lines with container name
                return self._parse_kubectl_logs(result.stdout), None
            else:
                # Return error message
                error_msg = (
                    result.stdout.strip()
                    or f"kubectl logs command failed with return code {result.returncode}"
                )
                logging.debug(
                    f"kubectl logs command failed for pod {params.pod_name} "
                    f"(previous={previous}): {error_msg}"
                )
                return [], error_msg

        except subprocess.TimeoutExpired:
            error_msg = f"kubectl logs command timed out after {KUBERNETES_LOGS_TIMEOUT_SECONDS} seconds"
            logging.warning(
                f"kubectl logs command timed out for pod {params.pod_name} "
                f"(previous={previous})"
            )
            return [], error_msg
        except Exception as e:
            error_msg = f"Error executing kubectl: {str(e)}"
            logging.error(
                f"Error executing kubectl logs for pod {params.pod_name} "
                f"(previous={previous}): {str(e)}"
            )
            return [], error_msg

    def _parse_kubectl_logs(self, logs: str) -> List[StructuredLog]:
        """Parse kubectl logs output with container prefixes"""
        structured_logs: List[StructuredLog] = []

        if not logs:
            return structured_logs

        for line in logs.strip().split("\n"):
            if not line:
                continue

            # kubectl with --all-containers prefixes lines with [pod/container]
            # Format: [pod/container] timestamp content
            container_match = re.match(r"^\[([^/]+)/([^\]]+)\]\s+(.*)$", line)

            if container_match:
                pod_name, container_name, rest_of_line = container_match.groups()

                # Now extract timestamp from rest_of_line
                timestamp_match = timestamp_pattern.match(rest_of_line)

                if timestamp_match:
                    timestamp_str = timestamp_match.group(0)
                    try:
                        log_unix_ts = to_unix_ms(timestamp_str)
                        prefix_length = len(timestamp_str)
                        content = rest_of_line[prefix_length:].lstrip()

                        structured_logs.append(
                            StructuredLog(
                                timestamp_ms=log_unix_ts,
                                content=content,
                                container=container_name,
                            )
                        )
                    except ValueError:
                        # Keep the line with container info but no timestamp
                        structured_logs.append(
                            StructuredLog(
                                timestamp_ms=None,
                                content=rest_of_line,
                                container=container_name,
                            )
                        )
                else:
                    # No timestamp but has container info
                    structured_logs.append(
                        StructuredLog(
                            timestamp_ms=None,
                            content=rest_of_line,
                            container=container_name,
                        )
                    )
            else:
                # No container prefix - parse as regular log line
                parsed = parse_logs(line, None)
                structured_logs.extend(parsed)

        return structured_logs


def format_logs(logs: List[StructuredLog], display_container_name: bool) -> str:
    if display_container_name:
        return "\n".join([f"{log.container or 'N/A'}: {log.content}" for log in logs])
    else:
        return "\n".join([log.content for log in logs])


class TimeFilter(BaseModel):
    start_ms: int
    end_ms: int


def filter_logs(
    logs: List[StructuredLog], params: FetchPodLogsParams
) -> List[StructuredLog]:
    time_filter: Optional[TimeFilter] = None
    if params.start_time or params.end_time:
        start, end = process_timestamps_to_int(
            start=params.start_time,
            end=params.end_time,
            default_time_span_seconds=3600,
        )
        time_filter = TimeFilter(start_ms=start * 1000, end_ms=end * 1000)

    filtered_logs = []
    logs.sort(key=lambda x: x.timestamp_ms or 0)

    for log in logs:
        if params.filter and params.filter.lower() not in log.content.lower():
            # exclude this log
            continue

        if (
            time_filter
            and log.timestamp_ms
            and (
                log.timestamp_ms
                < time_filter.start_ms  # log is before expected time range
                or time_filter.end_ms
                < log.timestamp_ms  # log is after expected time range
            )
        ):
            # exclude this log
            continue
        else:
            filtered_logs.append(log)

    if params.limit and params.limit < len(filtered_logs):
        filtered_logs = filtered_logs[-params.limit :]
    return filtered_logs


def parse_logs(
    logs: Optional[str], container_name: Optional[str]
) -> list[StructuredLog]:
    structured_logs = []
    if logs:
        for log_line in logs.strip().split("\n"):
            if not isinstance(log_line, str):
                # defensive code given logs are from an external API
                structured_logs.append(
                    StructuredLog(
                        timestamp_ms=None,
                        content=str(log_line),
                        container=container_name,
                    )
                )
                continue
            match = timestamp_pattern.match(log_line)
            if match:
                timestamp_str = match.group(0)
                try:
                    log_unix_ts = to_unix_ms(timestamp_str)
                    prefix_length = len(timestamp_str)
                    line_content = log_line[prefix_length:].lstrip()
                    structured_logs.append(
                        StructuredLog(
                            timestamp_ms=log_unix_ts,
                            content=line_content,
                            container=container_name,
                        )
                    )

                except ValueError:
                    # For invalid timestamp formats (when regex matches but date parsing fails)
                    # keep the original line - this is important for testing and consistency
                    structured_logs.append(
                        StructuredLog(
                            timestamp_ms=None,
                            content=log_line,
                            container=container_name,
                        )
                    )
            elif len(structured_logs) > 0:
                # if a line has no timestamp, assume it is part of a previous line
                structured_logs[-1].content += "\n" + log_line
            else:
                structured_logs.append(
                    StructuredLog(
                        timestamp_ms=None, content=log_line, container=container_name
                    )
                )
    return structured_logs
