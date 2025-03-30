import logging
from typing import Dict, Any, List, Tuple, Optional
import requests
import os
import json
from pydantic import BaseModel, ConfigDict
from holmes.core.tools import (
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
)

log = logging.getLogger(__name__)

# Moved PROMETHEUS_URL to be a class-level variable with a default
DEFAULT_PROMETHEUS_URL = os.getenv("PROMETEHUS_URL")  # Or your default Prometheus URL


def fetch_prometheus_metric(query: str, try_json: bool = True) -> Dict[str, Any]:
    """Fetches data from Prometheus using its API.
       Handles possible errors.
    """
    prometheus_url = os.getenv("PROMETHEUS_URL", DEFAULT_PROMETHEUS_URL)
    params = {'query': query}
    try:
        response = requests.get(f"{prometheus_url}/api/v1/query", params=params, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        if try_json:
          return response.json()
        else:
          return response.text()
    except requests.exceptions.RequestException as e:
        log.error(f"Error fetching Prometheus metric: {e}")
        raise  # Re-raise the exception to be caught by the caller

    except json.JSONDecodeError as e:
        log.error("Invalid JSON response: ", e)
        log.error(f"Query: {query}")
        log.error(f"Response: {response.text}")
        raise

    except Exception as e:
       log.error("An unexpected error has occured", e)
       raise


class BaseKubernetesCPUThrottlingTool(Tool):
    """Base class for Kubernetes CPU Throttling tools."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    toolset: "KubernetesCPUThrottlingToolset"


class GetContainerCPUThrottling(BaseKubernetesCPUThrottlingTool):

    def __init__(self, toolset: "KubernetesCPUThrottlingToolset"):
        super().__init__(
            name="get_container_cpu_throttling",
            description="""Fetches CPU throttling metrics for a specific container in a pod and calculates the throttling rate.
            Returns the pod name, container name, and throttling percentage. Returns null for throttling_percentage if no data is found.""",
            parameters={
                "namespace": ToolParameter(
                    description="The Kubernetes namespace.", type="string", required=True
                ),
                "pod_name": ToolParameter(
                    description="The name of the pod.", type="string", required=True
                ),
                "container_name": ToolParameter(
                    description="The name of the container.", type="string", required=True
                ),
                "duration": ToolParameter(
                    description="Prometheus range duration for rate calculation (e.g., '3m', '5m').",
                    type="string",
                    required=False,
                    default="3m"
                ),
                "history": ToolParameter(
                    description="How far back to look for historical data.",
                    type="string",
                    required=False,
                    default="60m"

                ),
                "step": ToolParameter(
                    description="Step size for historical data.",
                    type="string",
                    required=False,
                    default="3m"
                )
            },
            toolset=toolset
        )
    def _invoke(self, params: Dict[str, Any]) -> str:
        """Invokes the tool to get container CPU throttling."""
        namespace = params["namespace"]
        pod_name = params["pod_name"]
        container_name = params["container_name"]
        duration = params.get("duration", "3m")  # Use .get() for optional params
        history = params.get("history", "60m")
        step = params.get("step", "3m")
        try:
            result = get_container_cpu_throttling(namespace, pod_name, container_name, duration, history, step)
            return json.dumps(result, indent=2) # Serialize the dict to a JSON string
        except Exception as e:
            log.exception(f"Error getting throttling for {container_name} in {pod_name}: {e}")
            return f"Error: {e}" # Return the error message as string
    def get_parameterized_one_liner(self, params: Dict) -> str:
        namespace = params.get('namespace', '')
        pod_name = params.get('pod_name', '')
        container_name = params.get('container_name', '')
        duration = params.get('duration', '')
        history = params.get('history','')
        step = params.get('step', '')
        return f"get_container_cpu_throttling(namespace='{namespace}', pod_name='{pod_name}', container_name='{container_name}', duration='{duration}', history='{history}', step='{step}')"

class GetPodCPUThrottling(BaseKubernetesCPUThrottlingTool):
    def __init__(self, toolset: "KubernetesCPUThrottlingToolset"):
        super().__init__(
            name="get_pod_cpu_throttling",
            description="Gets CPU throttling data for all containers in a pod.",
            parameters={
                "namespace": ToolParameter(
                    description="The Kubernetes namespace.", type="string", required=True
                ),
                "pod_name": ToolParameter(
                    description="The name of the pod.", type="string", required=True
                ),
                "duration": ToolParameter(
                    description="Prometheus range duration for rate calculation (e.g., '3m', '5m').",
                    type="string",
                    required=False,
                    default="3m"
                ),
                "history": ToolParameter(
                    description="How far back to look for historical data",
                    type="string",
                    required=False,
                    default="60m"

                ),
                "step": ToolParameter(
                    description="Step size for historical data",
                    type="string",
                    required=False,
                    default="3m"
                )
            },
            toolset=toolset
        )
    def _invoke(self, params: Dict[str, Any]) -> str:
        """Invokes the tool to get pod CPU throttling."""
        namespace = params["namespace"]
        pod_name = params["pod_name"]
        duration = params.get("duration", "3m")
        history = params.get("history", "60m")
        step = params.get("step", "3m")

        try:
            results = get_pod_cpu_throttling(namespace, pod_name, duration, history, step)
            return json.dumps(results, indent=2)  # Serialize list of dicts
        except Exception as e:
            log.exception(f"Error getting pod throttling for {pod_name}: {e}")
            return f"Error: {e}"
    def get_parameterized_one_liner(self, params: Dict) -> str:
        namespace = params.get('namespace', '')
        pod_name = params.get('pod_name', '')
        duration = params.get('duration', '')
        history = params.get('history', '')
        step = params.get('step','')
        return f"get_pod_cpu_throttling(namespace='{namespace}', pod_name='{pod_name}', duration='{duration}', history='{history}', step='{step}')"


class GetNamespaceCPUThrottling(BaseKubernetesCPUThrottlingTool):
    def __init__(self, toolset: "KubernetesCPUThrottlingToolset"):
        super().__init__(
            name="get_namespace_cpu_throttling",
            description="Gets CPU throttling for all pods in a namespace.",
            parameters={
                "namespace": ToolParameter(
                    description="The Kubernetes namespace.", type="string", required=True
                ),
                "duration": ToolParameter(
                    description="Prometheus range duration for rate calculation (e.g., '3m', '5m').",
                    type="string",
                    required=False,
                    default="3m"
                ),
                 "history": ToolParameter(
                    description="How far back to look for historical data",
                    type="string",
                    required=False,
                    default="60m"

                ),
                "step": ToolParameter(
                    description="Step size for historical data",
                    type="string",
                    required=False,
                    default="3m"
                )
            },
            toolset=toolset
        )
    def _invoke(self, params: Dict[str, Any]) -> str:
        """Invokes the tool to get namespace CPU throttling."""
        namespace = params["namespace"]
        duration = params.get("duration", "3m")
        history = params.get("history", "60m")
        step = params.get("step", "3m")

        try:
            results = get_namespace_cpu_throttling(namespace, duration, history, step)
            return json.dumps(results, indent=2)  # Serialize list of dicts
        except Exception as e:
            log.exception(f"Error getting namespace throttling for {namespace}: {e}")
            return f"Error: {e}"
    def get_parameterized_one_liner(self, params: Dict) -> str:
        namespace = params.get('namespace', '')
        duration = params.get('duration', '')
        history = params.get("history", "")
        step = params.get("step", "")
        return f"get_namespace_cpu_throttling(namespace='{namespace}', duration='{duration}', history='{history}', step='{step}')"


class GetContainerNames(BaseKubernetesCPUThrottlingTool):
    def __init__(self, toolset: "KubernetesCPUThrottlingToolset"):
        super().__init__(
            name="get_container_names",
            description="Fetches a list of container names for a given pod.",
            parameters={
                "namespace": ToolParameter(
                    description="The Kubernetes namespace.", type="string", required=True
                ),
                "pod_name": ToolParameter(
                    description="The name of the pod.", type="string", required=True
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        """Invokes the tool to get container names."""
        namespace = params["namespace"]
        pod_name = params["pod_name"]
        try:
            container_names = get_container_names(namespace, pod_name)
            return json.dumps(container_names, indent=2) # List of strings
        except Exception as e:
            log.exception(f"Error getting container names for {pod_name}: {e}")
            return f"Error: {e}"
    def get_parameterized_one_liner(self, params: Dict) -> str:
        namespace = params.get('namespace', '')
        pod_name = params.get('pod_name', '')
        return f"get_container_names(namespace='{namespace}', pod_name='{pod_name}')"

class KubernetesCPUThrottlingToolset(Toolset):
    """Toolset for fetching Kubernetes CPU throttling information."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    def __init__(self):
        super().__init__(
            name="kubernetes_cpu_throttling",
            description="Fetches and calculates CPU throttling for Kubernetes containers.",
            tools=[
                GetContainerCPUThrottling(self),
                GetPodCPUThrottling(self),
                GetNamespaceCPUThrottling(self),
                GetContainerNames(self),
            ],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )

# --- Helper Functions (Defined *after* the Tool Classes) ---

def get_container_cpu_throttling(namespace: str, pod_name: str, container_name: str, duration:str="3m", history: str = "60m", step: str = "3m") -> Dict[str, Any]:
    """
    Fetches CPU throttling metrics for a specific container in a pod and
    calculates the throttling rate.
    """
    try:
        throttled_query = f'rate(container_cpu_cfs_throttled_periods_total{{namespace="{namespace}",pod="{pod_name}",container="{container_name}"}}[{duration}])[{history}:{step}]'
        periods_query = f'rate(container_cpu_cfs_periods_total{{namespace="{namespace}",pod="{pod_name}",container="{container_name}"}}[{duration}])[{history}:{step}]'

        throttled_response = fetch_prometheus_metric(throttled_query)
        periods_response = fetch_prometheus_metric(periods_query)

        #check for error in response
        if throttled_response.get("status") == "error":
            raise Exception(f"Prometheus query error: {throttled_response.get('error')}")

        if periods_response.get("status") == "error":
            raise Exception(f"Prometheus query error: {periods_response.get('error')}")

        throttled_values = None
        total_periods_values = None
        if throttled_response and throttled_response['data']['result']:
          throttled_values = throttled_response['data']['result'][0].get('values', [])
        if periods_response and periods_response['data']['result']:
          total_periods_values = periods_response['data']['result'][0].get('values', [])

        if not throttled_values or not total_periods_values:
             return {
                "pod_name": pod_name,
                "container_name": container_name,
                "throttling_percentage": None,
                "message": "No throttling data found."
             }
        # Ensure both lists have same length.
        if len(throttled_values) != len(total_periods_values):
          return {
                "pod_name": pod_name,
                "container_name": container_name,
                "throttling_percentage": None,
                "message": "Inconsistent throttling data found."
             }

        throttling_percentages = []
        for (throttled_ts, throttled_val_str), (periods_ts, periods_val_str) in zip(throttled_values, total_periods_values):
            throttled_val = float(throttled_val_str)
            periods_val = float(periods_val_str)

            # Avoid division by zero
            if periods_val > 0:
                throttling_percentage = (throttled_val / periods_val) * 100
                throttling_percentages.append([throttled_ts, throttling_percentage])
            else:
                throttling_percentages.append([throttled_ts, 0.0])  # Or handle as appropriate for your use-case

        # Return last value for the given duration
        return {
            "pod_name": pod_name,
            "container_name": container_name,
            "throttling_percentage": throttling_percentages[-1][1] if throttling_percentages else None,
            "historical_data": throttling_percentages,
            "message": "Successfully fetched and calculated throttling rate."
        }

    except Exception as e:
        log.error(f"Error in get_container_cpu_throttling: {e}")
        raise  # Re-raise the exception for the LLM to handle

def get_pod_cpu_throttling(namespace: str, pod_name: str, duration:str="3m", history: str = "60m", step:str="3m") -> List[Dict[str, Any]]:
    """Gets CPU throttling data for all containers in a pod."""
    try:
        # Use a simpler Prometheus query to get the pod's container names
        pod_info_query = f'kube_pod_info{{namespace="{namespace}", pod="{pod_name}"}}'
        pod_info_response = fetch_prometheus_metric(pod_info_query)

        if not pod_info_response['data']['result']:
             raise Exception(f"No pod found with name {pod_name} in namespace {namespace}.")

        container_names = get_container_names(namespace, pod_name)  # Use the new helper function

        results = []
        for container_name in container_names:
            try:
                throttling_data = get_container_cpu_throttling(namespace, pod_name, container_name, duration, history, step)
                results.append(throttling_data)
            except Exception as e:
                #  Log the error, but continue with the other containers
                log.error(f"Error fetching throttling for container {container_name} in pod {pod_name}: {e}")
                results.append({
                    "pod_name": pod_name,
                    "container_name": container_name,
                    "throttling_percentage": None,
                    "message": str(e),
                })
        return results

    except Exception as e:
        log.error(f"Error in get_pod_cpu_throttling: {e}")
        raise # Re-raise the exception

def get_container_names(namespace: str, pod_name: str) -> List[str]:
    """Fetches a list of container names for a given pod using kube_pod_container_info."""
    try:
        query = f'kube_pod_container_info{{namespace="{namespace}", pod="{pod_name}"}}'
        response = fetch_prometheus_metric(query)

        if response.get("status") == "error":
            raise Exception(f"Prometheus query error: {response.get('error')}")
        if not response['data']['result']:
            raise Exception(f"No containers found for pod {pod_name} in namespace {namespace}.")

        container_names = [result['metric']['container'] for result in response['data']['result']]
        return container_names

    except Exception as e:
        log.error(f"Error fetching container names: {e}")
        raise

def get_namespace_cpu_throttling(namespace: str, duration: str = "3m", history: str = "60m", step: str = "3m") -> List[Dict[str, Any]]:
    """Gets CPU throttling for all pods in a namespace"""
    try:
      query = f'kube_pod_container_info{{namespace="{namespace}"}}'
      response = fetch_prometheus_metric(query)

      if response.get("status") == "error":
        raise Exception(f"Prometheus query error: {response.get('error')}")

      if not response['data']['result']:
        return []

      results = []
      processed_pods = set()  # Keep track of processed pods to avoid duplicates

      for result in response['data']['result']:
        pod_name = result['metric']['pod']
        if pod_name not in processed_pods:
          pod_throttling_data = get_pod_cpu_throttling(namespace, pod_name, duration, history, step)
          results.extend(pod_throttling_data)
          processed_pods.add(pod_name)

      return results
    except Exception as e:
        log.error(f"Error fetching container names: {e}")
        raise
