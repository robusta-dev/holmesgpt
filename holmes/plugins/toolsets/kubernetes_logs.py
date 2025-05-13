import logging
import re
from typing import Dict, Optional, List, Any, Tuple
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    ToolResultStatus,
    ToolsetTag,
)
from holmes.plugins.toolsets.logging_api import (
    BaseLoggingToolset,
    FetchLogsParams,
    LoggingTool,
)
from holmes.plugins.toolsets.utils import process_timestamps_to_int, to_unix


class Pod(BaseModel):
    containers: list[str]


class KubernetesLogsToolset(BaseLoggingToolset):
    """Implementation of the unified logging API for Kubernetes logs using the official Python client"""

    def __init__(self):
        super().__init__(
            name="kubernetes/logs",
            description="Read Kubernetes pod logs using a unified API",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/kubernetes.html#logs",
            icon_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRPKA-U9m5BxYQDF1O7atMfj9EMMXEoGu4t0Q&s",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                LoggingTool(self),
            ],
            tags=[ToolsetTag.CORE],
        )
        self._api_client = None
        self._core_v1_api = None

    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify Kubernetes client can connect to the cluster"""
        try:
            # TODO: support API KEY / BearerToken
            # Try to load the kubeconfig and access the API
            self._initialize_client()
            self._api_client.call_api(
                "/version",
                "GET",
                auth_settings=["BearerToken"],
                response_type="object",
                _return_http_data_only=True,
            )
            return True, ""
        except Exception as e:
            return False, f"Kubernetes client initialization error: {str(e)}"

    def get_example_config(self):
        # TODO: implement
        return {}

    def _initialize_client(self):
        if not self._api_client:
            try:
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()

                self._api_client = client.ApiClient()
                self._core_v1_api = client.CoreV1Api(self._api_client)
            except Exception:
                logging.error("Failed to initialize Kubernetes client", exc_info=True)
                raise

    def fetch_logs(self, params: FetchLogsParams) -> StructuredToolResult:
        try:
            self._initialize_client()

            pod = self._find_pod(params.namespace, params.pod_name)
            all_logs = []
            if not pod or not pod.containers:
                all_logs = self._fetch_pod_logs(
                    params=params, previous=True
                ) + self._fetch_pod_logs(params=params, previous=False)
            else:
                all_logs = self._fetch_pod_logs(
                    params=params, containers=pod.containers, previous=True
                )
                all_logs = all_logs + self._fetch_pod_logs(
                    params=params, containers=pod.containers, previous=False
                )

            if params.filter_pattern:
                all_logs = self._filter_logs(all_logs, params.filter_pattern)

            if params.limit and params.limit < len(all_logs):
                all_logs = all_logs[-params.limit :]

            # Format output
            formatted_logs = self._format_logs(all_logs)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=formatted_logs,
                params=params.model_dump(),
            )
        except ApiException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Kubernetes API error: {str(e)}",
            )
        except Exception as e:
            logging.exception(f"Error fetching logs for pod {params.pod_name}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching logs: {str(e)}",
            )

    def _find_pod(self, namespace: str, pod_name: str) -> Optional[Pod]:
        if not self._core_v1_api:
            return None
        try:
            pod: Any = self._core_v1_api.read_namespaced_pod(
                name=pod_name, namespace=namespace
            )
            return Pod(containers=[container.name for container in pod.spec.containers])
        except ApiException as e:
            if e.status == 404:
                return None
            else:
                raise
        except Exception:
            logging.exception(f"Error getting pod {pod_name}", exc_info=True)
            raise

    def _fetch_pod_logs(
        self,
        params: FetchLogsParams,
        containers: Optional[List[str]] = None,
        previous: bool = False,
    ) -> List[Any]:
        pod_logs = []
        if containers:
            # Fetch logs for each container, try current logs first then previous if none found
            for container_name in containers:
                container_logs = self._fetch_logs(
                    params=params,
                    container_name=container_name,
                    previous=previous,
                )

                # Add container name prefix only for multi-container pods
                # This matches kubectl behavior
                if len(containers) > 1:
                    container_logs = [
                        f"{container_name}: {log}" for log in container_logs
                    ]
                pod_logs.extend(container_logs)
        else:
            pod_logs = self._fetch_logs(
                params=params,
                previous=previous,
            )

        return pod_logs

    def _fetch_logs(
        self,
        params: FetchLogsParams,
        container_name: Optional[str] = None,
        previous: bool = False,
    ) -> List[str]:
        """Fetch logs for a specific container in a pod"""
        if not self._core_v1_api:
            return []
        try:
            filter_by_timestamps = False
            if params.start_time or params.end_time:
                filter_by_timestamps = True

            query_params = {
                "name": params.pod_name,
                "namespace": params.namespace,
                "previous": previous,
                "timestamps": filter_by_timestamps,
            }

            if container_name:
                query_params["container"] = container_name

            # Add optional parameters if provided
            if params.start_time:
                query_params["since_seconds"] = params.start_time

            logs = self._core_v1_api.read_namespaced_pod_log(**query_params)

            if logs:
                # Split logs by newline but filter out empty lines
                logs = [line for line in logs.strip().split("\n") if line]

                if filter_by_timestamps:
                    start, end = process_timestamps_to_int(
                        start=params.start_time,
                        end=params.end_time,
                        default_time_span_seconds=3600,
                    )
                    return filter_log_lines_by_timestamp_and_strip_prefix(
                        logs=logs, start_unix_timestamp=start, end_unix_timestamp=end
                    )
                else:
                    return logs

            return []
        except ApiException as e:
            if e.status == 400 and "previous terminated container" in str(e).lower():
                return []
            elif e.status != 404:  # Ignore 404 errors for previous logs
                logging.warning(
                    f"API error fetching logs for container {container_name}: {str(e)}"
                )
            return []
        except Exception as e:
            logging.warning(
                f"Error fetching logs for container {container_name}: {str(e)}"
            )
            return []

    def _filter_logs(self, logs: List[str], pattern: str) -> List[str]:
        """Filter logs by regex pattern"""
        try:
            regex = re.compile(pattern)
            return [log for log in logs if regex.search(log)]
        except re.error as e:
            logging.warning(f"Invalid regex pattern: {pattern}, error: {str(e)}")
            return logs  # Return unfiltered logs on regex error

    def _format_logs(self, logs: List[str]) -> str:
        """Format logs for output"""
        if not logs:
            return "No logs found"

        # Simple join without line numbers to match kubectl logs format
        return "\n".join([log for log in logs if log.strip()])


def filter_log_lines_by_timestamp_and_strip_prefix(
    logs: List[str], start_unix_timestamp: int, end_unix_timestamp: int
) -> List[str]:
    """
    Filters log lines based on their leading ISO 8601 timestamp, keeping lines
    within the specified start and end Unix timestamps (inclusive). Returns the
    filtered lines *without* the leading timestamp prefix.
    """
    # match ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.fffffffff]Z)
    timestamp_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z)")
    filtered_lines_content: List[str] = []

    for line in logs:
        # Non-string entries are passed through as-is
        if not isinstance(line, str):
            filtered_lines_content.append(line)
            continue

        match = timestamp_pattern.match(line)
        if match:
            timestamp_str = match.group(0)
            try:
                log_unix_ts = to_unix(timestamp_str)

                if start_unix_timestamp <= log_unix_ts <= end_unix_timestamp:
                    prefix_length = len(timestamp_str)
                    line_content = line[prefix_length:].lstrip()
                    filtered_lines_content.append(line_content)
            except ValueError:
                # For invalid timestamp formats (when regex matches but date parsing fails)
                # keep the original line - this is important for testing and consistency
                filtered_lines_content.append(line)
        else:
            filtered_lines_content.append(line)

    return filtered_lines_content
