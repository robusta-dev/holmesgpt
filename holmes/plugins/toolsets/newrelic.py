import requests  # type: ignore
import logging
from typing import Any, Optional, Dict
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from pydantic import BaseModel
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.plugins.toolsets.utils import get_param_or_raise, toolset_name_for_one_liner


class BaseNewRelicTool(Tool):
    toolset: "NewRelicToolset"


class GetLogs(BaseNewRelicTool):
    def __init__(self, toolset: "NewRelicToolset"):
        super().__init__(
            name="newrelic_get_logs",
            description="Retrieve logs from New Relic",
            parameters={
                "app": ToolParameter(
                    description="The application name to filter logs",
                    type="string",
                    required=True,
                ),
                "since": ToolParameter(
                    description="Time range to fetch logs (e.g., '1 hour ago')",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        def success(msg: Any) -> StructuredToolResult:
            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=msg,
                params=params,
            )

        def error(msg: str) -> StructuredToolResult:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                data=msg,
                params=params,
            )

        app = params.get("app")
        since = params.get("since")

        query = {
            "query": f"""
            {{
                actor {{
                    account(id: {self.toolset.nr_account_id}) {{
                        nrql(query: \"SELECT * FROM Log WHERE app = '{app}' SINCE {since}\") {{
                            results
                        }}
                    }}
                }}
            }}
            """
        }

        url = "https://api.newrelic.com/graphql"
        headers = {
            "Content-Type": "application/json",
            "Api-Key": self.toolset.nr_api_key,
        }

        try:
            logging.info(f"Getting New Relic logs for app {app} since {since}")
            response = requests.post(url, headers=headers, json=query)  # type: ignore[arg-type]

            if response.status_code == 200:
                return success(response.json())
            else:
                return error(
                    f"Failed to fetch logs. Status code: {response.status_code}\n{response.text}"
                )
        except Exception as e:
            logging.exception("Exception while fetching logs")
            return error(f"Error while fetching logs: {str(e)}")

    def get_parameterized_one_liner(self, params) -> str:
        app = params.get("app", "")
        since = params.get("since", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Get Logs ({app} - {since})"


class GetTraces(BaseNewRelicTool):
    def __init__(self, toolset: "NewRelicToolset"):
        super().__init__(
            name="newrelic_get_traces",
            description="Retrieve traces from New Relic",
            parameters={
                "duration": ToolParameter(
                    description="Minimum trace duration in seconds",
                    type="number",
                    required=True,
                ),
                "trace_id": ToolParameter(
                    description="Specific trace ID to fetch details (optional)",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        def success(msg: Any) -> StructuredToolResult:
            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=msg,
                params=params,
            )

        def error(msg: str) -> StructuredToolResult:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                data=msg,
                params=params,
            )

        duration = get_param_or_raise(params, "duration")
        trace_id = params.get("trace_id")

        if trace_id:
            query_string = f"SELECT * FROM Span WHERE trace.id = '{trace_id}' and duration.ms > {duration * 1000} and span.kind != 'internal'"
        else:
            query_string = f"SELECT * FROM Span WHERE duration.ms > {duration * 1000} and span.kind != 'internal'"

        query = {
            "query": f"""
            {{
                actor {{
                    account(id: {self.toolset.nr_account_id}) {{
                        nrql(query: \"{query_string}\") {{
                            results
                        }}
                    }}
                }}
            }}
            """
        }

        url = "https://api.newrelic.com/graphql"
        headers = {
            "Content-Type": "application/json",
            "Api-Key": self.toolset.nr_api_key,
        }

        try:
            logging.info(f"Getting New Relic traces with duration > {duration}s")
            response = requests.post(url, headers=headers, json=query)  # type: ignore[arg-type]

            if response.status_code == 200:
                return success(response.json())
            else:
                return error(
                    f"Failed to fetch traces. Status code: {response.status_code}\n{response.text}"
                )
        except Exception as e:
            logging.exception("Exception while fetching traces")
            return error(f"Error while fetching traces: {str(e)}")

    def get_parameterized_one_liner(self, params) -> str:
        if "trace_id" in params and params["trace_id"]:
            trace_id = params.get("trace_id", "")
            return f"{toolset_name_for_one_liner(self.toolset.name)}: Get Trace Details ({trace_id})"
        duration = params.get("duration", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Get Traces (>{duration}s)"


class NewrelicConfig(BaseModel):
    nr_api_key: Optional[str] = None
    nr_account_id: Optional[str] = None


class NewRelicToolset(Toolset):
    nr_api_key: Optional[str] = None
    nr_account_id: Optional[str] = None

    def __init__(self):
        super().__init__(
            name="newrelic",
            description="Toolset for interacting with New Relic to fetch logs and traces",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/newrelic/",
            icon_url="https://companieslogo.com/img/orig/NEWR-de5fcb2e.png?t=1720244493",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetLogs(self),
                GetTraces(self),
            ],
            experimental=True,
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(
        self, config: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        if not config:
            return False, "No configuration provided"

        try:
            nr_config = NewrelicConfig(**config)
            self.nr_account_id = nr_config.nr_account_id
            self.nr_api_key = nr_config.nr_api_key

            if not self.nr_account_id or not self.nr_api_key:
                return False, "New Relic account ID or API key is missing"

            return True, None
        except Exception as e:
            logging.exception("Failed to set up New Relic toolset")
            return False, str(e)

    def get_example_config(self) -> Dict[str, Any]:
        return {}
