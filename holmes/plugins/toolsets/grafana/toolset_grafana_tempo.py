import os
from typing import Any, Dict, List, cast

import requests  # type: ignore
import yaml  # type: ignore
from pydantic import BaseModel

from holmes.common.env_vars import load_bool
from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
)
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset
from holmes.plugins.toolsets.grafana.common import (
    GrafanaConfig,
    build_headers,
    get_base_url,
)
from holmes.plugins.toolsets.grafana.tempo_api import (
    query_tempo_trace_by_id,
    query_tempo_traces,
)
from holmes.plugins.toolsets.grafana.trace_parser import (
    format_traces_list,
    build_span_hierarchy,
)
from holmes.plugins.toolsets.logging_utils.logging_api import (
    DEFAULT_TIME_SPAN_SECONDS,
)
from holmes.plugins.toolsets.utils import (
    get_param_or_raise,
    process_timestamps_to_int,
    toolset_name_for_one_liner,
)

TEMPO_LABELS_ADD_PREFIX = load_bool("TEMPO_LABELS_ADD_PREFIX", True)

ONE_HOUR_IN_SECONDS = 3600


class GrafanaTempoLabelsConfig(BaseModel):
    pod: str = "k8s.pod.name"
    namespace: str = "k8s.namespace.name"
    deployment: str = "k8s.deployment.name"
    node: str = "k8s.node.name"
    service: str = "service.name"


class GrafanaTempoConfig(GrafanaConfig):
    labels: GrafanaTempoLabelsConfig = GrafanaTempoLabelsConfig()


class BaseGrafanaTempoToolset(BaseGrafanaToolset):
    config_class = GrafanaTempoConfig

    def get_example_config(self):
        example_config = GrafanaTempoConfig(
            api_key="YOUR API KEY",
            url="YOUR GRAFANA URL",
            grafana_datasource_uid="<UID of the tempo datasource to use>",
        )
        return example_config.model_dump()

    @property
    def grafana_config(self) -> GrafanaTempoConfig:
        return cast(GrafanaTempoConfig, self._grafana_config)


def validate_params(params: Dict[str, Any], expected_params: List[str]):
    for param in expected_params:
        if param in params and params[param] not in (None, "", [], {}):
            return None

    return f"At least one of the following argument is expected but none were set: {expected_params}"


class GetTempoTraces(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="fetch_tempo_traces",
            description="""Lists Tempo traces. At least one of `service_name`, `pod_name` or `deployment_name` argument is required.""",
            parameters={
                "min_duration": ToolParameter(
                    description="The minimum duration of traces to fetch, e.g., '5s' for 5 seconds.",
                    type="string",
                    required=True,
                ),
                "service_name": ToolParameter(
                    description="Filter traces by service name",
                    type="string",
                    required=False,
                ),
                "pod_name": ToolParameter(
                    description="Filter traces by pod name",
                    type="string",
                    required=False,
                ),
                "namespace_name": ToolParameter(
                    description="Filter traces by namespace",
                    type="string",
                    required=False,
                ),
                "deployment_name": ToolParameter(
                    description="Filter traces by deployment name",
                    type="string",
                    required=False,
                ),
                "node_name": ToolParameter(
                    description="Filter traces by node",
                    type="string",
                    required=False,
                ),
                "start_datetime": ToolParameter(
                    description="The beginning time boundary for the trace search period. String in RFC3339 format. If a negative integer, the number of seconds relative to the end_timestamp. Defaults to negative one hour (-3600)",
                    type="string",
                    required=False,
                ),
                "end_datetime": ToolParameter(
                    description="The ending time boundary for the trace search period. String in RFC3339 format. Defaults to NOW().",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of traces to return. Defaults to 50",
                    type="integer",
                    required=False,
                ),
                "sort": ToolParameter(
                    description="One of 'descending', 'ascending' or 'none' for no sorting. Defaults to descending",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        api_key = self._toolset.grafana_config.api_key
        headers = self._toolset.grafana_config.headers
        labels = self._toolset.grafana_config.labels

        invalid_params_error = validate_params(
            params, ["service_name", "pod_name", "deployment_name"]
        )
        if invalid_params_error:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=invalid_params_error,
                params=params,
            )

        start, end = process_timestamps_to_int(
            params.get("start_datetime"),
            params.get("end_datetime"),
            default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
        )

        prefix = ""
        if TEMPO_LABELS_ADD_PREFIX:
            prefix = "resource."

        filters = []
        if params.get("service_name"):
            filters.append(f'{prefix}{labels.service}="{params.get("service_name")}"')
        if params.get("pod_name"):
            filters.append(f'{prefix}{labels.pod}="{params.get("pod_name")}"')
        if params.get("namespace_name"):
            filters.append(
                f'{prefix}{labels.namespace}="{params.get("namespace_name")}"'
            )
        if params.get("deployment_name"):
            filters.append(
                f'{prefix}{labels.deployment}="{params.get("deployment_name")}"'
            )
        if params.get("node_name"):
            filters.append(f'{prefix}{labels.node}="{params.get("node_name")}"')

        filters.append(f'duration>{get_param_or_raise(params, "min_duration")}')

        query = " && ".join(filters)
        query = f"{{{query}}}"

        base_url = get_base_url(self._toolset.grafana_config)
        traces = query_tempo_traces(
            base_url=base_url,
            api_key=api_key,
            headers=headers,
            query=query,
            start=start,
            end=end,
            limit=params.get("limit", 50),
        )
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=format_traces_list(traces),
            params=params,
            invocation=query,
        )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{toolset_name_for_one_liner(self._toolset.name)}: Fetched Tempo Traces (min_duration={params.get('min_duration')})"


class GetTempoTags(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="fetch_tempo_tags",
            description="List the tags available in Tempo",
            parameters={
                "start_datetime": ToolParameter(
                    description="The beginning time boundary for the search period. String in RFC3339 format. If a negative integer, the number of seconds relative to the end_timestamp. Defaults to negative 8 hours (-3600)",
                    type="string",
                    required=False,
                ),
                "end_datetime": ToolParameter(
                    description="The ending time boundary for the search period. String in RFC3339 format. Defaults to NOW().",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        api_key = self._toolset.grafana_config.api_key
        headers = self._toolset.grafana_config.headers
        start, end = process_timestamps_to_int(
            start=params.get("start_datetime"),
            end=params.get("end_datetime"),
            default_time_span_seconds=8 * ONE_HOUR_IN_SECONDS,
        )

        base_url = get_base_url(self._toolset.grafana_config)
        url = f"{base_url}/api/v2/search/tags?start={start}&end={end}"

        try:
            response = requests.get(
                url,
                headers=build_headers(api_key=api_key, additional_headers=headers),
                timeout=60,
            )
            response.raise_for_status()  # Raise an error for non-2xx responses
            data = response.json()
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=yaml.dump(data.get("scopes")),
                params=params,
            )
        except requests.exceptions.RequestException as e:
            raise Exception(
                f"Failed to retrieve tags after retries: {e} \n for URL: {url}"
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{toolset_name_for_one_liner(self._toolset.name)}: Fetched Tempo tags"


class GetTempoTraceById(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="fetch_tempo_trace_by_id",
            description="""Retrieves detailed information about a Tempo trace using its trace ID. Use this to investigate a trace.""",
            parameters={
                "trace_id": ToolParameter(
                    description="The unique trace ID to fetch.",
                    type="string",
                    required=True,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        labels_mapping = self._toolset.grafana_config.labels
        labels = list(labels_mapping.model_dump().values())

        base_url = get_base_url(self._toolset.grafana_config)
        trace_data = query_tempo_trace_by_id(
            base_url=base_url,
            api_key=self._toolset.grafana_config.api_key,
            headers=self._toolset.grafana_config.headers,
            trace_id=get_param_or_raise(params, "trace_id"),
            key_labels=labels,
        )
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=trace_data,
            params=params,
        )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{toolset_name_for_one_liner(self._toolset.name)}: Fetched Tempo Trace (trace_id={params.get('trace_id')})"


class AnalyzeTracesByAttributes(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="analyze_traces_by_attributes",
            description="Analyzes traces grouped by specified span attributes to find patterns in performance or errors.",
            parameters={
                "service_name": ToolParameter(
                    description="Service to analyze traces for",
                    type="string",
                    required=False,
                ),
                "group_by_attributes": ToolParameter(
                    description="Span attributes to group analysis by (discovered from your traces)",
                    type="array",
                    required=True,
                ),
                "min_duration": ToolParameter(
                    description="Minimum duration to include (e.g., '100ms', '1s')",
                    type="string",
                    required=False,
                ),
                "start_datetime": ToolParameter(
                    description="Start time for analysis (RFC3339 or relative)",
                    type="string",
                    required=False,
                ),
                "end_datetime": ToolParameter(
                    description="End time for analysis (RFC3339 or relative)",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of traces to analyze",
                    type="integer",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Build query with flexible attributes
            group_by = params.get("group_by_attributes", [])
            service_name = params.get("service_name")
            min_duration = params.get("min_duration", "100ms")

            start, end = process_timestamps_to_int(
                params.get("start_datetime"),
                params.get("end_datetime"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )

            # Build TraceQL query
            filters = []
            if service_name:
                filters.append(f'resource.service.name="{service_name}"')
            filters.append(f"duration>{min_duration}")

            query = " && ".join(filters)
            query = f"{{{query}}}"

            base_url = get_base_url(self._toolset.grafana_config)
            traces_summary = query_tempo_traces(
                base_url=base_url,
                api_key=self._toolset.grafana_config.api_key,
                headers=self._toolset.grafana_config.headers,
                query=query,
                start=start,
                end=end,
                limit=params.get("limit", 50),
            )

            # Group traces by specified attributes
            grouped_analysis = {}
            traces = traces_summary.get("traces", [])

            # For each trace, fetch full details to get attributes
            for trace_summary in traces[
                : params.get("limit", 50)
            ]:  # Limit to avoid too many API calls
                trace_id = trace_summary.get("traceID")
                if not trace_id:
                    continue

                try:
                    # Fetch raw trace data to get span attributes
                    url = f"{base_url}/api/traces/{trace_id}"
                    response = requests.get(
                        url,
                        headers=build_headers(
                            api_key=self._toolset.grafana_config.api_key,
                            additional_headers=self._toolset.grafana_config.headers,
                        ),
                        timeout=5,
                    )
                    response.raise_for_status()
                    trace_raw = response.json()

                    # Extract attributes from all spans in the trace
                    attr_values = {}
                    for attr in group_by:
                        attr_values[attr] = "unknown"

                    # Search through batches and spans for attributes
                    for batch in trace_raw.get("batches", []):
                        # Check resource attributes first (e.g., service.name, k8s.pod.name)
                        for resource_attr in batch.get("resource", {}).get(
                            "attributes", []
                        ):
                            attr_key = resource_attr.get("key", "")
                            if attr_key in group_by:
                                attr_value = (
                                    list(resource_attr.get("value", {}).values())[0]
                                    if resource_attr.get("value")
                                    else "unknown"
                                )
                                attr_values[attr_key] = str(attr_value)

                        for scope_spans in batch.get("scopeSpans", []):
                            for span_data in scope_spans.get("spans", []):
                                # Check span attributes
                                for span_attr in span_data.get("attributes", []):
                                    attr_key = span_attr.get("key", "")
                                    if attr_key in group_by:
                                        # Extract the value from the attribute
                                        attr_value = (
                                            list(span_attr.get("value", {}).values())[0]
                                            if span_attr.get("value")
                                            else "unknown"
                                        )
                                        attr_values[attr_key] = str(attr_value)

                    # Build the grouping key from extracted attributes
                    group_key = ", ".join(
                        [
                            f"{attr}={attr_values.get(attr, 'unknown')}"
                            for attr in group_by
                        ]
                    )

                    if group_key not in grouped_analysis:
                        grouped_analysis[group_key] = {
                            "count": 0,
                            "total_duration_ms": 0,
                            "avg_duration_ms": 0,
                            "min_duration_ms": float("inf"),
                            "max_duration_ms": 0,
                        }

                    duration_ms = trace_summary.get("durationMs", 0)
                    grouped_analysis[group_key]["count"] += 1
                    grouped_analysis[group_key]["total_duration_ms"] += duration_ms
                    grouped_analysis[group_key]["min_duration_ms"] = min(
                        grouped_analysis[group_key]["min_duration_ms"], duration_ms
                    )
                    grouped_analysis[group_key]["max_duration_ms"] = max(
                        grouped_analysis[group_key]["max_duration_ms"], duration_ms
                    )

                except Exception:
                    # If we can't fetch the trace, skip it
                    continue

            # Calculate averages
            for key in grouped_analysis:
                if grouped_analysis[key]["count"] > 0:
                    grouped_analysis[key]["avg_duration_ms"] = round(
                        grouped_analysis[key]["total_duration_ms"]
                        / grouped_analysis[key]["count"],
                        2,
                    )
                    grouped_analysis[key]["min_duration_ms"] = round(
                        grouped_analysis[key]["min_duration_ms"], 2
                    )
                    grouped_analysis[key]["max_duration_ms"] = round(
                        grouped_analysis[key]["max_duration_ms"], 2
                    )
                    grouped_analysis[key]["total_duration_ms"] = round(
                        grouped_analysis[key]["total_duration_ms"], 2
                    )

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=yaml.dump(grouped_analysis),
                params=params,
            )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error analyzing traces: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{toolset_name_for_one_liner(self._toolset.name)}: Analyze traces by attributes"


class FindSlowOperations(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="find_slow_operations",
            description="Identifies slow operations within traces based on span durations and attributes.",
            parameters={
                "service_name": ToolParameter(
                    description="Service to analyze",
                    type="string",
                    required=False,
                ),
                "operation_attribute": ToolParameter(
                    description="Span attribute that identifies operation type",
                    type="string",
                    required=False,
                ),
                "min_duration": ToolParameter(
                    description="Minimum duration to consider slow",
                    type="string",
                    required=True,
                ),
                "group_by": ToolParameter(
                    description="Additional attributes to group by",
                    type="array",
                    required=False,
                ),
                "start_datetime": ToolParameter(
                    description="Start time for search",
                    type="string",
                    required=False,
                ),
                "end_datetime": ToolParameter(
                    description="End time for search",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            min_duration = get_param_or_raise(params, "min_duration")
            service_name = params.get("service_name")

            start, end = process_timestamps_to_int(
                params.get("start_datetime"),
                params.get("end_datetime"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )

            # Build query for slow operations
            filters = [f"duration>{min_duration}"]
            if service_name:
                filters.append(f'resource.service.name="{service_name}"')

            query = " && ".join(filters)
            query = f"{{{query}}}"

            base_url = get_base_url(self._toolset.grafana_config)
            traces = query_tempo_traces(
                base_url=base_url,
                api_key=self._toolset.grafana_config.api_key,
                headers=self._toolset.grafana_config.headers,
                query=query,
                start=start,
                end=end,
                limit=50,
            )

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=format_traces_list(traces),
                params=params,
            )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error finding slow operations: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{toolset_name_for_one_liner(self._toolset.name)}: Find slow operations"


class CompareTracePeriods(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="compare_trace_periods",
            description="Compares trace patterns between two time periods to identify changes in performance or behavior.",
            parameters={
                "service_name": ToolParameter(
                    description="Service to compare",
                    type="string",
                    required=True,
                ),
                "baseline_start": ToolParameter(
                    description="Baseline period start time",
                    type="string",
                    required=True,
                ),
                "baseline_end": ToolParameter(
                    description="Baseline period end time",
                    type="string",
                    required=True,
                ),
                "comparison_start": ToolParameter(
                    description="Comparison period start time",
                    type="string",
                    required=True,
                ),
                "comparison_end": ToolParameter(
                    description="Comparison period end time",
                    type="string",
                    required=True,
                ),
                "attributes_to_compare": ToolParameter(
                    description="Span attributes to compare",
                    type="array",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            service_name = get_param_or_raise(params, "service_name")

            # Get baseline traces
            baseline_start, baseline_end = process_timestamps_to_int(
                params.get("baseline_start"),
                params.get("baseline_end"),
                default_time_span_seconds=3600,
            )

            comparison_start, comparison_end = process_timestamps_to_int(
                params.get("comparison_start"),
                params.get("comparison_end"),
                default_time_span_seconds=3600,
            )

            query = f'{{resource.service.name="{service_name}"}}'
            base_url = get_base_url(self._toolset.grafana_config)

            # Fetch baseline traces
            baseline_traces = query_tempo_traces(
                base_url=base_url,
                api_key=self._toolset.grafana_config.api_key,
                headers=self._toolset.grafana_config.headers,
                query=query,
                start=baseline_start,
                end=baseline_end,
                limit=100,
            )

            # Fetch comparison traces
            comparison_traces = query_tempo_traces(
                base_url=base_url,
                api_key=self._toolset.grafana_config.api_key,
                headers=self._toolset.grafana_config.headers,
                query=query,
                start=comparison_start,
                end=comparison_end,
                limit=100,
            )

            # Compare the two sets
            comparison_result = {
                "baseline_count": len(baseline_traces.get("traces", [])),
                "comparison_count": len(comparison_traces.get("traces", [])),
                "baseline_period": f"{baseline_start} to {baseline_end}",
                "comparison_period": f"{comparison_start} to {comparison_end}",
            }

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=yaml.dump(comparison_result),
                params=params,
            )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error comparing periods: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return (
            f"{toolset_name_for_one_liner(self._toolset.name)}: Compare trace periods"
        )


class ListServices(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="list_services",
            description="Lists all services that have traces in Tempo, optionally filtered by namespace",
            parameters={
                "namespace": ToolParameter(
                    description="Filter services by Kubernetes namespace",
                    type="string",
                    required=False,
                ),
                "start_datetime": ToolParameter(
                    description="Start time for search (RFC3339 or relative)",
                    type="string",
                    required=False,
                ),
                "end_datetime": ToolParameter(
                    description="End time for search (RFC3339 or relative)",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            start, end = process_timestamps_to_int(
                params.get("start_datetime"),
                params.get("end_datetime"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )

            base_url = get_base_url(self._toolset.grafana_config)

            # Get all service names
            services_url = f"{base_url}/api/v2/search/tag/service.name/values?start={start}&end={end}"

            response = requests.get(
                services_url,
                headers=build_headers(
                    api_key=self._toolset.grafana_config.api_key,
                    additional_headers=self._toolset.grafana_config.headers,
                ),
                timeout=10,
            )
            response.raise_for_status()
            services_data = response.json()
            services = services_data.get("tagValues", [])

            # If namespace filter provided, get traces for each service and filter
            if params.get("namespace"):
                namespace = params["namespace"]
                filtered_services = []

                for service in services:
                    # Check if this service has traces in the specified namespace
                    query = f'{{resource.service.name="{service}" && resource.k8s.namespace.name="{namespace}"}}'
                    traces = query_tempo_traces(
                        base_url=base_url,
                        api_key=self._toolset.grafana_config.api_key,
                        headers=self._toolset.grafana_config.headers,
                        query=query,
                        start=start,
                        end=end,
                        limit=1,  # Just check if any exist
                    )

                    if traces.get("traces"):
                        filtered_services.append(service)

                services = filtered_services

            # Get basic stats for each service
            service_stats = []
            for service in services:
                query = f'{{resource.service.name="{service}"}}'
                if params.get("namespace"):
                    query = f'{{resource.service.name="{service}" && resource.k8s.namespace.name="{params["namespace"]}"}}'

                # Get a sample of traces for basic stats
                traces = query_tempo_traces(
                    base_url=base_url,
                    api_key=self._toolset.grafana_config.api_key,
                    headers=self._toolset.grafana_config.headers,
                    query=query,
                    start=start,
                    end=end,
                    limit=100,
                )

                trace_list = traces.get("traces", [])
                if trace_list:
                    durations = [
                        t.get("durationMs", 0)
                        for t in trace_list
                        if t.get("durationMs", 0) > 0
                    ]
                    if durations:
                        service_stats.append(
                            {
                                "service_name": service,
                                "trace_count_sample": len(durations),
                                "avg_duration_ms": round(
                                    sum(durations) / len(durations), 2
                                ),
                                "min_duration_ms": round(min(durations), 2),
                                "max_duration_ms": round(max(durations), 2),
                            }
                        )

            # Sort by average duration (slowest first)
            service_stats.sort(key=lambda x: x["avg_duration_ms"], reverse=True)

            result = {
                "total_services": len(services),
                "services": service_stats if service_stats else services,
            }

            if params.get("namespace"):
                result["namespace_filter"] = params["namespace"]

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=yaml.dump(result, default_flow_style=False, sort_keys=False),
                params=params,
            )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error listing services: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{toolset_name_for_one_liner(self._toolset.name)}: List services"


class FetchTracesComparativeSample(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="fetch_traces_comparative_sample",
            description="""Fetches statistics and representative samples of fast, slow, and typical traces for comparative analysis to identify performance patterns.

Examples:
- For service latency: service_name="payment" (matches "payment-service" too)
- For namespace issues: namespace="production"
- Combined: service_name="auth", namespace="staging"

The tool automatically compares fast vs slow traces and highlights attribute differences. Usually this is the best first tool to call when investigating trace data as it gives a fantastic overview.""",
            parameters={
                "service_name": ToolParameter(
                    description="Service to analyze (partial match supported, e.g., 'payment' matches 'payment-service')",
                    type="string",
                    required=False,
                ),
                "namespace": ToolParameter(
                    description="Kubernetes namespace to filter traces (e.g., 'production', 'staging')",
                    type="string",
                    required=False,
                ),
                "base_query": ToolParameter(
                    description="Custom TraceQL filter. If not provided, service_name and/or namespace will be used",
                    type="string",
                    required=False,
                ),
                "sample_size": ToolParameter(
                    description="Number of traces to fetch from each category (fast/slow/typical). Default 5",
                    type="integer",
                    required=False,
                ),
                "start_datetime": ToolParameter(
                    description="Start time for analysis (RFC3339 or relative)",
                    type="string",
                    required=False,
                ),
                "end_datetime": ToolParameter(
                    description="End time for analysis (RFC3339 or relative)",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Build base query from parameters
            if params.get("base_query"):
                base_query = params["base_query"]
            else:
                filters = []

                # Add service filter (with smart matching)
                if params.get("service_name"):
                    service = params["service_name"]
                    # Try exact match first, then with -service suffix, then regex
                    # For now, use regex for flexibility
                    filters.append(f'resource.service.name=~"{service}.*"')

                # Add namespace filter
                if params.get("namespace"):
                    namespace = params["namespace"]
                    filters.append(f'resource.k8s.namespace.name="{namespace}"')

                if not filters:
                    return StructuredToolResult(
                        status=ToolResultStatus.ERROR,
                        error="Either base_query, service_name, or namespace is required",
                        params=params,
                    )

                base_query = " && ".join(filters)

            sample_size = params.get("sample_size", 5)

            start, end = process_timestamps_to_int(
                params.get("start_datetime"),
                params.get("end_datetime"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )

            base_url = get_base_url(self._toolset.grafana_config)

            # Step 1: Get overall trace statistics
            stats_query = f"{{{base_query}}}"
            all_traces_summary = query_tempo_traces(
                base_url=base_url,
                api_key=self._toolset.grafana_config.api_key,
                headers=self._toolset.grafana_config.headers,
                query=stats_query,
                start=start,
                end=end,
                limit=1000,  # Get enough for good statistics
            )

            traces = all_traces_summary.get("traces", [])
            if len(traces) == 0:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="No traces found matching the query",
                    params=params,
                )

            # Calculate statistics
            durations = [
                t.get("durationMs", 0) for t in traces if t.get("durationMs", 0) > 0
            ]
            durations.sort()

            if len(durations) == 0:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="No traces with valid duration found",
                    params=params,
                )

            stats = {
                "total_traces_analyzed": len(durations),
                "avg_duration_ms": round(sum(durations) / len(durations), 2),
                "min_duration_ms": round(durations[0], 2),
                "max_duration_ms": round(durations[-1], 2),
                "p50_duration_ms": round(durations[len(durations) // 2], 2),
                "p90_duration_ms": round(
                    durations[min(int(len(durations) * 0.9), len(durations) - 1)], 2
                ),
                "p99_duration_ms": round(
                    durations[min(int(len(durations) * 0.99), len(durations) - 1)], 2
                ),
            }

            # Step 2: Get slowest traces (sorted by duration descending)
            slow_traces_data = []
            # Sort traces by duration descending and take top N
            sorted_slow = sorted(
                traces, key=lambda x: x.get("durationMs", 0), reverse=True
            )[:sample_size]

            for trace_summary in sorted_slow:
                trace_id = trace_summary.get("traceID")
                if not trace_id:
                    continue

                # Fetch full trace details
                try:
                    url = f"{base_url}/api/traces/{trace_id}"
                    response = requests.get(
                        url,
                        headers=build_headers(
                            api_key=self._toolset.grafana_config.api_key,
                            additional_headers=self._toolset.grafana_config.headers,
                        ),
                        timeout=5,
                    )
                    response.raise_for_status()
                    trace_raw = response.json()

                    # Extract key attributes from the trace
                    trace_attributes = self._extract_trace_attributes(trace_raw)

                    # Build span hierarchy for analysis
                    root_spans = build_span_hierarchy(trace_raw)
                    slowest_spans = self._find_slowest_spans(root_spans, 3)

                    slow_traces_data.append(
                        {
                            "trace_id": trace_id,
                            "duration_ms": round(trace_summary.get("durationMs", 0), 2),
                            "root_service": trace_summary.get(
                                "rootServiceName", "unknown"
                            ),
                            "key_attributes": trace_attributes,
                            "slowest_operations": slowest_spans,
                            "span_count": self._count_spans(root_spans),
                        }
                    )
                except Exception:
                    continue

            # Step 3: Get fastest traces (but not trivially fast)
            fast_traces_data = []
            # Filter out very fast traces (likely health checks)
            min_duration_threshold = (
                stats["p50_duration_ms"] * 0.1
            )  # At least 10% of median
            meaningful_fast = [
                t for t in traces if t.get("durationMs", 0) >= min_duration_threshold
            ]
            sorted_fast = sorted(meaningful_fast, key=lambda x: x.get("durationMs", 0))[
                :sample_size
            ]

            for trace_summary in sorted_fast:
                trace_id = trace_summary.get("traceID")
                if not trace_id:
                    continue

                try:
                    url = f"{base_url}/api/traces/{trace_id}"
                    response = requests.get(
                        url,
                        headers=build_headers(
                            api_key=self._toolset.grafana_config.api_key,
                            additional_headers=self._toolset.grafana_config.headers,
                        ),
                        timeout=5,
                    )
                    response.raise_for_status()
                    trace_raw = response.json()

                    trace_attributes = self._extract_trace_attributes(trace_raw)
                    root_spans = build_span_hierarchy(trace_raw)

                    fast_traces_data.append(
                        {
                            "trace_id": trace_id,
                            "duration_ms": round(trace_summary.get("durationMs", 0), 2),
                            "root_service": trace_summary.get(
                                "rootServiceName", "unknown"
                            ),
                            "key_attributes": trace_attributes,
                            "span_count": self._count_spans(root_spans),
                        }
                    )
                except Exception:
                    continue

            # Step 4: Get typical traces (around median)
            typical_traces_data = []
            median = stats["p50_duration_ms"]
            # Find traces within 20% of median
            typical_traces = [
                t
                for t in traces
                if median * 0.8 <= t.get("durationMs", 0) <= median * 1.2
            ][:sample_size]

            for trace_summary in typical_traces:
                trace_id = trace_summary.get("traceID")
                if not trace_id:
                    continue

                try:
                    url = f"{base_url}/api/traces/{trace_id}"
                    response = requests.get(
                        url,
                        headers=build_headers(
                            api_key=self._toolset.grafana_config.api_key,
                            additional_headers=self._toolset.grafana_config.headers,
                        ),
                        timeout=5,
                    )
                    response.raise_for_status()
                    trace_raw = response.json()

                    trace_attributes = self._extract_trace_attributes(trace_raw)
                    root_spans = build_span_hierarchy(trace_raw)

                    typical_traces_data.append(
                        {
                            "trace_id": trace_id,
                            "duration_ms": round(trace_summary.get("durationMs", 0), 2),
                            "root_service": trace_summary.get(
                                "rootServiceName", "unknown"
                            ),
                            "key_attributes": trace_attributes,
                            "span_count": self._count_spans(root_spans),
                        }
                    )
                except Exception:
                    continue

            # Step 5: Analyze patterns
            analysis_insights = self._generate_insights(
                slow_traces_data, fast_traces_data, typical_traces_data
            )

            # Format output
            result = {
                "statistics": stats,
                "slow_traces": slow_traces_data,
                "fast_traces": fast_traces_data,
                "typical_traces": typical_traces_data,
                "pattern_analysis": analysis_insights,
            }

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=yaml.dump(result, default_flow_style=False, sort_keys=False),
                params=params,
            )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error analyzing traces: {str(e)}",
                params=params,
            )

    def _extract_trace_attributes(self, trace_raw: Dict) -> Dict[str, Any]:
        """Extract key attributes from trace for analysis"""
        attributes = {}

        # Common attributes to look for
        interesting_keys = [
            "user.id",
            "user.tier",
            "user.type",
            "user.email",
            "customer.id",
            "promo.code",
            "coupon.code",
            "discount.type",
            "zone.id",
            "region",
            "availability_zone",
            "datacenter",
            "items.count",
            "cart.size",
            "order.total",
            "request.size",
            "db.operation",
            "db.statement",
            "db.table",
            "cache.hit",
            "http.method",
            "http.route",
            "http.status_code",
            "http.url",
            "error",
            "error.message",
            "error.type",
            "feature.flag",
            "experiment.id",
            "version",
            "deployment.id",
            "queue.name",
            "job.type",
            "workflow.step",
        ]

        for batch in trace_raw.get("batches", []):
            # Check resource attributes
            for attr in batch.get("resource", {}).get("attributes", []):
                key = attr.get("key", "")
                if any(
                    k in key.lower()
                    for k in ["service", "version", "namespace", "pod", "node"]
                ):
                    value = (
                        list(attr.get("value", {}).values())[0]
                        if attr.get("value")
                        else None
                    )
                    if value:
                        attributes[key] = value

            # Check span attributes
            for scope_spans in batch.get("scopeSpans", []):
                for span_data in scope_spans.get("spans", []):
                    for attr in span_data.get("attributes", []):
                        key = attr.get("key", "")
                        if key in interesting_keys or any(
                            k in key.lower()
                            for k in ["promo", "zone", "user", "error", "db"]
                        ):
                            value = (
                                list(attr.get("value", {}).values())[0]
                                if attr.get("value")
                                else None
                            )
                            if value and key not in attributes:
                                attributes[key] = value

        return attributes

    def _find_slowest_spans(self, root_spans, limit=3):
        """Find the slowest spans in the trace"""
        all_spans = []

        def collect_spans(span):
            all_spans.append(span)
            for child in span.children:
                collect_spans(child)

        for root in root_spans:
            collect_spans(root)

        # Sort by duration and get top N
        sorted_spans = sorted(all_spans, key=lambda s: s.duration_ms, reverse=True)[
            :limit
        ]

        result = []
        for span in sorted_spans:
            span_info = {
                "operation": span.name,
                "service": span.service_name,
                "duration_ms": round(span.duration_ms, 2),
            }

            # Add relevant attributes
            if span.attributes.get("db.statement"):
                span_info["db_query"] = span.attributes["db.statement"][:100] + "..."
            if span.attributes.get("http.route"):
                span_info["http_route"] = span.attributes["http.route"]

            result.append(span_info)

        return result

    def _count_spans(self, root_spans):
        """Count total number of spans in trace"""
        count = 0

        def count_recursive(span):
            nonlocal count
            count += 1
            for child in span.children:
                count_recursive(child)

        for root in root_spans:
            count_recursive(root)

        return count

    def _generate_insights(self, slow_traces, fast_traces, typical_traces):
        """Generate insights by comparing trace groups"""
        insights = {
            "common_patterns_in_slow_traces": [],
            "common_patterns_in_fast_traces": [],
            "key_differences": [],
        }

        # Analyze attribute patterns
        slow_attrs = {}
        fast_attrs = {}

        # Collect attribute frequencies in slow traces
        for trace in slow_traces:
            for key, value in trace.get("key_attributes", {}).items():
                if key not in slow_attrs:
                    slow_attrs[key] = {}
                slow_attrs[key][str(value)] = slow_attrs[key].get(str(value), 0) + 1

        # Collect attribute frequencies in fast traces
        for trace in fast_traces:
            for key, value in trace.get("key_attributes", {}).items():
                if key not in fast_attrs:
                    fast_attrs[key] = {}
                fast_attrs[key][str(value)] = fast_attrs[key].get(str(value), 0) + 1

        # Find patterns unique to slow traces
        for key, values in slow_attrs.items():
            if len(slow_traces) > 0:
                for value, count in values.items():
                    ratio = count / len(slow_traces)
                    if ratio >= 0.8:  # Present in 80%+ of slow traces
                        fast_count = fast_attrs.get(key, {}).get(value, 0)
                        fast_ratio = (
                            fast_count / len(fast_traces) if len(fast_traces) > 0 else 0
                        )
                        if fast_ratio < 0.2:  # But in less than 20% of fast traces
                            insights["common_patterns_in_slow_traces"].append(
                                f"{key}={value} appears in {int(ratio*100)}% of slow traces but only {int(fast_ratio*100)}% of fast traces"
                            )

        # Check span count differences
        if slow_traces and fast_traces:
            avg_slow_spans = sum(t.get("span_count", 0) for t in slow_traces) / len(
                slow_traces
            )
            avg_fast_spans = sum(t.get("span_count", 0) for t in fast_traces) / len(
                fast_traces
            )
            if avg_slow_spans > avg_fast_spans * 1.5:
                insights["key_differences"].append(
                    f"Slow traces have {avg_slow_spans:.1f} spans on average vs {avg_fast_spans:.1f} for fast traces"
                )

        # Check for missing attributes
        slow_keys = set()
        for trace in slow_traces:
            slow_keys.update(trace.get("key_attributes", {}).keys())

        fast_keys = set()
        for trace in fast_traces:
            fast_keys.update(trace.get("key_attributes", {}).keys())

        only_in_slow = slow_keys - fast_keys
        if only_in_slow:
            insights["key_differences"].append(
                f"Attributes only in slow traces: {', '.join(only_in_slow)}"
            )

        return insights

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{toolset_name_for_one_liner(self._toolset.name)}: Comparative trace analysis"


class GrafanaTempoToolset(BaseGrafanaTempoToolset):
    def __init__(self):
        super().__init__(
            name="grafana/tempo",
            description="Fetches kubernetes traces from Tempo",
            icon_url="https://grafana.com/static/assets/img/blog/tempo.png",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanatempo.html",
            tools=[
                ListServices(self),
                GetTempoTraces(self),
                GetTempoTraceById(self),
                GetTempoTags(self),
                # AnalyzeTracesByAttributes(self),
                # FindSlowOperations(self),
                # CompareTracePeriods(self),
                FetchTracesComparativeSample(self),
            ],
        )
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "toolset_grafana_tempo.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
