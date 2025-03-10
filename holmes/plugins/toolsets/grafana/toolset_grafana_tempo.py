import os
from typing import Dict
import requests
import yaml
from logfmter import Logfmter
from holmes.core.tools import (
    Tool,
    ToolParameter,
)
from holmes.plugins.prompts import load_and_render_prompt
from holmes.plugins.toolsets.grafana.base_grafana_toolset import BaseGrafanaToolset
from holmes.plugins.toolsets.grafana.tempo_api import (
    execute_tempo_query_with_retry,
    query_tempo_traces_by_duration,
    query_tempo_trace_by_id,
)
from holmes.plugins.toolsets.grafana.common import (
    get_param_or_raise,
    process_timestamps,
)


class GetTempoTracesByMinDuration(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="fetch_tempo_traces_by_min_duration",
            description="""Lists Tempo traces ids that exceed a specified minimum duration in a given time range""",
            parameters={
                "min_duration": ToolParameter(
                    description="The minimum duration of traces to fetch, e.g., '5s' for 5 seconds.",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the trace search period. String in RFC3339 format. If a negative integer, the number of seconds relative to the end_timestamp. Defaults to negative one hour (-3600)",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the trace search period. String in RFC3339 format. Defaults to NOW().",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of traces to return. Defaults to 50",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        start, end = process_timestamps(
            params.get("start_timestamp"),
            params.get("end_timestamp"),
            output_format="unix"
        )
        traces = query_tempo_traces_by_duration(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            tempo_datasource_uid=self._toolset._grafana_config.grafana_datasource_uid,
            min_duration=get_param_or_raise(params, "min_duration"),
            start=start,
            end=end,
            limit=int(
                params.get("limit", 50)
            ),  # Default to 50 if limit is not provided
        )
        return yaml.dump(traces)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo traces with min_duration={params.get('min_duration')} ({str(params)})"

class GetTempoTracesForService(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="fetch_tempo_traces_for_service",
            description="""Lists Tempo traces ids for a specific service that exceed a specified minimum duration in a given time range""",
            parameters={
                "min_duration": ToolParameter(
                    description="The minimum duration of traces to fetch, e.g., '5s' for 5 seconds.",
                    type="string",
                    required=False,
                ),
                "service_name": ToolParameter(
                    description="The name of the service to fetch traces from",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the trace search period. String in RFC3339 format. If a negative integer, the number of seconds relative to the end_timestamp. Defaults to negative one hour (-3600)",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the trace search period. String in RFC3339 format. Defaults to NOW().",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of traces to return. Defaults to 50",
                    type="string",
                    required=False,
                ),
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        grafana_url=self._toolset._grafana_config.url
        api_key=self._toolset._grafana_config.api_key
        tempo_datasource_uid=self._toolset._grafana_config.grafana_datasource_uid

        start, end = process_timestamps(
            params.get("start_timestamp"), params.get("end_timestamp")
        )

        query_params = {
            "minDuration": get_param_or_raise(params, "min_duration"),
            "start": start,
            "end": end,
            "tags": Logfmter.format_params({
                "service.name": get_param_or_raise(params, "service.name")
            }),
            "limit": params.get("limit", 50),
        }
        traces = execute_tempo_query_with_retry(
            grafana_url, api_key, tempo_datasource_uid, query_params
        )
        return yaml.dump(traces)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo traces with min_duration={params.get('min_duration')} ({str(params)})"

class GetTempoTags(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
        super().__init__(
            name="fetch_tempo_tags",
            description="List the tags available in Tempo",
            parameters={
            },
        )
        self._toolset = toolset

    def _invoke(self, params: Dict) -> str:
        # TODO: add start.end
        grafana_url=self._toolset._grafana_config.url,
        api_key=self._toolset._grafana_config.api_key,
        tempo_datasource_uid=self._toolset._grafana_config.grafana_datasource_uid,

        url = f"{grafana_url}/api/datasources/proxy/uid/{tempo_datasource_uid}/api/v2/search/tags"

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
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(
                f"Failed to retrieve trace by ID after retries: {e} \n for URL: {url}"
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo trace with trace_id={params.get('trace_id')} ({str(params)})"

class GetTempoTraceById(Tool):
    def __init__(self, toolset: BaseGrafanaToolset):
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
        trace_data = query_tempo_trace_by_id(
            grafana_url=self._toolset._grafana_config.url,
            api_key=self._toolset._grafana_config.api_key,
            tempo_datasource_uid=self._toolset._grafana_config.grafana_datasource_uid,
            trace_id=get_param_or_raise(params, "trace_id"),
        )
        return yaml.dump(trace_data)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo trace with trace_id={params.get('trace_id')} ({str(params)})"


class GrafanaTempoToolset(BaseGrafanaToolset):
    def __init__(self):
        super().__init__(
            name="grafana/tempo",
            description="Fetches kubernetes traces from Tempo",
            icon_url="https://grafana.com/static/assets/img/blog/tempo.png",
            docs_url="https://grafana.com/oss/tempo/",
            tools=[
                GetTempoTracesByMinDuration(self),
                GetTempoTracesForService(self),
                GetTempoTraceById(self),
                GetTempoTags(self)
            ],
        )

    def get_prompt(self):
        promt_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tempo_prompt.jinja2'))
        tool_names = [t.name for t in self.tools]
        return load_and_render_prompt(prompt=f"file://{promt_file_path}", context={"tool_names": tool_names})
