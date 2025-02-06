import requests
import json
import logging
from typing import Any
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from datetime import datetime, timedelta


class BaseCoralogixTool(Tool):
    toolset: "CoralogixToolset"


class GetLogs(BaseCoralogixTool):
    def __init__(self, toolset: "CoralogixToolset"):
        super().__init__(
            name="coralogix_get_logs",
            description="Retrieve logs from Coralogix based on filters",
            parameters={
                "app_name": ToolParameter(
                    description="The application name to filter logs",
                    type="string",
                    required=False,
                ),
                "namespace": ToolParameter(
                    description="The Kubernetes namespace to filter logs",
                    type="string",
                    required=False,
                ),
                "pod_name": ToolParameter(
                    description="The specific pod name to filter logs",
                    type="string",
                    required=False,
                ),
                "start_time": ToolParameter(
                    description="Start time for log retrieval (default: 2 hours back in ISO format)",
                    type="string",
                    required=False,
                ),
                "end_time": ToolParameter(
                    description="End time for log retrieval (default: now in ISO format)",
                    type="string",
                    required=False,
                ),
                "log_count": ToolParameter(
                    description="Maximum number of logs to retrieve (default: 100)",
                    type="integer",
                    required=False,
                ),
                "min_log_level": ToolParameter(
                    description="Minimum log level (default: 'INFO')",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def invoke(self, params: Any) -> str:
        app_name = params.get("app_name", "*")
        namespace = params.get("namespace", "*")
        pod_name = params.get("pod_name", "*")
        log_count = params.get("log_count", 200)
        min_log_level = params.get("min_log_level", "INFO")

        # Compute default timestamps
        end_time = params.get("end_time", datetime.utcnow().isoformat() + "Z")
        start_time = params.get("start_time", (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z")

        query = {
            "query": f"source logs | lucene 'kubernetes.namespace_name:{namespace} AND kubernetes.pod_name:{pod_name} AND coralogix.metadata.applicationName:{app_name} AND log:({min_log_level})' | limit {log_count}",
            "metadata": {
                "syntax": "QUERY_SYNTAX_DATAPRIME",
                "startDate": start_time,
                "endDate": end_time,
            },
        }

        url = "https://ng-api-http.eu2.coralogix.com/api/v1/dataprime/query"
        headers = {
            "Authorization": f"Bearer {self.toolset.config.get('coralogix_api_key', None)}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, headers=headers, json=query)
        logging.info(f"Fetching logs for app={app_name}, namespace={namespace}, pod={pod_name}, from {start_time} to {end_time}")

        try:
            return self.process_response(response)
        except:
            logging.error(f"Failed to decode JSON response: {response} {response.text}")
            return f"Failed to decode JSON response. Raw response: {response.text}"

    def parse_json_lines(self, raw_text):
        """Parses JSON objects from a raw text response."""
        json_objects = []
        for line in raw_text.strip().split("\n"):  # Split by newlines
            try:
                json_objects.append(json.loads(line))
            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON from line: {line}")
        return json_objects

    def extract_logs(self, json_objects):
        """Extracts only the log values from parsed JSON objects."""
        logs = []
        for data in json_objects:
            if isinstance(data, dict) and "result" in data and "results" in data["result"]:
                for entry in data["result"]["results"]:
                    try:
                        user_data = json.loads(entry.get("userData", "{}"))
                        if "log" in user_data:
                            logs.append(user_data["log"])
                    except json.JSONDecodeError:
                        logging.error(f"Failed to decode userData JSON: {entry.get('userData')}")
        return logs

    def process_response(self, response):
        """Processes the HTTP response and extracts only log outputs."""
        try:
            raw_text = response.text.strip()
            json_objects = self.parse_json_lines(raw_text)
            if not json_objects:
                return "Error: No valid JSON objects found."
            logs = self.extract_logs(json_objects)
            return "\n".join(logs) if logs else "No log output found."
        except Exception as e:
            logging.error(f"Unexpected error processing response: {str(e)}")
            return f"Error: {str(e)}"


    def get_parameterized_one_liner(self, params) -> str:
        return f"coralogix GetLogs(app_name='{params.get('app_name', '*')}', namespace='{params.get('namespace', '*')}', pod_name='{params.get('pod_name', '*')}', start_time='{params.get('start_time', (datetime.utcnow() - timedelta(hours=2)).isoformat() + 'Z')}', end_time='{params.get('end_time', datetime.utcnow().isoformat() + 'Z')}', log_count={params.get('log_count', 100)}, min_log_level='{params.get('min_log_level', 'INFO')}')"


class CoralogixToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="coralogix",
            description="Toolset for interacting with Coralogix to fetch logs",
            docs_url="https://coralogix.com/docs/",
            icon_url="https://www.coralogix.com/wp-content/uploads/2021/02/coralogix-logo-dark.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetLogs(self),
            ],
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        return bool(config.get("coralogix_api_key", None))
