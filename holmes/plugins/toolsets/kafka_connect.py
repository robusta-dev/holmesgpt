# plugins/toolsets/kafka_connect.py
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import ConfigDict

from holmes.core.tools import Tool, ToolParameter, Toolset, ToolsetTag


class BaseKafkaConnectTool(Tool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    toolset: "KafkaConnectToolset"

    def _get(self, endpoint: str) -> requests.Response:
        """Helper function for GET requests to the Connect REST API."""
        base_url = self.toolset.config.get("connect_rest_url", "http://localhost:8083")
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response
        except requests.exceptions.RequestException as e:
            logging.exception(f"Failed to make request to {url}")
            raise ConnectionError(f"Error communicating with Kafka Connect: {e}") from e

    def _post(self, endpoint: str, data: Optional[Dict] = None) -> requests.Response:
         """Helper function for POST requests to the Connect REST API."""
         base_url = self.toolset.config.get("connect_rest_url", "http://localhost:8083")
         url = f"{base_url}{endpoint}"
         headers = {"Content-Type": "application/json"}
         try:
            response = requests.post(url, headers=headers, data=json.dumps(data) if data else None, timeout=10)
            response.raise_for_status()
            return response
         except requests.exceptions.RequestException as e:
            logging.exception(f"Failed to make POST request to {url}")
            raise ConnectionError(f"Error communicating with Kafka Connect: {e}") from e

    def _delete(self, endpoint: str) -> requests.Response:
        """Helper for DELETE requests."""
        base_url = self.toolset.config.get("connect_rest_url", "http://localhost:8083")
        url = f"{base_url}{endpoint}"
        try:
            response = requests.delete(url, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.exception(f"Failed to make DELETE request to {url}")
            raise ConnectionError(f"Error communicating with Kafka Connect: {e}") from e

    def _put(self, endpoint: str, data: Optional[Dict] = None) -> requests.Response:
        """Helper for PUT requests."""
        base_url = self.toolset.config.get("connect_rest_url", "http://localhost:8083")
        url = f"{base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.put(url, headers=headers, data=json.dumps(data) if data else None, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.exception(f"Failed to make PUT request to {url}")
            raise ConnectionError(f"Error communicating with Kafka Connect: {e}") from e

class KafkaConnectListConnectors(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_list_connectors",
            description="List all active connectors in the Kafka Connect cluster.",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        try:
            response = self._get("/connectors?expand=info&expand=status") # Include info and status
            return json.dumps(response.json(), indent=2)
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "kafka_connect_list_connectors()"


class KafkaConnectGetConnectorStatus(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_get_connector_status",
            description="Get the status of a specific connector, including task status.",
            parameters={
                "connector_name": ToolParameter(
                    description="The name of the connector. This is REQUIRED.",
                    type="string",
                    required=True,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_name = params["connector_name"]
        try:
            response = self._get(f"/connectors/{connector_name}/status")
            return json.dumps(response.json(), indent=2)
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_get_connector_status(connector_name='{params.get('connector_name')}')"

class KafkaConnectGetConnectorConfig(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_get_connector_config",
            description="Gets the configuration of a specific connector.",
            parameters = {
                "connector_name": ToolParameter(
                    description="Name of the connector",
                    type="string",
                    required=True
                )
            },
            toolset=toolset
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_name = params["connector_name"]
        try:
            response = self._get(f"/connectors/{connector_name}/config")
            return json.dumps(response.json(), indent=2)
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_get_connector_config(connector_name='{params.get('connector_name')}')"

class KafkaConnectRestartConnectorTask(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name = "kafka_connect_restart_connector_task",
            description="Restarts a connector task",
            parameters = {
                "connector_name": ToolParameter(
                    description="Name of the connector.",
                    type="string",
                    required=True
                ),
                "task_id": ToolParameter(
                    description = "Id of the task to restart.",
                    type = "integer",
                    required = True
                )
            },
            toolset=toolset
        )
    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_name = params["connector_name"]
        task_id = params["task_id"]
        try:
            response = self._post(f"/connectors/{connector_name}/tasks/{task_id}/restart")
            if response.status_code == 202:  # Accepted for processing
               return "Task restart request submitted successfully.  Check status using kafka_connect_get_connector_status."
            elif response.status_code == 204: # No content, but successful.
                return "Task restarted successfully." #Some versions of connect return 204.
            else:
                return f"Task restart failed with status code: {response.status_code}, Response: {response.text}"
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_restart_connector_task(connector_name='{params.get('connector_name')}', task_id={params.get('task_id')})"

class KafkaConnectPauseConnector(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_pause_connector",
            description="Pauses a connector.",
            parameters={
                "connector_name": ToolParameter(
                    description="The name of the connector to pause. This is REQUIRED.",
                    type="string",
                    required=True,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_name = params["connector_name"]
        try:
            response = self._put(f"/connectors/{connector_name}/pause")
            if response.status_code == 202:
                return f"Connector '{connector_name}' pause request submitted successfully."
            else:
                return f"Failed to pause connector '{connector_name}'. Status code: {response.status_code}, Response: {response.text}"

        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_pause_connector(connector_name='{params.get('connector_name')}')"

class KafkaConnectResumeConnector(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_resume_connector",
            description="Resumes a paused connector.",
            parameters={
                "connector_name": ToolParameter(
                    description="The name of the connector to resume. This is REQUIRED.",
                    type="string",
                    required=True,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_name = params["connector_name"]
        try:
            response = self._put(f"/connectors/{connector_name}/resume")
            if response.status_code == 202:
                return f"Connector '{connector_name}' resume request submitted successfully."
            else:
                return f"Failed to resume connector '{connector_name}'. Status code: {response.status_code}, Response: {response.text}"
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_resume_connector(connector_name='{params.get('connector_name')}')"

class KafkaConnectDeleteConnector(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_delete_connector",
            description="Deletes a connector.",
            parameters={
                "connector_name": ToolParameter(
                    description="The name of the connector to delete.  This is REQUIRED.",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )
    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_name = params["connector_name"]
        try:
            response = self._delete(f"/connectors/{connector_name}")
            if response.status_code == 204:  # Successful deletion
                return f"Connector '{connector_name}' deleted successfully."
            else:
                return f"Failed to delete connector '{connector_name}'. Status code: {response.status_code}, Response: {response.text}"
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_delete_connector(connector_name='{params.get('connector_name')}')"

class KafkaConnectListWorkers(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_list_workers",
            description="Lists all active Kafka Connect worker nodes in the cluster.",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        try:
            response = self._get("/connectors?expand=status")  # Use this instead of `/workers`
            data = response.json()
            workers = {connector: details["status"]["worker_id"] for connector, details in data.items()}
            return json.dumps({"active_workers": list(set(workers.values()))}, indent=2)
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "kafka_connect_list_workers()"



class KafkaConnectClusterStatus(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_cluster_status",
            description="Fetches overall Kafka Connect cluster health.",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        try:
            response = self._get("/")
            return json.dumps(response.json(), indent=2)
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "kafka_connect_cluster_status()"


class KafkaConnectValidateConfig(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_validate_config",
            description="Validates a connector configuration before applying it.",
            parameters={
                "connector_type": ToolParameter(
                    description="The type of the connector (e.g., 'source' or 'sink').",
                    type="string",
                    required=True,
                ),
                "config": ToolParameter(
                    description="The JSON configuration of the connector.",
                    type="object",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_type = params["connector_type"]
        config = params["config"]
        try:
            response = self._put(f"/connector-plugins/{connector_type}/config/validate", data=config)
            return json.dumps(response.json(), indent=2)
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_validate_config(connector_type='{params.get('connector_type')}', config={params.get('config')})"


class KafkaConnectListFailedTasks(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_list_failed_tasks",
            description="Lists all failed connector tasks and their error messages.",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        try:
            response = self._get("/connectors?expand=status")
            connectors = response.json()
            failed_tasks = []

            for connector, data in connectors.items():
                for task in data["status"]["tasks"]:
                    if task["state"] == "FAILED":
                        failed_tasks.append({"connector": connector, "task_id": task["id"], "error": task.get("trace", "No error message")})

            return json.dumps(failed_tasks, indent=2) if failed_tasks else "No failed tasks found."
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "kafka_connect_list_failed_tasks()"




class KafkaConnectGetOffsetStatus(BaseKafkaConnectTool):
    def __init__(self, toolset: "KafkaConnectToolset"):
        super().__init__(
            name="kafka_connect_get_offset_status",
            description="Retrieves the offset status for a specific connector.",
            parameters={
                "connector_name": ToolParameter(
                    description="The name of the connector.",
                    type="string",
                    required=True,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> str:
        connector_name = params["connector_name"]
        try:
            response = self._get(f"/connectors/{connector_name}/offsets")
            return json.dumps(response.json(), indent=2)
        except ConnectionError as e:
            return str(e)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_get_offset_status(connector_name='{params.get('connector_name')}')"



class KafkaConnectToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: Dict[str, Any] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="kafka_connect",
            description="Toolset for interacting with Kafka Connect.",
            docs_url="https://docs.confluent.io/platform/current/connect/index.html",
            icon_url="https://d3g9wbak8ap9v2.cloudfront.net/static/images/connect/confluent-connector-logo-color.svg",  # Placeholder
            prerequisites=[],
            tools=[
                KafkaConnectListConnectors(self),
                KafkaConnectGetConnectorStatus(self),
                KafkaConnectGetConnectorConfig(self),
                KafkaConnectRestartConnectorTask(self),
                KafkaConnectPauseConnector(self),
                KafkaConnectResumeConnector(self),
                KafkaConnectDeleteConnector(self),
                KafkaConnectListWorkers(self),
                KafkaConnectClusterStatus(self),
                KafkaConnectValidateConfig(self),
                KafkaConnectListFailedTasks(self),
                KafkaConnectGetOffsetStatus(self),

            ],
            tags=[ToolsetTag.CORE],
            is_default=False,
        )
        if config:
            self.config = config

    def prerequisites_callable(self, config: Dict[str, Any]) -> bool:
        return bool(config.get("connect_rest_url"))

    def get_example_config(self) -> Dict[str, Any]:
        return {"connect_rest_url": "http://localhost:8083"}
