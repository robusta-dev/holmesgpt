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
from datetime import datetime, timedelta


class BaseCoralogixTool(Tool):
    toolset: "CoralogixToolset"


LOG_LEVEL_TO_SEVERITY = {"DEBUG": 1, "INFO": 2, "WARNING": 3, "ERROR": 4, "CRITICAL": 5}


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

    def _invoke(self, params: Any) -> str:
        app_name = params.get("app_name", None)
        # namespace = None
        pod_name = params.get("pod_name", None)
        log_count = params.get("log_count", 100)
        min_log_level = params.get("min_log_level", "INFO")

        # Compute default timestamps
        end_time = params.get("end_time", datetime.utcnow().isoformat() + "Z")
        start_time = params.get(
            "start_time", (datetime.utcnow() - timedelta(hours=5)).isoformat() + "Z"
        )

        query_filters = []
        # if namespace:
        #     query_filters.append(f"kubernetes.namespace_name:{namespace}")
        if pod_name:
            query_filters.append(f"kubernetes.pod_name:{pod_name}")
        if app_name:
            query_filters.append(f"kubernetes.labels.app:{app_name}")
        if min_log_level:
            min_severity = LOG_LEVEL_TO_SEVERITY.get(
                min_log_level.upper(), 1
            )  # Default to DEBUG (1) if not found
            query_filters.append(f"coralogix.metadata.severity:[{min_severity} TO *]")

        query_string = " AND ".join(query_filters)

        query = {
            "query": f"source logs | lucene '{query_string}' | limit {log_count}",
            "metadata": {
                "syntax": "QUERY_SYNTAX_DATAPRIME",
                "startDate": start_time,
                "endDate": end_time,
            },
        }

        url = f"{self.toolset.coralogix_url_base}/api/v1/dataprime/query"
        headers = {
            "Authorization": f"Bearer {self.toolset.coralogix_api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, headers=headers, json=query)
        logging.info(f"Fetching logs {query}")

        try:
            return self.process_response(response)
        except Exception:
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
        """Extracts timestamp and log values from parsed JSON objects, sorted in ascending order (oldest first)."""
        logs = []

        for data in json_objects:
            if (
                isinstance(data, dict)
                and "result" in data
                and "results" in data["result"]
            ):
                for entry in data["result"]["results"]:
                    try:
                        user_data = json.loads(entry.get("userData", "{}"))
                        timestamp = user_data.get("time", "UNKNOWN_TIMESTAMP")
                        log_message = user_data.get("log", "")

                        if log_message:
                            logs.append(
                                (timestamp, log_message)
                            )  # Store as tuple for sorting

                    except json.JSONDecodeError:
                        logging.error(
                            f"Failed to decode userData JSON: {entry.get('userData')}"
                        )
            else:
                logging.error(f"{data}")

        def parse_timestamp(ts):
            """Parses timestamps with varying precision, truncating extra fractional seconds if needed."""
            if ts == "UNKNOWN_TIMESTAMP":
                return datetime.max

            try:
                # Strip 'Z' at the end and truncate microseconds to 6 digits if necessary
                ts = ts.rstrip("Z")
                if (
                    "." in ts
                ):  # If fractional seconds exist, ensure they are at most 6 digits
                    ts_parts = ts.split(".")
                    ts = f"{ts_parts[0]}.{ts_parts[1][:6]}"  # Keep only first 6 digits of microseconds

                return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                return datetime.strptime(
                    ts, "%Y-%m-%dT%H:%M:%S"
                )  # Fallback for timestamps without fractions

        # Sort logs by timestamp (ascending order)
        logs.sort(key=lambda x: parse_timestamp(x[0]))

        # Return formatted logs
        return [f"{timestamp} {log_message}" for timestamp, log_message in logs]

    def process_response(self, response):
        """Processes the HTTP response and extracts only log outputs."""
        try:
            raw_text = response.text.strip()
            logging.warning(f"raw_text {raw_text}")
            json_objects = self.parse_json_lines(raw_text)
            if not json_objects:
                return "Error: No valid JSON objects found."
            logs = self.extract_logs(json_objects)
            return "\n".join(logs) if logs else "No log output found."
        except Exception as e:
            logging.error(f"Unexpected error processing response: {str(e)}")
            return f"Error: {str(e)}"

    def get_parameterized_one_liner(self, params) -> str:
        return f"coralogix GetLogs(app_name='{params.get('app_name', '*')}', namespace='{ '*'}', pod_name='{params.get('pod_name', '*')}', start_time='{params.get('start_time', (datetime.utcnow() - timedelta(hours=2)).isoformat() + 'Z')}', end_time='{params.get('end_time', datetime.utcnow().isoformat() + 'Z')}', log_count={params.get('log_count', 100)}, min_log_level='{params.get('min_log_level', 'INFO')}')"


class CoralogixToolset(Toolset):
    coralogix_api_key: Optional[str] = None
    coralogix_url_base: Optional[str] = None

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
        if not config:
            return False
        self.coralogix_api_key = config.get("coralogix_api_key", None)
        self.coralogix_url_base = config.get(
            "coralogix_url_base", "https://ng-api-http.eu2.coralogix.com"
        )
        return self.coralogix_api_key
