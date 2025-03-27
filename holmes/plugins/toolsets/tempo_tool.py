import os
import json
import logging
from datetime import datetime
from typing import Any, Dict

import requests
from pydantic import BaseModel, ConfigDict
from holmes.core.tools import (
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
)

# Define a base tool class for the Kfuse Tempo toolset
class BaseTempoTool(Tool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    toolset: "KfuseTempoToolset"

# Define the tool that fetches traces for all services running in a Kubernetes cluster
class FetchTraces(BaseTempoTool):
    def __init__(self, toolset: "KfuseTempoToolset"):
        super().__init__(
            name="kfuse_tempo_fetch_traces",
            description="""Fetch APM traces for all services running in the Kubernetes cluster.  This tool retrieves traces across *all* services
            in the cluster, providing a broad overview.  It's best suited for identifying general trends or finding traces *without* knowing
            the specific service or deployment beforehand.  It fetches traces from the last 30 minutes by default.  Use this when you need
            to see a wide range of activity, or when you're starting an investigation and don't yet have a specific target.  This tool does *not*
            require any specific input parameters, as it automatically uses the cluster name from the configuration.""",
            parameters={},  # No extra parameters in this example
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        # Get configuration values from the toolset config
        tempo_url =  os.getenv("TEMPO_URL", self.toolset.config.get("tempo_url"))
        kube_cluster_name = os.getenv("KUBE_CLUSTER_NAME", self.toolset.config.get("kube_cluster_name"))
        if not tempo_url or not kube_cluster_name:
            raise ValueError("Config must provide 'tempo_url' and 'kube_cluster_name'.")

        # Generate current timestamp in ISO 8601 format with timezone offset
        current_timestamp = datetime.now().astimezone().isoformat()

        # Build the query payload as a single-line string.
        # (Note: Adjust the filter structure as required by your Tempo API.)
        query = ("    {traces (durationSecs: 3600, filter: { and: [{attributeFilter: {eq: { key: \"kube_cluster_name\", value:\"" + kube_cluster_name + "\"}}}{ durationFilter: { lowerBound: 500000000, upperBound: 476102000000 }}{attributeFilter: {eq : {key: \"span_service_entry\", value: \"true\"}}}] } timestamp: \"" + current_timestamp + "\",sortField: \"duration\", sortOrder: Desc, ) { traceId span { spanId           parentSpanId           startTimeNs           endTimeNs          attributes          durationNs          name          service {            name            labels            hash            distinctLabels          }          statusCode          method          endpoint          rootSpan                  }        traceMetrics {          spanCount          serviceExecTimeNs        }      }    }  ")
        payload = {
            "query": query,
            "variables": {}
        }

        # Construct the API endpoint URL
        url = f"http://{tempo_url}:8080/v1/trace/query"
        headers = {"Content-Type": "application/json"}
        print(payload)
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return json.dumps(response.json(), indent=2)
        except Exception as e:
            logging.exception("Failed to fetch traces")
            return f"Error fetching traces: {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        tool_choice = "kfuse_tempo_fetch_traces()"
        logging.debug(f"Tool choice: {tool_choice}")
        return tool_choice

# Define the tool that fetches traces for a single kubernetes deployment workload
class FetchKubeDeploymentTraces(Tool):
    def __init__(self):
        super().__init__(
            name="kfuse_tempo_fetch_kube_deployment_traces",
            description="""Fetch APM traces for a *specific* Kubernetes deployment. This tool narrows down the search to a single
            deployment, identified by its name.  Use this when you suspect a problem with a particular deployment and want to examine its traces
            in isolation. It retrieves the traces from last 30 minutes. The 'kube_deployment' parameter is *required*. This tool helps you quickly focus
            on a known trouble spot, rather than searching through all traces.""",
            parameters={
                "kube_deployment": ToolParameter(
                    description="Kubernetes deployment name for which APM traces need to be fetched",
                    type="string",
                    required=True,
                )
            },  # No extra parameters in this example
        )

    def _invoke(self, params: Any) -> str:
        # Get configuration values from the toolset config
        tempo_url =  os.getenv("TEMPO_URL")
        kube_cluster_name = os.getenv("KUBE_CLUSTER_NAME")
        kube_deployment: str = params["kube_deployment"]
        if not tempo_url or not kube_cluster_name:
            raise ValueError("Config must provide 'tempo_url' and 'kube_cluster_name'.")

        # Generate current timestamp in ISO 8601 format with timezone offset
        current_timestamp = datetime.now().astimezone().isoformat()

        # Build the query payload as a single-line string.
        # (Note: Adjust the filter structure as required by your Tempo API.)
        query = ("    {traces (durationSecs: 1800, filter: { and: [{attributeFilter: {eq: { key: \"kube_deployment\", value:\"" + kube_deployment + "\"}}}{attributeFilter: {eq: { key: \"kube_cluster_name\", value:\"" + kube_cluster_name + "\"}}}{ durationFilter: { lowerBound: 500000000, upperBound: 476102000000 }}{attributeFilter: {eq : {key: \"span_service_entry\", value: \"true\"}}}] } timestamp: \"" + current_timestamp + "\",sortField: \"duration\", sortOrder: Desc, ) { traceId span { spanId           parentSpanId           startTimeNs           endTimeNs          attributes          durationNs          name          service {            name            labels            hash            distinctLabels          }          statusCode          method          endpoint          rootSpan                  }        traceMetrics {          spanCount          serviceExecTimeNs        }      }    }  ")
        payload = {
            "query": query,
            "variables": {}
        }

        # Construct the API endpoint URL
        url = f"http://{tempo_url}:8080/v1/trace/query"
        headers = {"Content-Type": "application/json"}
        print(payload)
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return json.dumps(response.json(), indent=2)
        except Exception as e:
            logging.exception("Failed to fetch traces")
            return f"Error fetching traces: {e}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        tool_choice = "kfuse_tempo_fetch_traces()"  # Corrected typo here: should match the class's name
        logging.debug(f"Tool choice: {tool_choice}")
        return tool_choice


# New tool to analyze a trace and fetch RCA details
class AnalyzeTraceRCA(BaseTempoTool):
    def __init__(self, toolset: "KfuseTempoToolset"):
        super().__init__(
            name="kfuse_tempo_analyze_trace_rca",
            description="""Perform a detailed analysis of a *specific* APM trace to identify the root cause of performance issues (RCA).
            This tool requires the 'trace_id' and a 'timestamp' as input.  It retrieves comprehensive information, including the full trace details,
            details of the slowest span within the trace, and performance metrics (latency percentiles) for that span. Use this tool when you
            have already identified a problematic trace (e.g., using 'kfuse_tempo_fetch_traces' or 'kfuse_tempo_fetch_kube_deployment_traces')
            and need to drill down into the specifics to understand *why* it was slow. This provides deep insights for root cause analysis.""",
            parameters={
                "trace_id": ToolParameter(
                    description="Trace ID to analyze",
                    type="string",
                    required=True,
                ),
                "timestamp": ToolParameter(
                    description="Timestamp (ISO8601) for the query (e.g., '2025-02-28T00:59:09+05:30')",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        trace_id: str = params["trace_id"]
        timestamp: str = params["timestamp"]
        tempo_url = os.getenv("TEMPO_URL", self.toolset.config.get("tempo_url"))
        if not tempo_url:
            raise ValueError("Config must provide 'tempo_url'.")
        headers = {"Content-Type": "application/json"}
        url = f"http://{tempo_url}:8080/v1/trace/query"

        # Step 1. Fetch detailed trace data using describeTrace.
        # Generate current timestamp in ISO 8601 format with timezone offset
        current_timestamp = datetime.now().astimezone().isoformat()
        # (Payload strictly follows the sample format; only timestamp and traceId are updated.)
        trace_query = (
            '{"operationName":null,"query":"\\n    {\\n      describeTrace(\\n        traceId: \\"'
            + trace_id
            + '\\"\\n        timestamp: \\"'
            + current_timestamp
            + '\\"\\n      ) {\\n        spans {\\n          attributes\\n          endpoint\\n          endTimeNs\\n          method\\n          name\\n          durationNs\\n          parentSpanId\\n          rootSpan\\n          service {\\n            name\\n            distinctLabels\\n            hash\\n            labels\\n          }\\n          span\\n          spanId\\n          startTimeNs\\n          statusCode\\n          traceId\\n        }\\n        traceMetrics {\\n          hostExecTimeNs\\n          spanCount\\n          serviceExecTimeNs\\n          spanIdExecTimeNs\\n        }\\n      }\\n    }\\n  ","variables":{}}'
        )
        print(trace_query)
        try:
            response_trace = requests.post(url, headers=headers, data=trace_query)
            print(response_trace)
            response_trace.raise_for_status()
            trace_details = response_trace.json()
        except Exception as e:
            logging.exception("Failed to fetch trace details")
            return f"Error fetching trace details: {e}"

        spans = trace_details.get("data", {}).get("describeTrace", {}).get("spans", [])
        if not spans:
            return "No spans found in the trace."
        # For RCA, pick the span with maximum durationNs
        max_span = max(spans, key=lambda s: s.get("durationNs", 0))
        span_id = max_span.get("spanId")
        span_name = max_span.get("name")
        service_hash = max_span.get("service", {}).get("hash")
        latency_ns = max_span.get("durationNs")

        # Step 2. Fetch detailed span data using describeSpan.
        span_query = (
            '{"operationName":null,"query":"\\n    {\\n        describeSpan(\\n        spanId: \\"'
            + span_id
            + '\\"\\n        traceId: \\"'
            + trace_id
            + '\\"\\n        timestamp: \\"'
            + current_timestamp
            + '\\"\\n      ) {\\n        attributes\\n        endpoint\\n        endTimeNs\\n        method\\n        name\\n        durationNs\\n        parentSpanId\\n        rootSpan\\n        service {\\n          name\\n          distinctLabels\\n          hash\\n          labels\\n        }\\n        span\\n        spanId\\n        startTimeNs\\n        statusCode\\n        traceId\\n      }\\n    }\\n  ","variables":{}}'
        )
        print(span_query)
        try:
            response_span = requests.post(url, headers=headers, data=span_query)
            print(response_span)
            response_span.raise_for_status()
            span_details = response_span.json()
        except Exception as e:
            logging.exception("Failed to fetch span details")
            return f"Error fetching span details: {e}"

        # Step 3. Fetch span metrics (latency percentiles) using spanMetrics.
        metrics_query = (
            '{"operationName":null,"query":"\\n    {\\n      spanMetrics(\\n        latencyNs: '
            + str(latency_ns)
            + '\\n        service: {\\n          hash: \\"'
            + service_hash
            + '\\"\\n        }\\n        spanName: \\"'
            + span_name
            + '\\"\\n        timestamp: \\"'
            + current_timestamp
            + '\\"\\n      ) {\\n        spanDurationPercentiles {\\n          max\\n          p99\\n          p95\\n          p90\\n          p75\\n          p50\\n        }\\n        spanDurationRank\\n      }\\n    }\\n  ","variables":{}}'
        )
        print(metrics_query)
        try:
            response_metrics = requests.post(url, headers=headers, data=metrics_query)
            print(response_metrics)
            response_metrics.raise_for_status()
            metrics_details = response_metrics.json()
        except Exception as e:
            logging.exception("Failed to fetch span metrics")
            return f"Error fetching span metrics: {e}"

        # Combine all results into a single JSON response.
        result = {
            "trace_details": trace_details,
            "span_details": span_details,
            "span_metrics": metrics_details,
        }
        return json.dumps(result, indent=2)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f'kfuse_tempo_analyze_trace_rca(trace_id="{params["trace_id"]}", timestamp="{params["timestamp"]}")'
# Define the toolset for Kfuse Tempo
class KfuseTempoToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # The configuration should include at least tempo_url and kube_cluster_name
    config: Dict[str, Any] = {}

    def __init__(self):
        super().__init__(
            name="kfuse/tempo",
            description="Toolset to query Kfuse Tempo for traces",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafana.html",
            icon_url="https://grafana.com/static/img/fav32.png",
            prerequisites=[],
            tools=[FetchTraces(self), FetchKubeDeploymentTraces(), AnalyzeTraceRCA(self)],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        # Check that the config includes required keys
        return bool(config.get("tempo_url") and config.get("kube_cluster_name"))

    def get_example_config(self) -> Dict[str, Any]:
        # Return an example configuration for this toolset
        return {
            "tempo_url": "your-tempo-host",  # e.g., "10.254.240.159"
            "kube_cluster_name": "your-cluster-name"  # e.g., "falliance-prod"
        }
