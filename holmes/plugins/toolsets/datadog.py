import requests
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

    def _invoke(self, params: Any) -> str:
        try:
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

            response = requests.post(url, headers=headers, json=payload)
            logging.info(
                f"Fetching Datadog logs for service {service} from {from_time} to {to_time}"
            )

            if response.status_code == 200:
                data = response.json()
                logs = [
                    log["attributes"].get("message", "[No message]")
                    for log in data.get("data", [])
                ]
                if logs:
                    return "\n".join(logs)
                else:
                    logging.warning(f"No logs found for service {service}")
                    return "[No logs found]"

            logging.warning(
                f"Failed to fetch logs. Status code: {response.status_code}, Response: {response.text}"
            )
        except Exception:
            logging.exception(f"failed to query datadog {params}")
        return f"Failed to fetch logs. Status code: {response.status_code}\n{response.text}"

    def get_parameterized_one_liner(self, params) -> str:
        return f"datadog GetLogs(service='{params.get('service')}', from_time='{params.get('from_time')}', to_time='{params.get('to_time')}')"


class DatadogConfig(BaseModel):
    dd_api_key: Optional[str] = None
    dd_app_key: Optional[str] = None


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

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config:
            return False, ""

        try:
            dd_config = DatadogConfig(**config)
            self.dd_api_key = dd_config.dd_api_key
            self.dd_app_key = dd_config.dd_app_key
            return bool(self.dd_api_key and self.dd_app_key), ""
        except Exception:
            logging.exception("Failed to set up Datadog toolset")
            return False, ""

    def get_example_config(self) -> Dict[str, Any]:
        return {}
