import logging
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Tuple, Set
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
    LoggingCapability,
    LoggingConfig,
    PodLoggingTool,
)
from holmes.plugins.toolsets.logging_utils.shared_log_utils import (
    StructuredLog,
    filter_logs,
    format_logs_with_containers,
    add_log_metadata,
)
from holmes.plugins.toolsets.utils import to_unix_ms


# match ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.fffffffff]Z) or (YYYY-MM-DDTHH:MM:SS[.fffffffff]+/-XX:XX)
timestamp_pattern = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))"
)


class Pod(BaseModel):
    containers: list[str]


class LogResult(BaseModel):
    error: Optional[str]
    return_code: Optional[int]
    has_multiple_containers: bool
    logs: list[StructuredLog]


class KubernetesLogsToolset(BasePodLoggingToolset):
    """Implementation of the unified logging API for Kubernetes logs using kubectl commands"""

    @property
    def supported_capabilities(self) -> Set[LoggingCapability]:
        """Kubernetes native logging supports regex and exclude filters"""
        return {
            LoggingCapability.REGEX_FILTER,
            LoggingCapability.EXCLUDE_FILTER,
        }

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

            # Fetch previous and current logs in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_previous = executor.submit(
                    self._fetch_kubectl_logs, params, previous=True
                )
                future_current = executor.submit(
                    self._fetch_kubectl_logs, params, previous=False
                )

                futures = {future_previous: "previous", future_current: "current"}
                previous_logs_result = None
                current_logs_result = None

                for future in as_completed(futures):
                    log_type = futures[future]
                    try:
                        result = future.result()
                        if log_type == "previous":
                            previous_logs_result = result
                        else:
                            current_logs_result = result
                    except Exception as e:
                        logging.error(f"Error fetching {log_type} logs: {str(e)}")
                        error_result = LogResult(
                            logs=[],
                            error=f"Error fetching {log_type} logs: {str(e)}",
                            return_code=None,
                            has_multiple_containers=False,
                        )
                        if log_type == "previous":
                            previous_logs_result = error_result
                        else:
                            current_logs_result = error_result

            # Ensure both results are not None (they should always be set by the loop)
            if current_logs_result is None or previous_logs_result is None:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Internal error: Failed to fetch logs",
                    params=params.model_dump(),
                )

            return_code: Optional[int] = current_logs_result.return_code

            if previous_logs_result.logs:
                all_logs.extend(previous_logs_result.logs)
                return_code = previous_logs_result.return_code

            if current_logs_result.logs:
                all_logs.extend(current_logs_result.logs)
                return_code = current_logs_result.return_code

            if (
                not all_logs
                and previous_logs_result.error
                and current_logs_result.error
            ):
                # Both commands failed - return error from current logs
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=current_logs_result.error,
                    params=params.model_dump(),
                    return_code=return_code,
                )

            # Track counts for metadata
            total_count = len(all_logs)
            (
                filtered_logs,
                filtered_count_before_limit,
                used_substring_fallback,
                exclude_used_substring_fallback,
                removed_by_include_filter,
                removed_by_exclude_filter,
            ) = filter_logs(all_logs, params)

            has_multiple_containers = (
                previous_logs_result.has_multiple_containers
                or current_logs_result.has_multiple_containers
            )

            formatted_logs = format_logs_with_containers(
                logs=filtered_logs,
                display_container_name=has_multiple_containers,
            )

            # Generate metadata
            metadata_lines = add_log_metadata(
                params=params,
                total_count=total_count,
                filtered_logs=filtered_logs,
                filtered_count_before_limit=filtered_count_before_limit,
                used_substring_fallback=used_substring_fallback,
                exclude_used_substring_fallback=exclude_used_substring_fallback,
                removed_by_include_filter=removed_by_include_filter,
                removed_by_exclude_filter=removed_by_exclude_filter,
                has_multiple_containers=has_multiple_containers,
                provider_name="Kubernetes (kubectl)",
            )

            # Check if we have any logs to return
            if len(filtered_logs) == 0:
                # Return NO_DATA status when there are no logs
                return StructuredToolResult(
                    status=ToolResultStatus.NO_DATA,
                    data="\n".join(
                        metadata_lines
                    ),  # Still include metadata for context
                    params=params.model_dump(),
                    return_code=return_code,
                )

            # Put metadata at the end
            response_data = formatted_logs + "\n" + "\n".join(metadata_lines)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=response_data,
                params=params.model_dump(),
                return_code=return_code,
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
    ) -> LogResult:
        """Fetch logs using kubectl command"""
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
                log_result = self._parse_kubectl_logs(logs=result.stdout)
                log_result.return_code = result.returncode
                return log_result
            else:
                error_msg = (
                    result.stdout.strip()
                    or f"kubectl logs command failed with return code {result.returncode}"
                )
                logging.debug(
                    f"kubectl logs command failed for pod {params.pod_name} "
                    f"(previous={previous}): {error_msg}"
                )
                return LogResult(
                    logs=[],
                    error=error_msg,
                    return_code=result.returncode,
                    has_multiple_containers=False,
                )

        except subprocess.TimeoutExpired:
            error_msg = f"kubectl logs command timed out after {KUBERNETES_LOGS_TIMEOUT_SECONDS} seconds"
            logging.warning(
                f"kubectl logs command timed out for pod {params.pod_name} "
                f"(previous={previous})"
            )
            return LogResult(
                logs=[],
                error=error_msg,
                return_code=None,
                has_multiple_containers=False,
            )
        except Exception as e:
            error_msg = f"Error executing kubectl: {str(e)}"
            logging.error(
                f"Error executing kubectl logs for pod {params.pod_name} "
                f"(previous={previous}): {str(e)}"
            )
            return LogResult(
                logs=[],
                error=error_msg,
                return_code=None,
                has_multiple_containers=False,
            )

    def _parse_kubectl_logs(self, logs: str) -> LogResult:
        """Parse kubectl logs output with container prefixes"""
        structured_logs: List[StructuredLog] = []

        if not logs:
            return LogResult(
                logs=structured_logs,
                error=None,
                return_code=None,
                has_multiple_containers=False,
            )

        has_multiple_containers = False

        previous_container: Optional[str] = None

        for line in logs.strip().split("\n"):
            if not line:
                continue

            # kubectl with --all-containers prefixes lines with [pod/container]
            # Format: [pod/container] timestamp content
            container_match = re.match(r"^\[([^/]+)/([^\]]+)\] (.*)$", line)

            if container_match:
                pod_name, container_name, rest_of_line = container_match.groups()

                if not has_multiple_containers and not previous_container:
                    previous_container = container_name
                elif (
                    not has_multiple_containers and previous_container != container_name
                ):
                    has_multiple_containers = True

                # Now extract timestamp from rest_of_line
                timestamp_match = timestamp_pattern.match(rest_of_line)

                if timestamp_match:
                    timestamp_str = timestamp_match.group(0)
                    try:
                        log_unix_ts = to_unix_ms(timestamp_str)
                        prefix_length = len(timestamp_str)
                        content = rest_of_line[prefix_length:]
                        # Remove only the single space after timestamp, preserve other whitespaces to
                        #   keep the indentations of the original logs
                        if content.startswith(" "):
                            content = content[1:]

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

        return LogResult(
            logs=structured_logs,
            error=None,
            return_code=None,
            has_multiple_containers=has_multiple_containers,
        )


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
                    # Remove only the single space after timestamp, preserve other whitespace
                    line_content = log_line[prefix_length:]
                    if line_content.startswith(" "):
                        line_content = line_content[1:]
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
