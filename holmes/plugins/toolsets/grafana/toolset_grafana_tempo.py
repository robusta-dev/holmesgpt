from holmes.plugins.toolsets.grafana.common import ONE_HOUR_IN_SECONDS
import os
import yaml
from typing import Any, Dict, List, cast
from pydantic import BaseModel
import requests
from holmes.common.env_vars import load_bool
from holmes.core.tools import (
    Tool,
    ToolParameter,
)
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset
from holmes.plugins.toolsets.grafana.tempo_api import (
    query_tempo_trace_by_id,
    query_tempo_traces,
)
from holmes.plugins.toolsets.grafana.common import (
    GrafanaConfig,
    get_param_or_raise,
    process_timestamps_to_int,
)
from holmes.plugins.toolsets.grafana.trace_parser import format_traces_list

TEMPO_LABELS_ADD_PREFIX = load_bool("TEMPO_LABELS_ADD_PREFIX", True)


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

    def _invoke(self, params: Dict) -> str:
        grafana_url = self._toolset.grafana_config.url
        api_key = self._toolset.grafana_config.api_key
        tempo_datasource_uid = self._toolset.grafana_config.grafana_datasource_uid
        labels = self._toolset.grafana_config.labels

        invalid_params_error = validate_params(
            params, ["service_name", "pod_name", "deployment_name"]
        )
        if invalid_params_error:
            return invalid_params_error

        start, end = process_timestamps_to_int(
            params.get("start_datetime"), params.get("end_datetime")
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

        traces = query_tempo_traces(
            grafana_url=grafana_url,
            api_key=api_key,
            tempo_datasource_uid=tempo_datasource_uid,
            query=query,
            start=start,
            end=end,
            limit=params.get("limit", 50),
        )
        return format_traces_list(traces)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo traces with min_duration={params.get('min_duration')} ({str(params)})"


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

    def _invoke(self, params: Dict) -> str:
        grafana_url = self._toolset._grafana_config.url
        api_key = self._toolset._grafana_config.api_key
        tempo_datasource_uid = self._toolset._grafana_config.grafana_datasource_uid
        start, end = process_timestamps_to_int(
            start=params.get("start_datetime"),
            end=params.get("end_datetime"),
            default_time_span_seconds=8 * ONE_HOUR_IN_SECONDS,
        )

        url = f"{grafana_url}/api/datasources/proxy/uid/{tempo_datasource_uid}/api/v2/search/tags?start={start}&end={end}"

        try:
            response = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
                timeout=60,
            )
            response.raise_for_status()  # Raise an error for non-2xx responses
            data = response.json()
            return yaml.dump(data.get("scopes"))
        except requests.exceptions.RequestException as e:
            raise Exception(
                f"Failed to retrieve trace by ID after retries: {e} \n for URL: {url}"
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo tags ({str(params)})"


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

    def _invoke(self, params: Dict) -> str:
        labels_mapping = self._toolset.grafana_config.labels
        labels = list(labels_mapping.model_dump().values())

        trace_data = query_tempo_trace_by_id(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            tempo_datasource_uid=self._toolset._grafana_config.grafana_datasource_uid,
            trace_id=get_param_or_raise(params, "trace_id"),
            key_labels=labels,
        )
        return trace_data

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo trace with trace_id={params.get('trace_id')} ({str(params)})"


class GrafanaTempoToolset(BaseGrafanaTempoToolset):
    def __init__(self):
        super().__init__(
            name="grafana/tempo",
            description="Fetches kubernetes traces from Tempo",
            icon_url="https://grafana.com/static/assets/img/blog/tempo.png",
            docs_url="https://grafana.com/oss/tempo/",
            tools=[GetTempoTraces(self), GetTempoTraceById(self), GetTempoTags(self)],
        )
        self._load_llm_instructions(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "toolset_grafana_tempo.jinja2")
            )
        )
