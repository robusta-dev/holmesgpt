import requests  # type: ignore
import logging
from typing import Any, Dict, Tuple, List
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)

from pydantic import BaseModel
from holmes.core.tools import StructuredToolResult, ToolResultStatus
from requests.auth import HTTPDigestAuth  # type: ignore
import gzip
import io
from datetime import datetime, timedelta, timezone
import os


class MongoDBConfig(BaseModel):
    public_key: str
    private_key: str
    project_id: str


# https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/
class MongoDBAtlasToolset(Toolset):
    name: str = "MongoDBAtlas"
    description: str = "The MongoDB Atlas API allows access to Mongodb projects and processes. You can find logs, alerts, events, slow quereies and various metrics to understand the state of Mongodb projects."
    docs_url: str = (
        "https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/"
    )
    icon_url: str = "https://webimages.mongodb.com/_com_assets/cms/kuyjf3vea2hg34taa-horizontal_default_slate_blue.svg?auto=format%252Ccompress"
    tags: List[ToolsetTag] = [ToolsetTag.CORE]

    def __init__(self):
        super().__init__(
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                ReturnProjectAlerts(toolset=self),
                ReturnProjectProcesses(toolset=self),
                ReturnProjectSlowQueries(toolset=self),
                ReturnEventsFromProject(toolset=self),
                ReturnLogsForProcessInPorject(toolset=self),
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
            self.config: Dict = MongoDBConfig(**config).model_dump()
            return True, ""
        except Exception:
            logging.exception("Failed to set up MongoDBAtlas toolset")
            return False, ""

    def get_example_config(self) -> Dict[str, Any]:
        return {}


class MongoDBAtlasBaseTool(Tool):
    toolset: MongoDBAtlasToolset

    def get_parameterized_one_liner(self, params) -> str:
        return f"MongoDB {self.name} project {self.toolset.config.get('project_id')} {params}"


class ReturnProjectAlerts(MongoDBAtlasBaseTool):
    name: str = "atlas_return_project_alerts"
    description: str = "Returns all project alerts. These alerts apply to all components in one project. You receive an alert when a monitored component meets or exceeds a value you set."

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            url = "https://cloud.mongodb.com/api/atlas/v2/groups/{project_id}/alerts".format(
                project_id=self.toolset.config.get("project_id")
            )
            response = requests.get(
                url=url,
                headers={"Accept": "application/vnd.atlas.2025-03-12+json"},
                auth=HTTPDigestAuth(
                    self.toolset.config.get("public_key"),
                    self.toolset.config.get("private_key"),
                ),
            )
            response.raise_for_status()
            if response.ok:
                res = response.json()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS
                    if res.get("totalCount", 0)
                    else ToolResultStatus.NO_DATA,
                    data=res,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    data=f"Failed {self.name}.\n{response.text}",
                    return_code=response.status_code,
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Exception {self.name}: {str(e)}",
                params=params,
            )


class ReturnProjectProcesses(MongoDBAtlasBaseTool):
    name: str = "atlas_return_project_processes"
    description: str = "Returns details of all processes for the specified project. Useful for getting logs and data for specific project"

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            url = "https://cloud.mongodb.com/api/atlas/v2/groups/{project_id}/processes".format(
                project_id=self.toolset.config.get("project_id")
            )
            response = requests.get(
                url=url,
                headers={"Accept": "application/vnd.atlas.2025-03-12+json"},
                auth=HTTPDigestAuth(
                    self.toolset.config.get("public_key"),
                    self.toolset.config.get("private_key"),
                ),
            )
            response.raise_for_status()
            if response.ok:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS, data=response.json(), params=params
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed {self.name}. \n{response.text}",
                    return_code=response.status_code,
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception {self.name}: {str(e)}",
                params=params,
            )


# https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Performance-Advisor/operation/listSlowQueries
class ReturnProjectSlowQueries(MongoDBAtlasBaseTool):
    name: str = "atlas_return_project_processes_slow_queries"
    description: str = "Returns log lines for slow queries that the Performance Advisor and Query Profiler identified for a specific process in a specific project. requires fetching the project processes first. returns queries from the last 24 hours."
    url: str = "https://cloud.mongodb.com/api/atlas/v2/groups/{project_id}/processes/{process_id}/performanceAdvisor/slowQueryLogs?includeMetrics=true"
    parameters: Dict[str, ToolParameter] = {
        "process_id": ToolParameter(
            description="Combination of host and port that serves the MongoDB process. call tool atlas_return_project_processes tool to get host+port of project procecess.",
            type="string",
            required=True,
        ),
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            url = self.url.format(
                project_id=self.toolset.config.get("project_id"),
                process_id=params.pop("process_id", ""),
            )
            response = requests.get(
                url=url,
                headers={"Accept": "application/vnd.atlas.2025-03-12+json"},
                auth=HTTPDigestAuth(
                    self.toolset.config.get("public_key"),
                    self.toolset.config.get("private_key"),
                ),
            )
            response.raise_for_status()
            if response.ok:
                res = response.json()
                status = (
                    ToolResultStatus.SUCCESS
                    if res.get("slowQueries", [])
                    else ToolResultStatus.NO_DATA
                )
                return StructuredToolResult(status=status, data=res, params=params)
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed {self.name}. \n{response.text}",
                    return_code=response.status_code,
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception {self.name}: {str(e)}",
                params=params,
            )


# https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Events/operation/listProjectEvents
class ReturnEventsFromProject(MongoDBAtlasBaseTool):
    name: str = "atlas_return_events_from_project"
    description: str = "Returns events for the specified project. Events identify significant database, security activities or status changes. maximum of 500 events. can only query the last 4 hours."
    url: str = "https://cloud.mongodb.com/api/atlas/v2/groups/{projectId}/events"

    def _invoke(self, params: Any) -> StructuredToolResult:
        params.update({"itemsPerPage": 500})
        try:
            now_utc = datetime.now(timezone.utc)
            four_hours_ago = now_utc - timedelta(hours=4)
            iso_timestamp = four_hours_ago.isoformat()
            url = self.url.format(projectId=self.toolset.config.get("project_id"))
            response = requests.get(
                url=url,
                headers={"Accept": "application/vnd.atlas.2025-03-12+json"},
                auth=HTTPDigestAuth(
                    self.toolset.config.get("public_key"),
                    self.toolset.config.get("private_key"),
                ),
                params={"minDate": iso_timestamp},
            )

            # todo chagne to natan structure.
            response.raise_for_status()
            if response.ok:
                res = response.json()
                simplified_events = [
                    {
                        "created": event.get("created"),
                        "eventTypeName": event.get("eventTypeName"),
                    }
                    for event in res.get("results", [])
                ]
                status = (
                    ToolResultStatus.SUCCESS
                    if simplified_events
                    else ToolResultStatus.NO_DATA
                )
                res["results"] = simplified_events
                return StructuredToolResult(status=status, data=res, params=params)
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed {self.name}. \n{response.text}",
                    return_code=response.status_code,
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception {self.name}: {str(e)}",
                params=params,
            )


# https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Monitoring-and-Logs/operation/getHostLogs
class ReturnLogsForProcessInPorject(MongoDBAtlasBaseTool):
    name: str = "atlas_return_logs_for_host_in_project"
    description: str = "Returns log messages for the specified host for the specified project of the last 1 hour."
    url: str = "https://cloud.mongodb.com/api/atlas/v2/groups/{project_id}/clusters/{process_id}/logs/mongodb.gz"
    parameters: Dict[str, ToolParameter] = {
        "hostName": ToolParameter(
            description="The host must be the hostname, FQDN, IPv4 address, or IPv6 address of the host that runs the MongoDB process (mongod or mongos).",
            type="string",
            required=True,
        ),
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        one_hour_ago = int(one_hour_ago.timestamp())
        try:
            url = self.url.format(
                project_id=self.toolset.config.get("project_id"),
                process_id=params.get("hostName", ""),
            )
            response = requests.get(
                url=url,
                headers={"Accept": "application/vnd.atlas.2025-03-12+gzip"},
                auth=HTTPDigestAuth(
                    self.toolset.config.get("public_key"),
                    self.toolset.config.get("private_key"),
                ),
                params={"startDate": one_hour_ago},
            )
            response.raise_for_status()
            if response.ok:
                with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
                    text_data = gz.read().decode("utf-8")
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS, data=text_data, params=params
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed {self.name}. \n{response.text}",
                    return_code=response.status_code,
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Exception {self.name}: {str(e)}",
                params=params,
            )
