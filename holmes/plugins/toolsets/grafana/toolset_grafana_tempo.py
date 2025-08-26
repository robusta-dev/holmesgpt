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
from holmes.plugins.toolsets.grafana.trace_parser import format_traces_list
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

    def build_k8s_filters(
        self, params: Dict[str, Any], use_exact_match: bool = True
    ) -> List[str]:
        """Build TraceQL filters for k8s parameters.

        Args:
            params: Dictionary containing k8s parameters
            use_exact_match: If True, uses exact match (=), if False uses regex match (=~)

        Returns:
            List of TraceQL filter strings
        """
        prefix = ""
        if TEMPO_LABELS_ADD_PREFIX:
            prefix = "resource."

        filters = []
        labels = self.grafana_config.labels

        # Define parameter mappings: (param_name, label_attribute)
        parameter_mappings = [
            ("service_name", "service"),
            ("pod_name", "pod"),
            ("namespace_name", "namespace"),
            ("deployment_name", "deployment"),
            ("node_name", "node"),
        ]

        for param_name, label_attr in parameter_mappings:
            value = params.get(param_name)
            if value:
                # Get the label from the config
                label = getattr(labels, label_attr)

                # Build the filter based on match type
                if use_exact_match:
                    filters.append(f'{prefix}{label}="{value}"')
                else:
                    filters.append(f'{prefix}{label}=~".*{value}.*"')

        return filters


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
                    type="string",
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

        filters = self._toolset.build_k8s_filters(params, use_exact_match=True)

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
                f"Failed to retrieve trace by ID after retries: {e} \n for URL: {url}"
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


class FetchTracesSimpleComparison(Tool):
    def __init__(self, toolset: BaseGrafanaTempoToolset):
        super().__init__(
            name="fetch_tempo_traces_comparative_sample",
            description="""Fetches statistics and representative samples of fast, slow, and typical traces for performance analysis.

Important: call this tool first when investigating performance issues via traces. This tool provides comprehensive analysis for identifying patterns.

Examples:
- For service latency: service_name="payment" (matches "payment-service" too)
- For namespace issues: namespace_name="production"
- Combined: service_name="auth", namespace_name="staging\"""",
            parameters={
                "service_name": ToolParameter(
                    description="Service to analyze (partial match supported)",
                    type="string",
                    required=False,
                ),
                "pod_name": ToolParameter(
                    description="Filter traces by pod name (partial match supported)",
                    type="string",
                    required=False,
                ),
                "namespace_name": ToolParameter(
                    description="Kubernetes namespace to filter traces",
                    type="string",
                    required=False,
                ),
                "deployment_name": ToolParameter(
                    description="Filter traces by deployment name (partial match supported)",
                    type="string",
                    required=False,
                ),
                "node_name": ToolParameter(
                    description="Filter traces by node name",
                    type="string",
                    required=False,
                ),
                "base_query": ToolParameter(
                    description="Custom TraceQL filter",
                    type="string",
                    required=False,
                ),
                "sample_count": ToolParameter(
                    description="Number of traces to fetch from each category (fastest/slowest). Default 3",
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
            # Build query
            if params.get("base_query"):
                base_query = params["base_query"]
            else:
                # Use the shared utility with partial matching (regex)
                filters = self._toolset.build_k8s_filters(params, use_exact_match=False)

                # Validate that at least one parameter was provided
                invalid_params_error = validate_params(
                    params,
                    [
                        "service_name",
                        "pod_name",
                        "namespace_name",
                        "deployment_name",
                        "node_name",
                    ],
                )
                if invalid_params_error:
                    return StructuredToolResult(
                        status=ToolResultStatus.ERROR,
                        error=invalid_params_error,
                        params=params,
                    )

                base_query = " && ".join(filters)

            sample_count = params.get("sample_count", 3)

            start, end = process_timestamps_to_int(
                params.get("start_datetime"),
                params.get("end_datetime"),
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )

            base_url = get_base_url(self._toolset.grafana_config)

            # Step 1: Get all trace summaries
            stats_query = f"{{{base_query}}}"
            all_traces_response = query_tempo_traces(
                base_url=base_url,
                api_key=self._toolset.grafana_config.api_key,
                headers=self._toolset.grafana_config.headers,
                query=stats_query,
                start=start,
                end=end,
                limit=1000,
            )

            traces = all_traces_response.get("traces", [])
            if not traces:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data="No traces found matching the query",
                    params=params,
                )

            # Step 2: Sort traces by duration
            sorted_traces = sorted(traces, key=lambda x: x.get("durationMs", 0))

            # Step 3: Calculate basic statistics
            durations = [t.get("durationMs", 0) for t in sorted_traces]
            stats = {
                "trace_count": len(durations),
                "min_ms": durations[0],
                "p25_ms": durations[len(durations) // 4]
                if len(durations) >= 4
                else durations[0],
                "p50_ms": durations[len(durations) // 2],
                "p75_ms": durations[3 * len(durations) // 4]
                if len(durations) >= 4
                else durations[-1],
                "p90_ms": durations[int(len(durations) * 0.9)]
                if len(durations) >= 10
                else durations[-1],
                "p99_ms": durations[int(len(durations) * 0.99)]
                if len(durations) >= 100
                else durations[-1],
                "max_ms": durations[-1],
            }

            # Step 4: Select representative traces to fetch
            fastest_indices = list(range(min(sample_count, len(sorted_traces))))
            slowest_indices = list(
                range(max(0, len(sorted_traces) - sample_count), len(sorted_traces))
            )

            # Add median trace
            median_idx = len(sorted_traces) // 2

            # Step 5: Fetch full trace details
            def fetch_full_trace(trace_summary):
                trace_id = trace_summary.get("traceID")
                if not trace_id:
                    return None

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
                    return {
                        "traceID": trace_id,
                        "durationMs": trace_summary.get("durationMs", 0),
                        "rootServiceName": trace_summary.get(
                            "rootServiceName", "unknown"
                        ),
                        "traceData": response.json(),  # Raw trace data
                    }
                except Exception:
                    return {
                        "traceID": trace_id,
                        "durationMs": trace_summary.get("durationMs", 0),
                        "error": "Failed to fetch full trace",
                    }

            # Fetch the selected traces
            result = {
                "statistics": stats,
                "all_trace_durations_ms": durations,  # All durations for distribution analysis
                "fastest_traces": [
                    fetch_full_trace(sorted_traces[i]) for i in fastest_indices
                ],
                "median_trace": fetch_full_trace(sorted_traces[median_idx]),
                "slowest_traces": [
                    fetch_full_trace(sorted_traces[i]) for i in slowest_indices
                ],
            }

            # Return as YAML for readability
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=yaml.dump(result, default_flow_style=False, sort_keys=False),
                params=params,
            )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error fetching traces: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return (
            f"{toolset_name_for_one_liner(self._toolset.name)}: Simple trace comparison"
        )


class GrafanaTempoToolset(BaseGrafanaTempoToolset):
    def __init__(self):
        super().__init__(
            name="grafana/tempo",
            description="Fetches kubernetes traces from Tempo",
            icon_url="https://grafana.com/static/assets/img/blog/tempo.png",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanatempo.html",
            tools=[
                FetchTracesSimpleComparison(self),
                GetTempoTraces(self),
                GetTempoTraceById(self),
                GetTempoTags(self),
            ],
        )
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "toolset_grafana_tempo.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
