import logging
import re
from typing import Optional, List, Any, Tuple
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel

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
    """Implementation of the unified logging API for Kubernetes logs using the official Python client"""

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
        self._api_client = None
        self._core_v1_api = None
        self._initialize_client()
        enabled, disabled_reason = self.health_check()
        prerequisite.enabled = enabled
        prerequisite.disabled_reason = disabled_reason

    def health_check(self) -> Tuple[bool, str]:
        if self._api_client is None:
            return False, "Kubernetes client not initialized"
        try:
            # Try to load the kubeconfig and access the API
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
        return LoggingConfig().model_dump()

    def _initialize_client(self):
        try:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                logging.debug(
                    f"_initialize_client for {self.name} toolset falling back to loading kube_config"
                )
                config.load_kube_config()

            self._api_client = client.ApiClient()
            self._core_v1_api = client.CoreV1Api(self._api_client)
        except Exception:
            logging.error("Failed to initialize Kubernetes client", exc_info=True)

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        try:
            multi_containers: bool = False
            pod = self._find_pod(params.namespace, params.pod_name)
            all_logs: list[StructuredLog] = []
            multi_containers_previous = False
            logs_previous: list[StructuredLog] = []
            try:
                multi_containers_previous, logs_previous = self._fetch_pod_logs(
                    params=params,
                    containers=pod.containers if pod else None,
                    previous=True,
                )
            except Exception:
                # previous logs can fail for a number of reason, for example if the previous pod does not have the same containers as the current one
                pass

            multi_containers_current, logs_current = self._fetch_pod_logs(
                params=params,
                containers=pod.containers if pod else None,
                previous=False,
            )

            if logs_previous:
                multi_containers = multi_containers or multi_containers_previous
                all_logs = all_logs + logs_previous
            if logs_current:
                multi_containers = multi_containers or multi_containers_current
                all_logs = all_logs + logs_current

            all_logs = filter_logs(all_logs, params)

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
        except ApiException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Kubernetes API error: {str(e)}",
                params=params.model_dump(),
            )
        except Exception as e:
            logging.exception(f"Error fetching logs for pod {params.pod_name}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching logs: {str(e)}",
                params=params.model_dump(),
            )

    def _find_pod(self, namespace: str, pod_name: str) -> Optional[Pod]:
        if not self._core_v1_api:
            logging.warning(f"Toolset {self.name} failed to initialize.")
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
        params: FetchPodLogsParams,
        containers: Optional[List[str]] = None,
        previous: bool = False,
    ) -> tuple[bool, list[StructuredLog]]:
        pod_logs = []
        multi_container = False
        if containers:
            if len(containers) > 1:
                multi_container = True
            # Fetch logs for each container, try current logs first then previous if none found
            for container_name in containers:
                container_logs = self._fetch_logs_from_kubernetes(
                    params=params,
                    container_name=container_name,
                    previous=previous,
                )

                pod_logs.extend(container_logs)

        if not pod_logs:
            # Previous pods may have had different containers
            # fall back to fetching the 'default' pod logs in a attempt to be as resilient as possible
            pod_logs = self._fetch_logs_from_kubernetes(
                params=params,
                previous=previous,
            )

        return multi_container, pod_logs

    def _fetch_logs_from_kubernetes(
        self,
        params: FetchPodLogsParams,
        container_name: Optional[str] = None,
        previous: bool = False,
    ) -> List[StructuredLog]:
        """Fetch logs for a specific container in a pod"""
        if not self._core_v1_api:
            logging.warning(f"Toolset {self.name} failed to initialize.")
            return []

        query_params = {
            "name": params.pod_name,
            "namespace": params.namespace,
            "previous": previous,
            "timestamps": True,
        }
        try:
            if container_name:
                query_params["container"] = container_name

            logs = self._core_v1_api.read_namespaced_pod_log(**query_params)
            return parse_logs(logs, container_name)
        except ApiException as e:
            logs = []
            if e.body and e.body:
                logs.append(
                    StructuredLog(
                        timestamp_ms=None, container=container_name, content=e.body
                    )
                )
            if e.status == 400 and "previous terminated container" in str(e).lower():
                return logs
            elif (
                e.status == 400
                and "a container name must be specified for pod" in str(e).lower()
            ):
                # disregard this because we first try to explicitely fetch logs for all containers and only
                # if there is no result do we not request logs for a specific container
                return logs
            elif e.status == 400 and "is waiting to start" in str(e).lower():
                return logs
            elif e.status == 404:
                return logs
            else:
                logging.warning(
                    f"API error fetching logs. params={query_params}. Error: {str(e)}"
                )
                raise e
        except Exception as e:
            logging.error(
                f"Error fetching logs. params={query_params}. Error: {str(e)}"
            )
            raise


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
