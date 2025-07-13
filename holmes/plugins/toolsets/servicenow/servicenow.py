import requests  # type: ignore
import logging
import os
from typing import Any, Dict, Tuple, List
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)

from pydantic import BaseModel, PrivateAttr
from holmes.core.tools import StructuredToolResult, ToolResultStatus
from holmes.plugins.toolsets.utils import (
    process_timestamps_to_rfc3339,
    standard_start_datetime_tool_param_description,
)

DEFAULT_TIME_SPAN_SECONDS = 3600


class ServiceNowConfig(BaseModel):
    api_key: str
    instance: str


class ServiceNowToolset(Toolset):
    name: str = "ServiceNow"
    description: str = "Database containing changes information related to keys, workloads or any service."
    tags: List[ToolsetTag] = [ToolsetTag.CORE]
    _session: requests.Session = PrivateAttr(default=requests.Session())

    def __init__(self):
        super().__init__(
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            experimental=True,
            tools=[
                ReturnChangesInTimerange(toolset=self),
                ReturnChange(toolset=self),
                ReturnChangesWithKeyword(toolset=self),
            ],
        )
        instructions_filepath = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{instructions_filepath}")

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, "Missing config credentials."

        try:
            self.config: Dict = ServiceNowConfig(**config).model_dump()
            self._session.headers.update(
                {
                    "x-sn-apikey": self.config.get("api_key"),
                }
            )

            url = f"https://{self.config.get('instance')}.service-now.com/api/now/v2/table/change_request"
            response = self._session.get(url=url, params={"sysparm_limit": 1})

            return response.ok, ""
        except Exception as e:
            logging.exception(
                "Invalid ServiceNow config. Failed to set up ServiceNow toolset"
            )
            return False, f"Invalid ServiceNow config {e}"

    def get_example_config(self) -> Dict[str, Any]:
        example_config = ServiceNowConfig(
            api_key="now_xxxxxxxxxxxxxxxx", instance="dev12345"
        )
        return example_config.model_dump()


class ServiceNowBaseTool(Tool):
    toolset: ServiceNowToolset

    def return_result(
        self, response: requests.Response, params: Any, field: str = "result"
    ) -> StructuredToolResult:
        response.raise_for_status()
        res = response.json()
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS
            if res.get(field, [])
            else ToolResultStatus.NO_DATA,
            data=res,
            params=params,
        )

    def get_parameterized_one_liner(self, params) -> str:
        return f"ServiceNow {self.name} {params}"


class ReturnChangesInTimerange(ServiceNowBaseTool):
    name: str = "servicenow_return_changes_in_timerange"
    description: str = "Returns all changes requests from a specific time range. These changes tickets can apply to all components. default to changes from the last 1 hour."
    parameters: Dict[str, ToolParameter] = {
        "start": ToolParameter(
            description=standard_start_datetime_tool_param_description(
                DEFAULT_TIME_SPAN_SECONDS
            ),
            type="string",
            required=False,
        )
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        parsed_params = {}
        try:
            (start, _) = process_timestamps_to_rfc3339(
                start_timestamp=params.get("start"),
                end_timestamp=None,
                default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
            )

            url = f"https://{self.toolset.config.get('instance')}.service-now.com/api/now/v2/table/change_request"
            parsed_params.update(
                {
                    "sysparm_fields": "sys_id,number,short_description,type,active,sys_updated_on"
                }
            )
            parsed_params.update({"sysparm_query": f"sys_updated_on>={start}"})

            response = self.toolset._session.get(url=url, params=parsed_params)
            return self.return_result(response, parsed_params)
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Exception {self.name}: {str(e)}",
                params=params,
            )


class ReturnChange(ServiceNowBaseTool):
    name: str = "servicenow_return_change_details"
    description: str = "Returns detailed information for one specific ServiceNow change"
    parameters: Dict[str, ToolParameter] = {
        "sys_id": ToolParameter(
            description="The unique identifier of the change. Use servicenow_return_changes_in_timerange tool to fetch list of changes and use 'sys_id' for further information",
            type="string",
            required=True,
        )
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            url = "https://{instance}.service-now.com/api/now/v2/table/change_request/{sys_id}".format(
                instance=self.toolset.config.get("instance"),
                sys_id=params.get("sys_id"),
            )
            response = self.toolset._session.get(url=url)
            return self.return_result(response, params)
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Exception {self.name}: {str(e)}",
                params=params,
            )


class ReturnChangesWithKeyword(ServiceNowBaseTool):
    name: str = "servicenow_return_changes_with_keyword"
    description: str = "Returns all changes requests where a keyword is contained in the description. good for finding changes related to a key, workload or any object."
    parameters: Dict[str, ToolParameter] = {
        "keyword": ToolParameter(
            description="key, workload or object name. Keyword that will filter service now changes that are related to this keyword or object.",
            type="string",
            required=True,
        )
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        parsed_params = {}
        try:
            url = f"https://{self.toolset.config.get('instance')}.service-now.com/api/now/v2/table/change_request"
            parsed_params.update(
                {
                    "sysparm_fields": "sys_id,number,short_description,type,active,sys_updated_on"
                }
            )
            parsed_params.update(
                {"sysparm_query": f"short_descriptionLIKE{params.get('keyword')}"}
            )
            response = self.toolset._session.get(url=url, params=parsed_params)
            return self.return_result(response, parsed_params)
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Exception {self.name}: {str(e)}",
                params=params,
            )
