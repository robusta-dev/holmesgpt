import logging
import re
from typing import Dict, Optional, List, Any, Tuple

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    ToolResultStatus,
    ToolsetTag,
)
from holmes.plugins.toolsets.logging_api import (
    BaseLoggingToolset,
    LoggingTool,
    DEFAULT_LOG_LIMIT,
    process_time_parameters,
)


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
        return {}

    def _initialize_client(self):
        """Initialize the Kubernetes API client if not already initialized"""
        if not self._api_client:
            try:
                # Load either in-cluster config or kubeconfig file
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()

                self._api_client = client.ApiClient()
                self._core_v1_api = client.CoreV1Api(self._api_client)
            except Exception as e:
                logging.error(f"Failed to initialize Kubernetes client: {e}")
                raise

    def fetch_logs(
        self,
        namespace: str,
        pod_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        filter_pattern: Optional[str] = None,
        limit: int = DEFAULT_LOG_LIMIT,
    ) -> StructuredToolResult:
        if not namespace or not pod_name:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameters: namespace and pod_name",
            )

        try:
            self._initialize_client()

            pod = self._get_pod(namespace, pod_name)
            if not pod:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Pod {pod_name} not found in namespace {namespace}",
                )

            # Get container names
            containers = [container.name for container in pod.spec.containers]
            if not containers:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Pod {pod_name} has no containers",
                )

            # Process time parameters
            processed_start_time, processed_end_time = process_time_parameters(
                start_time, end_time
            )

            # Kubernetes API doesn't directly support complex time-based filtering,
            # so we'll fetch all logs and do any additional filtering ourselves

            all_logs = []

            # Fetch logs for each container, try current logs first then previous if none found
            for container_name in containers:
                container_logs = []

                # Try to get current logs first
                current_logs = self._fetch_container_logs(
                    namespace,
                    pod_name,
                    container_name,
                    previous=False,
                    timestamp=False,  # We don't include timestamps by default
                    # Pass limit as tail_lines to match kubectl behavior
                    tail_lines=limit if limit and limit > 0 else None,
                )

                # If no current logs found, try to get logs from previous container
                if not current_logs:
                    container_logs = self._fetch_container_logs(
                        namespace,
                        pod_name,
                        container_name,
                        previous=True,
                        timestamp=False,
                        # Pass limit as tail_lines to match kubectl behavior
                        tail_lines=limit if limit and limit > 0 else None,
                    )
                else:
                    container_logs = current_logs

                # Add container name prefix only for multi-container pods
                # This matches kubectl behavior
                if len(containers) > 1:
                    container_logs = [
                        f"{container_name}: {log}" for log in container_logs
                    ]

                all_logs.extend(container_logs)

            # Filter by pattern if provided
            if filter_pattern:
                all_logs = self._filter_logs(all_logs, filter_pattern)

            # Apply limit
            if limit and limit < len(all_logs):
                all_logs = all_logs[-limit:]

            # Format output
            formatted_logs = self._format_logs(all_logs)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=formatted_logs,
                params={
                    "namespace": namespace,
                    "pod_name": pod_name,
                    "containers": containers,
                    "start_time": processed_start_time,
                    "end_time": processed_end_time,
                    "filter": filter_pattern,
                    "limit": limit,
                },
            )
        except ApiException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Kubernetes API error: {str(e)}",
            )
        except Exception as e:
            logging.exception(f"Error fetching logs for pod {pod_name}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching logs: {str(e)}",
            )

    def _get_pod(self, namespace: str, pod_name: str):
        """Get pod details"""
        try:
            return self._core_v1_api.read_namespaced_pod(
                name=pod_name, namespace=namespace
            )
        except ApiException as e:
            if e.status == 404:
                # Pod not found
                return None
            else:
                # Other API error
                raise
        except Exception:
            logging.exception(f"Error getting pod {pod_name}")
            raise

    def _fetch_container_logs(
        self,
        namespace: str,
        pod_name: str,
        container_name: str,
        previous: bool = False,
        timestamp: bool = False,
        since_time: Optional[str] = None,
        tail_lines: Optional[int] = None,
    ) -> List[str]:
        """Fetch logs for a specific container in a pod"""
        try:
            # Build parameters the way kubectl would
            params = {
                "name": pod_name,
                "namespace": namespace,
                "container": container_name,
                "previous": previous,
                "timestamps": timestamp,
            }

            # Add optional parameters if provided
            if since_time:
                params["since_seconds"] = since_time

            if tail_lines is not None:
                params["tail_lines"] = tail_lines

            logs = self._core_v1_api.read_namespaced_pod_log(**params)

            if logs:
                # Split logs by newline but filter out empty lines
                return [line for line in logs.strip().split("\n") if line]
            return []
        except ApiException as e:
            if e.status == 400 and "previous terminated container" in str(e).lower():
                # Normal error when no previous logs exist
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
