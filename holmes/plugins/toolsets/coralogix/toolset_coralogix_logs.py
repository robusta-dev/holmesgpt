import logging
from typing import Any, Optional, Tuple
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)

from holmes.plugins.toolsets.coralogix.api import execute_query, health_check
from holmes.plugins.toolsets.coralogix.utils import CoralogixConfig, format_logs
from holmes.plugins.toolsets.utils import (
    STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
    STANDARD_START_DATETIME_TOOL_PARAM_DESCRIPTION,
    TOOLSET_CONFIG_MISSING_ERROR,
    process_timestamps_to_rfc3339,
)


LOG_LEVEL_TO_SEVERITY = {"DEBUG": 1, "INFO": 2, "WARNING": 3, "ERROR": 4, "CRITICAL": 5}
DEFAULT_LOG_COUNT = 1000
DEFAULT_MIN_LOG_LEVEL = "INFO"


class BaseCoralogixToolset(Toolset):
    config: Optional[CoralogixConfig] = None

    def get_example_config(self):
        example_config = CoralogixConfig(api_key="<cxuw_...>")
        return example_config.model_dump()


class BaseCoralogixTool(Tool):
    toolset: BaseCoralogixToolset


class GetLogs(BaseCoralogixTool):
    def __init__(self, toolset: BaseCoralogixToolset):
        super().__init__(
            name="coralogix_get_logs",
            description="Retrieve logs from Coralogix based on filters",
            parameters={
                "app_name": ToolParameter(
                    description="The application name to filter logs",
                    type="string",
                    required=False,
                ),
                "namespace_name": ToolParameter(
                    description="The Kubernetes namespace to filter logs",
                    type="string",
                    required=False,
                ),
                "pod_name": ToolParameter(
                    description="The specific pod name to filter logs",
                    type="string",
                    required=False,
                ),
                "start": ToolParameter(
                    description=STANDARD_START_DATETIME_TOOL_PARAM_DESCRIPTION,
                    type="string",
                    required=False,
                ),
                "end": ToolParameter(
                    description=STANDARD_END_DATETIME_TOOL_PARAM_DESCRIPTION,
                    type="string",
                    required=False,
                ),
                "log_count": ToolParameter(
                    description=f"Maximum number of logs to retrieve (default: {DEFAULT_LOG_COUNT})",
                    type="integer",
                    required=False,
                ),
                "min_log_level": ToolParameter(
                    description=f"Minimum log level (default: '{DEFAULT_MIN_LOG_LEVEL}')",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        if not self.toolset.config:
            return "The coralogix/logs toolset is not configured"
        app_name = params.get("app_name", None)
        namespace_name = params.get("namespace_name", None)
        pod_name = params.get("pod_name", None)
        log_count = params.get("log_count", DEFAULT_LOG_COUNT)
        min_log_level = params.get("min_log_level", DEFAULT_MIN_LOG_LEVEL)

        (start, end) = process_timestamps_to_rfc3339(
            params.get("start"), params.get("end")
        )

        query_filters = []
        if namespace_name:
            query_filters.append(
                f"{self.toolset.config.labels.namespace}:{namespace_name}"
            )
        if pod_name:
            query_filters.append(f"{self.toolset.config.labels.pod}:{pod_name}")
        if app_name:
            query_filters.append(f"{self.toolset.config.labels.app}:{app_name}")
        if min_log_level:
            min_severity = LOG_LEVEL_TO_SEVERITY.get(
                min_log_level.upper(), 2
            )  # Default to INFO (2) if not found
            query_filters.append(f"coralogix.metadata.severity:[{min_severity} TO *]")

        query_string = " AND ".join(query_filters)

        query = {
            "query": f"source logs | lucene '{query_string}' | limit {log_count}",
            "metadata": {
                "syntax": "QUERY_SYNTAX_DATAPRIME",
                "startDate": start,
                "endDate": end,
            },
        }

        response = execute_query(
            base_url=self.toolset.config.base_url,
            api_key=self.toolset.config.api_key,
            query=query,
        )

        # Do not print tags if they are repeating the query
        add_namespace_tag = not namespace_name and not pod_name
        add_pod_tag = not pod_name

        try:
            return format_logs(
                raw_logs=response.text.strip(),
                add_namespace_tag=add_namespace_tag,
                add_pod_tag=add_pod_tag,
            )
        except Exception:
            logging.error(f"Failed to decode JSON response: {response} {response.text}")
            return f"Failed to decode JSON response. Raw response: {response.text}"

    def get_parameterized_one_liner(self, params) -> str:
        return f"coralogix GetLogs(app_name='{params.get('app_name', '*')}', namespace='{params.get('namespace_name', '*')}', pod_name='{params.get('pod_name', '*')}', start='{params.get('start')}', end='{params.get('end')}', log_count={params.get('log_count', DEFAULT_LOG_COUNT)}, min_log_level='{params.get('min_log_level', DEFAULT_MIN_LOG_LEVEL)}')"


class CoralogixLogsToolset(BaseCoralogixToolset):
    def __init__(self):
        super().__init__(
            name="coralogix/logs",
            description="Toolset for interacting with Coralogix to fetch logs",
            docs_url="https://coralogix.com/docs/",
            icon_url="https://www.coralogix.com/wp-content/uploads/2021/02/coralogix-logo-dark.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetLogs(self),
            ],
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR
        self.config = CoralogixConfig(**config)
        if self.config.api_key:
            return health_check(
                base_url=self.config.base_url, api_key=self.config.api_key
            )
        else:
            return False, "Missing configuration field 'api_key'"
