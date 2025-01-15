
from typing import Dict
import yaml
from holmes.core.tools import StaticPrerequisite, Tool, ToolParameter, Toolset, ToolsetTag
from holmes.plugins.toolsets.grafana.tempo_api import query_tempo_traces_by_duration, query_tempo_trace_by_id
from holmes.plugins.toolsets.grafana.loki_api import list_grafana_datasources
from holmes.plugins.toolsets.grafana.common import GrafanaConfig, get_datasource_id, get_grafana_toolset_prerequisite, get_param_or_raise, process_timestamps

class ListAllDatasources(Tool):

    def __init__(self, config:GrafanaConfig):
        super().__init__(
            name = "list_all_datasources",
            description = "Fetches All the data sources in Grafana",
            parameters = {},
        )
        self._config = config

    def invoke(self, params: Dict) -> str:
        datasources= list_grafana_datasources(grafana_url=self._config.url, api_key=self._config.api_key)
        return yaml.dump(datasources)

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return "Fetched Grafana Tempo datasources"

class GetTempoTracesByMinDuration(Tool):

    def __init__(self, config:GrafanaConfig):
        super().__init__(
            name="fetch_tempo_traces_by_min_duration",
            description="""Lists Tempo traces ids that exceed a specified minimum duration in a given time range""",
            parameters={
                "tempo_datasource_id": ToolParameter(
                    description="The ID of the Tempo datasource to use. Call the tool list_grafana_datasources.",
                    type="string",
                    required=True,
                ),
                "min_duration": ToolParameter(
                    description="The minimum duration of traces to fetch, e.g., '5s' for 5 seconds.",
                    type="string",
                    required=True,
                ),
                "start_timestamp": ToolParameter(
                    description="The beginning time boundary for the trace search period. Epoch in seconds. Traces with timestamps before this value will be excluded from the results.",
                    type="string",
                    required=False,
                ),
                "end_timestamp": ToolParameter(
                    description="The ending time boundary for the trace search period. Epoch in seconds. Traces with timestamps after this value will be excluded from the results. Defaults to NOW().",
                    type="string",
                    required=False,
                ),
                "limit": ToolParameter(
                    description="Maximum number of traces to return.",
                    type="string",
                    required=False,
                ),
            },
        )
        self._config = config

    def invoke(self, params: Dict) -> str:
        start, end = process_timestamps(params.get("start_timestamp"), params.get("end_timestamp"))
        traces = query_tempo_traces_by_duration(
            grafana_url=self._config.url,
            api_key=self._config.api_key,
            tempo_datasource_id=get_datasource_id(params, "tempo_datasource_id"),
            min_duration=get_param_or_raise(params, "min_duration"),
            start=start,
            end=end,
            limit=int(params.get("limit", 50)),  # Default to 50 if limit is not provided
        )
        return yaml.dump(traces)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo traces with min_duration={params.get('min_duration')} ({str(params)})"

class GetTempoTraceById(Tool):

    def __init__(self, config:GrafanaConfig):
        super().__init__(
            name="fetch_tempo_trace_by_id",
            description="""Retrieves detailed information about a Tempo trace using its trace ID. Use this to investigate a trace.""",
            parameters={
                "tempo_datasource_id": ToolParameter(
                    description="The ID of the Tempo datasource to use. Call the tool list_grafana_datasources.",
                    type="string",
                    required=True,
                ),
                "trace_id": ToolParameter(
                    description="The unique trace ID to fetch.",
                    type="string",
                    required=True,
                ),
            },
        )
        self._config = config

    def invoke(self, params: Dict) -> str:

        trace_data = query_tempo_trace_by_id(
            grafana_url=self._config.url,
            api_key=self._config.api_key,
            tempo_datasource_id=get_datasource_id(params, "tempo_datasource_id"),
            trace_id=get_param_or_raise(params, "trace_id"),
        )
        return yaml.dump(trace_data)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetched Tempo trace with trace_id={params.get('trace_id')} ({str(params)})"

class GrafanaTempoToolset(Toolset):
    def __init__(self, config:GrafanaConfig):
        super().__init__(
            name = "grafana_Tempo",
            description = "Fetchs kubernetes traces from Tempo",
            icon_url = "https://grafana.com/static/assets/img/blog/tempo.png",
            prerequisites = [
                get_grafana_toolset_prerequisite(config),
                StaticPrerequisite(enabled=config.tempo.enabled, disabled_reason="Tempo toolset explicitly disabled by config")
            ],
            tools = [
                ListAllDatasources(config),
                GetTempoTracesByMinDuration(config),
                GetTempoTraceById(config)
            ],
            tags = [ToolsetTag.CORE, ]
        )
        self.check_prerequisites()
