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
from requests.auth import HTTPDigestAuth
import gzip
import io


def success(msg: Any, params: Any) -> StructuredToolResult:
    return StructuredToolResult(
        status=ToolResultStatus.SUCCESS,
        data=msg,
        params=params,
    )


def error(msg: str, params: Any) -> StructuredToolResult:
    return StructuredToolResult(
        status=ToolResultStatus.ERROR,
        data=msg,
        params=params,
    )


class MongoDBConfig(BaseModel):
    public_key: str
    private_key: str
    project_id: str


# https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/  using administration api.
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

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, "Missing config credentials."

        try:
            MongoDBConfig(**config)
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
                return success(response.json(), params)
            else:
                return error(
                    f"Failed {self.name}. Status code: {response.status_code}\n{response.text}",
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return error(f"Exception {self.name}: {str(e)}")


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
                return success(response.json(), params)
            else:
                return error(
                    f"Failed {self.name}. Status code: {response.status_code}\n{response.text}",
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return error(f"Exception {self.name}: {str(e)}", params=params)


class ReturnProjectSlowQueries(MongoDBAtlasBaseTool):
    name: str = "atlas_return_project_slow_queries"
    description: str = "Returns log lines for slow queries that the Performance Advisor and Query Profiler identified for a specific process in a specific project."
    url: str = "https://cloud.mongodb.com/api/atlas/v2/groups/{project_id}/processes/{process_id}/performanceAdvisor/slowQueryLogs?includeMetrics=true"
    parameters: Dict[str, ToolParameter] = {
        "process_id": ToolParameter(
            description="Combination of host and port that serves the MongoDB process. The host must be the hostname, FQDN, IPv4 address, or IPv6 address of the host that runs the MongoDB process (mongod or mongos). The port must be the IANA port on which the MongoDB process listens for requests.",
            type="string",
            required=True,
        ),
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            url = self.url.format(
                project_id=self.toolset.config.get("project_id"),
                process_id=params.get("process_id", ""),
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
                return success(response.json(), params)
            else:
                return error(
                    msg=f"Failed {self.name}. Status code: {response.status_code}\n{response.text}",
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return error(f"Exception {self.name}: {str(e)}", params=params)


# https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Events/operation/listProjectEvents
class ReturnEventsFromProject(MongoDBAtlasBaseTool):
    name: str = "atlas_return_events_from_project"
    description: str = "Returns events for the specified project. Events identify significant database, security activities or status changes."
    url: str = "https://cloud.mongodb.com/api/atlas/v2/groups/{projectId}/events"
    parameters: Dict[str, ToolParameter] = {
        "itemsPerPage": ToolParameter(
            description="Number of the page that displays the current set of the total objects that the response returns. >=1 default 1",
            type="integer",
            required=True,
        ),
        "pageNum": ToolParameter(
            description="Number of items that the response returns per page. [200-500] default 200",
            type="integer",
            required=True,
        ),
        "minDate": ToolParameter(
            description="Date and time from when MongoDB Cloud starts returning events. This parameter uses the ISO 8601 timestamp format in UTC. default to 6 hours ago",
            type="string",
            required=True,
        ),
        "maxDate": ToolParameter(
            description="Date and time from when MongoDB Cloud stops returning events. This parameter uses the ISO 8601 timestamp format in UTC.",
            type="string",
            required=True,
        ),
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            url = self.url.format(projectId=self.toolset.config.get("project_id"))
            response = requests.get(
                url=url,
                headers={"Accept": "application/vnd.atlas.2025-03-12+json"},
                auth=HTTPDigestAuth(
                    self.toolset.config.get("public_key"),
                    self.toolset.config.get("private_key"),
                ),
                params=params,
            )
            response.raise_for_status()
            if response.ok:
                return success(response.json(), params)
            else:
                return error(
                    f"Failed {self.name}. Status code: {response.status_code}\n{response.text}",
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return error(f"Exception {self.name}: {str(e)}", params=params)


# TODO https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Monitoring-and-Logs/operation/getHostLogs logs from on project
class ReturnLogsForProcessInPorject(MongoDBAtlasBaseTool):
    name: str = "atlas_return_logs_for_host_in_project"
    description: str = "Returns log messages for the specified host for the specified project of the last 1 hour."
    url: str = "https://cloud.mongodb.com/api/atlas/v2/groups/{project_id}/clusters/{process_id}/logs/mongodb.gz?startDate={start_date}"
    parameters: Dict[str, ToolParameter] = {
        "hostName": ToolParameter(
            description="The host must be the hostname, FQDN, IPv4 address, or IPv6 address of the host that runs the MongoDB process (mongod or mongos).",
            type="string",
            required=True,
        ),
        # "endDate": ToolParameter(
        #     description="Specifies the date and time for the starting point of the range of log messages to retrieve, in the number of seconds that have elapsed since the UNIX epoch. This value will default to 1 hour after the start date.",
        #     type="string",
        #     required=True,
        # ),
        # "startDate": ToolParameter(
        #     description="Specifies the date and time for the ending point of the range of log messages to retrieve, in the number of seconds that have elapsed since the UNIX epoch. This value will default to 1 hour prior to the end date.",
        #     type="string",
        #     required=True,
        # ),
    }

    def _invoke(self, params: Any) -> StructuredToolResult:
        import time

        one_hour_ago = int(time.time()) - (1 * 3600)
        try:
            url = self.url.format(
                project_id=self.toolset.config.get("project_id"),
                process_id=params.get("hostName", ""),
                start_date=one_hour_ago,
            )
            response = requests.get(
                url=url,
                headers={"Accept": "application/vnd.atlas.2025-03-12+gzip"},
                auth=HTTPDigestAuth(
                    self.toolset.config.get("public_key"),
                    self.toolset.config.get("private_key"),
                ),
            )
            response.raise_for_status()
            if response.ok:
                with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
                    text_data = gz.read().decode("utf-8")
                return success(text_data, params)
            else:
                return error(
                    f"Failed {self.name}. Status code: {response.status_code}\n{response.text}",
                    params=params,
                )
        except Exception as e:
            logging.exception(self.get_parameterized_one_liner(params))
            return error(f"Exception {self.name}: {str(e)}", params=params)
