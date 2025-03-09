import requests
import json
import logging
from typing import Any, Optional
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from pydantic import BaseModel


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

    def _invoke(self, params: Any) -> str:
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

        response = requests.post(url, headers=headers, json=query)
        logging.info(f"Getting new relic logs for app {app} since {since}")
        if response.status_code == 200:
            data = response.json()
            return json.dumps(data, indent=2)
        else:
            return f"Failed to fetch logs. Status code: {response.status_code}\n{response.text}"

    def get_parameterized_one_liner(self, params) -> str:
        return f"newrelic GetLogs(app='{params.get('app')}', since='{params.get('since')}')"


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

    def _invoke(self, params: Any) -> str:
        duration = params.get("duration")
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

        response = requests.post(url, headers=headers, json=query)
        logging.info(f"Getting newrelic traces longer than {duration}s")
        if response.status_code == 200:
            data = response.json()
            return json.dumps(data, indent=2)
        else:
            return f"Failed to fetch traces. Status code: {response.status_code}\n{response.text}"

    def get_parameterized_one_liner(self, params) -> str:
        if "trace_id" in params and params["trace_id"]:
            return f"newrelic GetTraces(trace_id='{params.get('trace_id')}')"
        return f"newrelic GetTraces(duration={params.get('duration')})"


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
            docs_url="https://docs.newrelic.com/docs/apis/nerdgraph-api/",
            icon_url="https://companieslogo.com/img/orig/NEWR-de5fcb2e.png?t=1720244493",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetLogs(self),
                GetTraces(self),
            ],
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config:
            return False

        try:
            nr_config = NewrelicConfig(**config)
            self.nr_account_id = nr_config.nr_account_id
            self.nr_api_key = nr_config.nr_api_key
            return self.nr_account_id and self.nr_api_key
        except Exception:
            logging.exception("Failed to set up new relic toolset")
            return False
