import os
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from pydantic import ConfigDict, Field
from holmes.core.tools import (
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
    StructuredToolResult,
    ToolResultStatus,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Remove base tool class - inherit directly from Tool


class PromptParser:
    """Utility class to extract Kubernetes and duration information from user prompts
    Following the same patterns used by InfraInsights toolsets"""

    @staticmethod
    def extract_kube_cluster_name(prompt: str) -> Optional[str]:
        """Extract Kubernetes cluster name from prompt using various patterns"""
        if not prompt:
            return None

        # Enhanced patterns following InfraInsights conventions
        patterns = [
            # Specific name patterns with colons (highest priority)
            r'cluster_name[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'kube_cluster[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'kubernetes_cluster[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'cluster\s+name\s*(?:is\s*)?["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'clustername[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            # Direct mentions with service types
            r"([a-zA-Z0-9\-_]+)\s+kubernetes(?:\s+cluster)?",
            r"([a-zA-Z0-9\-_]+)\s+k8s(?:\s+cluster)?",
            # "my" patterns
            r"my\s+([a-zA-Z0-9\-_]+)(?:\s+(?:kubernetes|k8s|cluster))?",
            # Environment-based patterns
            r"([a-zA-Z0-9\-_]+)\s+environment",
            r"([a-zA-Z0-9\-_]+)\s+prod",
            r"([a-zA-Z0-9\-_]+)\s+staging",
            r"([a-zA-Z0-9\-_]+)\s+dev",
            r"([a-zA-Z0-9\-_]+)\s+test",
            # Generic patterns (lower priority)
            r"(?:in|from)\s+([a-zA-Z0-9\-_]+)\s+cluster",
            r"([a-zA-Z0-9\-_]+)\s+cluster",
            r"(?:instance|cluster|service)\s+([a-zA-Z0-9\-_]+)",
            r"([a-zA-Z0-9\-_]{3,})(?:\s+(?:instance|cluster|service))",
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1)
                # Skip common false positives
                if extracted.lower() in [
                    "kubernetes",
                    "k8s",
                    "cluster",
                    "instance",
                    "service",
                    "in",
                    "from",
                    "my",
                ]:
                    continue
                return extracted

        return None

    @staticmethod
    def extract_kube_deployment(prompt: str) -> Optional[str]:
        """Extract Kubernetes deployment name from prompt"""
        if not prompt:
            return None

        # Enhanced patterns following InfraInsights conventions
        patterns = [
            # Specific name patterns with keyword first (highest priority)
            r'deployment[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'service[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'pod[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'workload[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'container[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            # Direct mentions with resource types
            r"([a-zA-Z0-9\-_]+)\s+deployment",
            r"([a-zA-Z0-9\-_]+)\s+service",
            r"([a-zA-Z0-9\-_]+)\s+pod",
            r"([a-zA-Z0-9\-_]+)\s+workload",
            r"([a-zA-Z0-9\-_]+)\s+container",
            # "for" patterns
            r"for\s+([a-zA-Z0-9\-_]+)(?:\s+(?:deployment|service|pod|workload))?",
            r"traces?\s+for\s+([a-zA-Z0-9\-_]+)",
            r"logs?\s+for\s+([a-zA-Z0-9\-_]+)",
            # Service name patterns
            r"([a-zA-Z0-9\-_]+)-service",
            r"([a-zA-Z0-9\-_]+)-api",
            r"([a-zA-Z0-9\-_]+)-app",
            # Generic patterns (lower priority)
            r"([a-zA-Z0-9\-_]+)\s+traces",
            r"([a-zA-Z0-9\-_]+)\s+logs",
        ]

        # Try to find the most specific match first
        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1)
                # Skip common false positives
                if extracted.lower() in [
                    "deployment",
                    "service",
                    "pod",
                    "workload",
                    "container",
                    "traces",
                    "logs",
                    "for",
                    "in",
                    "from",
                    "get",
                    "show",
                    "fetch",
                    "display",
                    "retrieve",
                    "list",
                ]:
                    continue
                return extracted

        return None

    @staticmethod
    def extract_kube_pod_name(prompt: str) -> Optional[str]:
        """Extract Kubernetes pod name from prompt"""
        if not prompt:
            return None

        patterns = [
            r"pod:\s*([a-zA-Z0-9\-_]+)",
            r"pod_name:\s*([a-zA-Z0-9\-_]+)",
            r"([a-zA-Z0-9\-_]+)\s+pod",
            r"pod\s+([a-zA-Z0-9\-_]+)",
            r"logs?\s+from\s+pod\s+([a-zA-Z0-9\-_]+)",
            r"traces?\s+from\s+pod\s+([a-zA-Z0-9\-_]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1)
                if extracted.lower() not in ["pod", "logs", "traces", "from"]:
                    return extracted

        return None

    @staticmethod
    def extract_container_name(prompt: str) -> Optional[str]:
        """Extract Kubernetes container name from prompt"""
        if not prompt:
            return None

        patterns = [
            r"container:\s*([a-zA-Z0-9\-_]+)",
            r"container_name:\s*([a-zA-Z0-9\-_]+)",
            r"([a-zA-Z0-9\-_]+)\s+container",
            r"container\s+([a-zA-Z0-9\-_]+)",
            r"in\s+container\s+([a-zA-Z0-9\-_]+)",
            r"from\s+container\s+([a-zA-Z0-9\-_]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1)
                if extracted.lower() not in ["container", "in", "from"]:
                    return extracted

        return None

    @staticmethod
    def extract_namespace(prompt: str) -> Optional[str]:
        """Extract Kubernetes namespace from prompt"""
        if not prompt:
            return None

        patterns = [
            r'namespace[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'ns[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'in\s+namespace\s+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'from\s+namespace\s+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r"([a-zA-Z0-9\-_]+)\s+namespace",
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1)
                if extracted.lower() not in ["namespace", "ns", "in", "from"]:
                    return extracted

        return None

    @staticmethod
    def extract_service_name(prompt: str) -> Optional[str]:
        """Extract Kubernetes service name from prompt"""
        if not prompt:
            return None

        patterns = [
            r'servicename[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'service\s+name\s*(?:is\s*)?["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'service[:\s]+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'["\']?([a-zA-Z0-9\-_]+)["\']?\s+service',
            r'service\s+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r"([a-zA-Z0-9\-_]+)-service",
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1)
                if extracted.lower() not in ["service"]:
                    return extracted

        return None

    @staticmethod
    def extract_duration_filter(prompt: str) -> Dict[str, int]:
        """Extract duration filter from prompt and return in nanoseconds"""
        # Default duration: last 30 minutes
        default_duration = 30 * 60  # 30 minutes in seconds

        patterns = [
            r"last (\d+) minutes?",  # last 15 minutes
            r"(\d+) minutes? ago",  # 15 minutes ago
            r"last (\d+) hours?",  # last 2 hours
            r"(\d+) hours? ago",  # 2 hours ago
            r"last (\d+) days?",  # last 1 day
            r"(\d+) days? ago",  # 1 day ago
            r"since (\d+):(\d+)",  # since 14:30 (today)
            r"between (\d+):(\d+) and (\d+):(\d+)",  # between 14:00 and 16:00
            r"(\d+) hour",  # 1 hour (singular)
            r"(\d+) minute",  # 1 minute (singular)
            r"(\d+) day",  # 1 day (singular)
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                if "minutes" in pattern or "minute" in pattern:
                    minutes = int(match.group(1))
                    return {
                        "lower_bound": 500000000,  # 500ms in nanoseconds
                        "upper_bound": minutes
                        * 60
                        * 1000000000,  # minutes to nanoseconds
                    }
                elif "hours" in pattern or "hour" in pattern:
                    hours = int(match.group(1))
                    return {
                        "lower_bound": 500000000,  # 500ms in nanoseconds
                        "upper_bound": hours
                        * 60
                        * 60
                        * 1000000000,  # hours to nanoseconds
                    }
                elif "days" in pattern or "day" in pattern:
                    days = int(match.group(1))
                    return {
                        "lower_bound": 500000000,  # 500ms in nanoseconds
                        "upper_bound": days
                        * 24
                        * 60
                        * 60
                        * 1000000000,  # days to nanoseconds
                    }

        # Return default duration (last 30 minutes)
        return {
            "lower_bound": 500000000,  # 500ms in nanoseconds
            "upper_bound": default_duration * 1000000000,  # 30 minutes to nanoseconds
        }

    @staticmethod
    def extract_trace_id(prompt: str) -> Optional[str]:
        """Extract trace ID from prompt"""
        # Trace ID patterns (hexadecimal, typically 16-32 characters)
        patterns = [
            r"trace[:\s]+([a-fA-F0-9]{16,32})",  # trace: abc123...
            r"trace_id[:\s]+([a-fA-F0-9]{16,32})",  # trace_id: abc123...
            r"trace ([a-fA-F0-9]{16,32})",  # trace abc123...
            r"([a-fA-F0-9]{16,32})",  # just the hex string (should be last)
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def extract_timestamp(prompt: str) -> Optional[str]:
        """Extract timestamp from prompt"""
        # ISO 8601 timestamp patterns
        patterns = [
            r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z))",  # ISO format
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",  # YYYY-MM-DD HH:MM:SS
            r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",  # MM/DD/YYYY HH:MM:SS
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                timestamp_str = match.group(1)
                try:
                    # Try to parse and convert to ISO format
                    if "/" in timestamp_str:
                        # MM/DD/YYYY format
                        dt = datetime.strptime(timestamp_str, "%m/%d/%Y %H:%M:%S")
                    elif "T" in timestamp_str:
                        # Already ISO format
                        dt = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                    else:
                        # YYYY-MM-DD format
                        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                    return dt.astimezone().isoformat()
                except ValueError:
                    continue

        return None

    @staticmethod
    def extract_all_kubernetes_info(prompt: str) -> Dict[str, Optional[str]]:
        """Extract all Kubernetes-related information from a prompt"""
        return {
            "cluster_name": PromptParser.extract_kube_cluster_name(prompt),
            "deployment_name": PromptParser.extract_kube_deployment(prompt),
            "pod_name": PromptParser.extract_kube_pod_name(prompt),
            "container_name": PromptParser.extract_container_name(prompt),
            "namespace": PromptParser.extract_namespace(prompt),
            "service_name": PromptParser.extract_service_name(prompt),
            "duration_filter": PromptParser.extract_duration_filter(prompt),
            "trace_id": PromptParser.extract_trace_id(prompt),
            "timestamp": PromptParser.extract_timestamp(prompt),
        }


# Define the tool that fetches traces for all services running in a Kubernetes cluster
class FetchTraces(Tool):
    """Tool to fetch APM traces for all services in Kubernetes cluster"""

    name: str = "kfuse_tempo_fetch_traces"
    description: str = """Fetch APM traces for all services running in the Kubernetes cluster. This tool automatically extracts
    the cluster name and duration filter from your prompt. It retrieves traces across all services in the cluster,
    providing a broad overview. Use this when you need to see a wide range of activity, or when you're starting
    an investigation and don't yet have a specific target. Examples:
    - "Show me traces from the last hour in production cluster"
    - "Get all traces from staging environment in the last 30 minutes"
    - "Fetch traces from dev cluster since 2 hours ago"
    """
    parameters: Dict[str, ToolParameter] = {
        "user_prompt": ToolParameter(
            description="User prompt containing cluster name and duration information",
            type="string",
            required=False,
            default="",
        )
    }

    toolset: Optional[Any] = Field(default=None, exclude=True)

    def __init__(self, toolset=None):
        super().__init__(
            name="kfuse_tempo_fetch_traces",
            description="""Fetch APM traces for all services running in the Kubernetes cluster. This tool automatically extracts
            the cluster name and duration filter from your prompt. It retrieves traces across all services in the cluster,
            providing a broad overview. Use this when you need to see a wide range of activity, or when you're starting
            an investigation and don't yet have a specific target. Examples:
            - "Show me traces from the last hour in production cluster"
            - "Get all traces from staging environment in the last 30 minutes"
            - "Fetch traces from dev cluster since 2 hours ago"
            """,
            parameters={
                "user_prompt": ToolParameter(
                    description="User prompt containing cluster name and duration information",
                    type="string",
                    required=False,
                    default="",
                )
            },
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Fetch APM traces for all services in the cluster"""
        try:
            user_prompt = params.get("user_prompt", "")

            # Get configuration values from the toolset config
            tempo_url = os.getenv("TEMPO_URL", self.toolset.config.get("tempo_url"))
            kube_cluster_name = os.getenv(
                "KUBE_CLUSTER_NAME", self.toolset.config.get("kube_cluster_name")
            )

            if not tempo_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Config must provide 'tempo_url'.",
                    params=params,
                )

            # Extract all Kubernetes information from prompt
            kube_info = PromptParser.extract_all_kubernetes_info(user_prompt)

            # Use cluster name from prompt if provided, otherwise fall back to config
            prompt_cluster = kube_info["cluster_name"]
            if prompt_cluster:
                kube_cluster_name = prompt_cluster
            elif not kube_cluster_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not determine Kubernetes cluster name from prompt. Please specify the cluster in your request.",
                    params=params,
                )

            # Extract duration filter from prompt
            duration_filter = kube_info["duration_filter"]
            duration_secs = duration_filter["upper_bound"] // 1000000000

            # Generate current timestamp in ISO 8601 format with timezone offset
            current_timestamp = datetime.now().astimezone().isoformat()

            # Build the query payload
            query = f"""
            {{
              traces (
                durationSecs: {duration_secs}
                filter: {{
                  and: [
                    {{
                      attributeFilter: {{
                        eq: {{
                          key: "span_service_entry",
                          value: "true"
                        }}
                      }}
                    }},
                    {{
                      attributeFilter: {{
                        eq: {{
                          key: "kube_cluster_name",
                          value: "{kube_cluster_name}"
                        }}
                      }}
                    }}
                  ]
                }}
                limit: 100
                pageNum: 1
                timestamp: "{current_timestamp}"
                sortField: "timestamp"
                sortOrder: Desc
              ) {{
                traceId
                span {{
                  spanId
                  parentSpanId
                  startTimeNs
                  endTimeNs
                  attributes
                  durationNs
                  name
                  service {{
                    name
                    labels
                    hash
                    distinctLabels
                  }}
                  statusCode
                  method
                  endpoint
                  rootSpan
                }}
                traceMetrics {{
                  spanCount
                  serviceExecTimeNs
                }}
              }}
            }}
            """

            payload = {"query": query, "variables": {}}

            # Construct the API endpoint URL
            url = f"http://{tempo_url}:8080/v1/trace/query"
            headers = {"Content-Type": "application/json"}
            token = self.toolset.config.get("basic_auth_token")
            auth_user = self.toolset.config.get("auth_user")
            if token:
                headers["Authorization"] = f"Basic {token}"
            if auth_user:
                headers["X-Auth-Request-User"] = auth_user

            logger.info(f"Fetching traces for cluster: {kube_cluster_name}")
            logger.info(f"Duration filter: {duration_secs} seconds")
            logger.info("Tempo request payload: %s", payload)
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            logger.info("Tempo response [%s]: %s", response.status_code, response.text)
            response.raise_for_status()
            result = response.json()

            # Add metadata to the response
            result["metadata"] = {
                "cluster_name": kube_cluster_name,
                "duration_filter_seconds": duration_secs,
                "query_timestamp": current_timestamp,
                "tempo_host": tempo_url,
            }

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS, data=result, params=params
            )
        except requests.exceptions.Timeout:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Request to Tempo timed out. Please try again.",
                params=params,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching traces: HTTP {e}",
                params=params,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error parsing response: {e}",
                params=params,
            )
        except Exception as e:
            logger.exception("Unexpected error fetching traces")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching traces: {e}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "kfuse_tempo_fetch_traces()"


###############################################
# Define the tool that fetches traces for a single service
class FetchServiceTraces(Tool):
    """Tool to fetch APM traces for a specific Kubernetes service"""

    name: str = "kfuse_tempo_fetch_service_traces"
    description: str = """Fetch APM traces for a specific Kubernetes service. This tool automatically extracts the service name,
    namespace, cluster name, and duration filter from your prompt. Use this when you suspect a problem with a particular service
    and want to examine its traces in isolation. Examples:
    - "Show me traces for the checkout service in production namespace prod"
    - "Get traces from auth-service in staging for the last hour"
    - "Fetch traces for payment-service in dev cluster since 2 hours ago"
    """
    parameters: Dict[str, ToolParameter] = {
        "user_prompt": ToolParameter(
            description="User prompt containing service, namespace, cluster, and duration information",
            type="string",
            required=True,
        )
    }

    toolset: Optional[Any] = Field(default=None, exclude=True)

    def __init__(self, toolset=None):
        super().__init__(
            name="kfuse_tempo_fetch_service_traces",
            description="""Fetch APM traces for a specific Kubernetes service. This tool automatically extracts the service name,
            namespace, cluster name, and duration filter from your prompt. Use this when you suspect a problem with a particular service
            and want to examine its traces in isolation. Examples:
            - "Show me traces for the checkout service in production"
            - "Get traces from auth-service in staging for the last hour"
            - "Fetch traces for payment-service in dev cluster since 2 hours ago"
            """,
            parameters={
                "user_prompt": ToolParameter(
                    description="User prompt containing service, namespace, cluster, and duration information",
                    type="string",
                    required=True,
                )
            },
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Fetch APM traces for a specific Kubernetes service"""
        try:
            user_prompt = params["user_prompt"]

            # Get configuration values from the toolset config
            tempo_url = os.getenv("TEMPO_URL", self.toolset.config.get("tempo_url"))
            kube_cluster_name = os.getenv(
                "KUBE_CLUSTER_NAME", self.toolset.config.get("kube_cluster_name")
            )

            if not tempo_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Config must provide 'tempo_url'.",
                    params=params,
                )

            # Extract all Kubernetes information from prompt
            kube_info = PromptParser.extract_all_kubernetes_info(user_prompt)

            # Extract parameters from prompt
            service_name = kube_info["service_name"]
            namespace = kube_info["namespace"]
            if not service_name or not namespace:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not determine service name or namespace from prompt. Please specify both in your request.",
                    params=params,
                )

            # Use cluster name from prompt if provided, otherwise fall back to config
            prompt_cluster = kube_info["cluster_name"]
            if prompt_cluster:
                kube_cluster_name = prompt_cluster
            elif not kube_cluster_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not determine Kubernetes cluster name from prompt. Please specify the cluster in your request.",
                    params=params,
                )

            # Extract duration filter from prompt
            duration_filter = kube_info["duration_filter"]
            duration_secs = duration_filter["upper_bound"] // 1000000000

            # Generate current timestamp in ISO 8601 format with timezone offset
            current_timestamp = datetime.now().astimezone().isoformat()

            # Build the query payload
            query = f"""
        {{
          traces (
            durationSecs: {duration_secs}
            filter: {{
              and: [
                {{ attributeFilter: {{ eq: {{ key: "span_service_entry", value: "true" }} }} }},
                {{ attributeFilter: {{ eq: {{ key: "kube_cluster_name", value: "{kube_cluster_name}" }} }} }},
                {{ attributeFilter: {{ eq: {{ key: "kube_namespace", value: "{namespace}" }} }} }},
                {{ attributeFilter: {{ eq: {{ key: "service_name", value: "{service_name}" }} }} }}
              ]
            }}
            limit: 100
            pageNum: 1
            timestamp: "{current_timestamp}"
            sortField: "timestamp"
            sortOrder: Desc
          ) {{
            traceId
            span {{
              spanId
              parentSpanId
              startTimeNs
              endTimeNs
              attributes
              durationNs
              name
              service {{
                name
                labels
                hash
                distinctLabels
              }}
              statusCode
              method
              endpoint
              rootSpan
            }}
            traceMetrics {{
              spanCount
              serviceExecTimeNs
            }}
          }}
            }}
            """

            payload = {"query": query, "variables": {}}

            # Construct the API endpoint URL
            url = f"http://{tempo_url}:8080/v1/trace/query"
            headers = {"Content-Type": "application/json"}
            token = self.toolset.config.get("basic_auth_token")
            auth_user = self.toolset.config.get("auth_user")
            if token:
                headers["Authorization"] = f"Basic {token}"
            if auth_user:
                headers["X-Auth-Request-User"] = auth_user

            logger.info(f"Fetching traces for service: {service_name}")
            logger.info(f"Namespace: {namespace}")
            logger.info(f"Cluster: {kube_cluster_name}")
            logger.info(f"Duration filter: {duration_secs} seconds")
            logger.info("Tempo request payload: %s", payload)
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            logger.info("Tempo response [%s]: %s", response.status_code, response.text)
            response.raise_for_status()
            result = response.json()

            # Add metadata to the response
            result["metadata"] = {
                "service_name": service_name,
                "namespace": namespace,
                "cluster_name": kube_cluster_name,
                "duration_filter_seconds": duration_secs,
                "query_timestamp": current_timestamp,
                "tempo_host": tempo_url,
            }

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS, data=result, params=params
            )
        except requests.exceptions.Timeout:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Request to Tempo timed out. Please try again.",
                params=params,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching traces: HTTP {e}",
                params=params,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error parsing response: {e}",
                params=params,
            )
        except Exception as e:
            logger.exception("Unexpected error fetching traces")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching traces: {e}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return (
            f'kfuse_tempo_fetch_service_traces(user_prompt="{params["user_prompt"]}")'
        )


# New tool to analyze a trace and fetch RCA details
class AnalyzeTraceRCA(Tool):
    """Tool to analyze APM traces for root cause analysis"""

    name: str = "kfuse_tempo_analyze_trace_rca"
    description: str = """Perform a detailed analysis of a specific APM trace to identify the root cause of performance issues (RCA).
    This tool automatically extracts the trace_id and timestamp from your prompt, or you can provide them directly.
    It retrieves comprehensive information including the full trace details, details of the slowest span within the trace,
    and performance metrics (latency percentiles) for that span. Examples:
    - "Analyze trace abc123def456 for root cause analysis"
    - "Show me RCA details for trace xyz789 from 2 hours ago"
    - "What's the root cause of slow performance in trace abc123?"
    """
    parameters: Dict[str, ToolParameter] = {
        "user_prompt": ToolParameter(
            description="User prompt containing trace_id and optionally timestamp information",
            type="string",
            required=True,
        )
    }

    toolset: Optional[Any] = Field(default=None, exclude=True)

    def __init__(self, toolset=None):
        super().__init__(
            name="kfuse_tempo_analyze_trace_rca",
            description="""Perform a detailed analysis of a specific APM trace to identify the root cause of performance issues (RCA).
            This tool automatically extracts the trace_id and timestamp from your prompt, or you can provide them directly.
            It retrieves comprehensive information including the full trace details, details of the slowest span within the trace,
            and performance metrics (latency percentiles) for that span. Examples:
            - "Analyze trace abc123def456 for root cause analysis"
            - "Show me RCA details for trace xyz789 from 2 hours ago"
            - "What's the root cause of slow performance in trace abc123?"
            """,
            parameters={
                "user_prompt": ToolParameter(
                    description="User prompt containing trace_id and optionally timestamp information",
                    type="string",
                    required=True,
                )
            },
        )
        self.toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Analyze APM trace for root cause analysis"""
        try:
            user_prompt = params["user_prompt"]

            # Extract trace_id and timestamp from prompt
            trace_id = PromptParser.extract_trace_id(user_prompt)
            if not trace_id:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not determine trace ID from prompt. Please specify the trace ID in your request.",
                    params=params,
                )

            timestamp = PromptParser.extract_timestamp(user_prompt)
            if not timestamp:
                # Use current timestamp if none provided
                timestamp = datetime.now().astimezone().isoformat()

            tempo_url = os.getenv("TEMPO_URL", self.toolset.config.get("tempo_url"))
            if not tempo_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Config must provide 'tempo_url'.",
                    params=params,
                )

            headers = {"Content-Type": "application/json"}
            token = self.toolset.config.get("basic_auth_token")
            auth_user = self.toolset.config.get("auth_user")
            if token:
                headers["Authorization"] = f"Basic {token}"
            if auth_user:
                headers["X-Auth-Request-User"] = auth_user
            url = f"http://{tempo_url}:8080/v1/trace/query"

            logger.info(f"Analyzing trace: {trace_id}")
            logger.info(f"Timestamp: {timestamp}")

            # Step 1. Fetch detailed trace data using describeTrace
            trace_query = f"""
        {{
          describeTrace(
            traceId: "{trace_id}"
            timestamp: "{timestamp}"
          ) {{
            spans {{
              attributes
              endpoint
              endTimeNs
              method
              name
              durationNs
              parentSpanId
              rootSpan
              service {{
                name
                distinctLabels
                hash
                labels
              }}
              span
              spanId
              startTimeNs
              statusCode
              traceId
            }}
            traceMetrics {{
              hostExecTimeNs
              spanCount
              serviceExecTimeNs
              spanIdExecTimeNs
            }}
          }}
            }}
            """

            payload = {"query": trace_query, "variables": {}}

            try:
                logger.info("Tempo request payload: %s", payload)
                response_trace = requests.post(
                    url, headers=headers, json=payload, timeout=30
                )
                logger.info(
                    "Tempo response [%s]: %s",
                    response_trace.status_code,
                    response_trace.text,
                )
                response_trace.raise_for_status()
                trace_details = response_trace.json()
            except requests.exceptions.Timeout:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Request to Tempo timed out. Please try again.",
                    params=params,
                )
            except requests.exceptions.RequestException as e:
                logger.error(f"HTTP request failed: {e}")
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Error fetching trace details: HTTP {e}",
                    params=params,
                )
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response: {e}")
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Error parsing response: {e}",
                    params=params,
                )
            except Exception as e:
                logger.exception("Failed to fetch trace details")
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Error fetching trace details: {e}",
                    params=params,
                )

            spans = (
                trace_details.get("data", {}).get("describeTrace", {}).get("spans", [])
            )
            if not spans:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="No spans found in the trace.",
                    params=params,
                )

            # For RCA, pick the span with maximum durationNs
            max_span = max(spans, key=lambda s: s.get("durationNs", 0))
            span_id = max_span.get("spanId")
            span_name = max_span.get("name")
            service_hash = max_span.get("service", {}).get("hash")
            latency_ns = max_span.get("durationNs")

            # Step 2. Fetch detailed span data using describeSpan
            span_query = f"""
            {{
              describeSpan(
                spanId: "{span_id}"
                traceId: "{trace_id}"
                timestamp: "{timestamp}"
              ) {{
                attributes
                endpoint
                endTimeNs
                method
                name
                durationNs
                parentSpanId
                rootSpan
                service {{
                  name
                  distinctLabels
                  hash
                  labels
                }}
                span
                spanId
                startTimeNs
                statusCode
                traceId
              }}
            }}
            """

            payload = {"query": span_query, "variables": {}}

            try:
                logger.info("Tempo request payload: %s", payload)
                response_span = requests.post(
                    url, headers=headers, json=payload, timeout=30
                )
                logger.info(
                    "Tempo response [%s]: %s",
                    response_span.status_code,
                    response_span.text,
                )
                response_span.raise_for_status()
                span_details = response_span.json()
            except requests.exceptions.Timeout:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Request to Tempo timed out. Please try again.",
                    params=params,
                )
            except requests.exceptions.RequestException as e:
                logger.error(f"HTTP request failed: {e}")
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Error fetching span details: HTTP {e}",
                    params=params,
                )
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response: {e}")
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Error parsing response: {e}",
                    params=params,
                )
            except Exception as e:
                logger.exception("Failed to fetch span details")
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Error fetching span details: {e}",
                    params=params,
                )

            # Step 3. Fetch span metrics (latency percentiles) using spanMetrics
            if service_hash and span_name:
                metrics_query = f"""
            {{
              spanMetrics(
                latencyNs: {latency_ns}
                service: {{
                  hash: "{service_hash}"
                }}
                spanName: "{span_name}"
                timestamp: "{timestamp}"
              ) {{
                spanDurationPercentiles {{
                  max
                  p99
                  p95
                  p90
                  p75
                  p50
                }}
                spanDurationRank
              }}
            }}
            """

            payload = {"query": metrics_query, "variables": {}}

            try:
                logger.info("Tempo request payload: %s", payload)
                response_metrics = requests.post(
                    url, headers=headers, json=payload, timeout=30
                )
                logger.info(
                    "Tempo response [%s]: %s",
                    response_metrics.status_code,
                    response_metrics.text,
                )
                response_metrics.raise_for_status()
                metrics_details = response_metrics.json()
            except requests.exceptions.Timeout:
                metrics_details = {"error": "Request to Tempo timed out"}
            except Exception as e:
                logger.warning(f"Failed to fetch span metrics: {e}")
                metrics_details = {"error": f"Failed to fetch metrics: {e}"}
            else:
                metrics_details = {"error": "Service hash or span name not available"}

            # Combine all results into a single JSON response
            result = {
                "trace_details": trace_details,
                "span_details": span_details,
                "span_metrics": metrics_details,
                "metadata": {
                    "trace_id": trace_id,
                    "timestamp": timestamp,
                    "slowest_span": {
                        "span_id": span_id,
                        "span_name": span_name,
                        "duration_ns": latency_ns,
                        "duration_ms": latency_ns // 1000000 if latency_ns else None,
                    },
                    "tempo_host": tempo_url,
                },
            }

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS, data=result, params=params
            )
        except requests.exceptions.Timeout:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="Request to Tempo timed out. Please try again.",
                params=params,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error analyzing trace: HTTP {e}",
                params=params,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error parsing response: {e}",
                params=params,
            )
        except Exception as e:
            logger.exception("Unexpected error analyzing trace")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error analyzing trace: {e}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f'kfuse_tempo_analyze_trace_rca(user_prompt="{params["user_prompt"]}")'


# Define the toolset for Kfuse Tempo
# kfuse_tempo_toolset.py
class KfuseTempoToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: Dict[str, Any] = {}

    def __init__(self):
        super().__init__(
            name="kfuse_tempo",  # avoid slashes in IDs
            description="""Toolset to query Kfuse Tempo for APM traces with intelligent parameter extraction.
            This toolset automatically extracts Kubernetes cluster names, namespaces, service names, and duration filters
            from user prompts, making it easy to query traces without specifying technical parameters.

            Features:
            - Automatic extraction of kube_cluster_name, kube_namespace, service_name, and duration filters from natural language
            - Centralized Tempo host configuration
            - Smart parsing of time ranges (last 30 minutes, 2 hours ago, etc.)
            - Comprehensive trace analysis and root cause analysis (RCA)

            Examples:
            - "Show me traces from production cluster in the last hour"
            - "Get traces for user-service in staging namespace"
            - "Analyze trace abc123 for root cause analysis"
            """,
            enabled=False,  # start disabled until configured
            tools=[],  # attach after init
            tags=[ToolsetTag.CORE],
            prerequisites=[CallablePrerequisite(callable=self._prereq_check)],
        )
        # Declare tools after init so they capture the instance cleanly
        self.tools = [
            FetchTraces(self),
            FetchServiceTraces(self),
            AnalyzeTraceRCA(self),
        ]

    def _prereq_check(self, _: Dict[str, Any]) -> tuple[bool, str]:
        tempo = os.getenv("TEMPO_URL") or self.config.get("tempo_url")
        if not tempo:
            return (
                False,
                "tempo_url missing (set TEMPO_URL env or provide config.tempo_url)",
            )
        return True, ""

    def configure(self, cfg: Dict[str, Any]) -> None:
        self.config = cfg or {}
        ok, msg = self._prereq_check({})
        if not ok:
            raise ValueError(msg)
        self.enabled = True  # ✅ flip it on

    def get_example_config(self) -> Dict[str, Any]:
        """Return example configuration for this toolset"""
        return {
            "tempo_url": "your-kfuse-tempo-url",
            "kube_cluster_name": "your-cluster-name",
            "basic_auth_token": "base64-encoded-token",
            "auth_user": "your-user",
        }
