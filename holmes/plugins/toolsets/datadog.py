import requests  # type: ignore
import logging
from typing import Any, Optional, Dict, Tuple
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from pydantic import BaseModel
from holmes.core.tools import StructuredToolResult, ToolResultStatus


class BaseDatadogTool(Tool):
    toolset: "DatadogToolset"


class GetLogs(BaseDatadogTool):
    def __init__(self, toolset: "DatadogToolset"):
        super().__init__(
            name="datadog_get_logs",
            description="Retrieve logs from Datadog",
            parameters={
                "service": ToolParameter(
                    description="The service name to filter logs",
                    type="string",
                    required=True,
                ),
                "from_time": ToolParameter(
                    description="Start time for logs (e.g., '2025-02-23T08:00:00Z')",
                    type="string",
                    required=True,
                ),
                "to_time": ToolParameter(
                    description="End time for logs (e.g., '2025-02-23T11:00:00Z')",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        def success(msg: Any) -> StructuredToolResult:
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=msg,
                params=params,
            )

        def error(msg: str) -> StructuredToolResult:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=msg,
                params=params,
            )

        service = params.get("service")
        from_time = params.get("from_time")
        to_time = params.get("to_time")

        url = "https://api.us5.datadoghq.com/api/v2/logs/events/search"
        headers = {
            "Content-Type": "application/json",
            "DD-API-KEY": self.toolset.dd_api_key,
            "DD-APPLICATION-KEY": self.toolset.dd_app_key,
        }

        payload = {
            "filter": {
                "from": from_time,
                "to": to_time,
                "query": f"service:{service}",
            },
            "sort": "timestamp",
            "page": {"limit": 1000},
        }

        try:
            logging.info(
                f"Fetching Datadog logs for service '{service}' from {from_time} to {to_time}"
            )
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                logs = [
                    log["attributes"].get("message", "[No message]")
                    for log in data.get("data", [])
                ]
                if logs:
                    return success("\n".join(logs))
                else:
                    logging.warning(f"No logs found for service {service}")
                    return success("[No logs found]")

            logging.warning(
                f"Failed to fetch logs. Status code: {response.status_code}, Response: {response.text}"
            )
            return error(
                f"Failed to fetch logs. Status code: {response.status_code}\n{response.text}"
            )

        except Exception as e:
            logging.exception(f"Failed to query Datadog logs for params: {params}")
            return error(f"Exception while querying Datadog: {str(e)}")

    def get_parameterized_one_liner(self, params) -> str:
        return f"datadog GetLogs(service='{params.get('service')}', from_time='{params.get('from_time')}', to_time='{params.get('to_time')}')"


class DatadogConfig(BaseModel):
    dd_api_key: str
    dd_app_key: str


class DatadogToolset(Toolset):
    dd_api_key: Optional[str] = None
    dd_app_key: Optional[str] = None

    def __init__(self):
        super().__init__(
            name="datadog",
            description="Toolset for interacting with Datadog to fetch logs",
            docs_url="https://docs.datadoghq.com/api/latest/logs/",
            icon_url="https://imgix.datadoghq.com//img/about/presskit/DDlogo.jpg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GetLogs(self),
            ],
            experimental=True,
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return (
                False,
                "Datadog toolset is misconfigured. 'dd_api_key' and 'dd_app_key' are required.",
            )

        try:
            dd_config = DatadogConfig(**config)
            self.dd_api_key = dd_config.dd_api_key
            self.dd_app_key = dd_config.dd_app_key
            return True, ""
        except Exception as e:
            logging.exception("Failed to set up Datadog toolset")
            return (False, f"Failed to parse Datadog configuration: {str(e)}")

    def get_example_config(self) -> Dict[str, Any]:
        return {}
