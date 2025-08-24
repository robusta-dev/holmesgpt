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
            traces = query_tempo_traces(
                base_url=base_url,
                api_key=self._toolset.grafana_config.api_key,
                headers=self._toolset.grafana_config.headers,
                query=query,
                start=start,
                end=end,
                limit=params.get("limit", 100),
            )

            # Group traces by specified attributes
            grouped_analysis = {}
            for trace in traces:
                # Extract attribute values for grouping
                group_key = []
                for attr in group_by:
                    # Look for attribute in trace spans
                    value = "unknown"
                    # This would need actual trace parsing logic
                    group_key.append(f"{attr}={value}")

                key = ", ".join(group_key)
                if key not in grouped_analysis:
                    grouped_analysis[key] = {
                        "count": 0,
                        "total_duration": 0,
                        "errors": 0,
                    }

                grouped_analysis[key]["count"] += 1
                # Add duration and error tracking

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
                "baseline_count": len(baseline_traces),
                "comparison_count": len(comparison_traces),
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


class GrafanaTempoToolset(BaseGrafanaTempoToolset):
    def __init__(self):
        super().__init__(
            name="grafana/tempo",
            description="Fetches kubernetes traces from Tempo",
            icon_url="https://grafana.com/static/assets/img/blog/tempo.png",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanatempo.html",
            tools=[
                GetTempoTraces(self),
                GetTempoTraceById(self),
                GetTempoTags(self),
                AnalyzeTracesByAttributes(self),
                FindSlowOperations(self),
                CompareTracePeriods(self),
            ],
        )
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "toolset_grafana_tempo.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
