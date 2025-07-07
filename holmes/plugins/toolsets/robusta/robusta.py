import os

import logging

from typing import Optional, Dict, Any, List
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import (
    StaticPrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from holmes.core.tools import StructuredToolResult, ToolResultStatus

PARAM_FINDING_ID = "id"
START_TIME = "start_datetime"
END_TIME = "end_datetime"
NAMESPACE = "namespace"
WORKLOAD = "workload"


class FetchRobustaFinding(Tool):
    _dal: Optional[SupabaseDal]

    def __init__(self, dal: Optional[SupabaseDal]):
        super().__init__(
            name="fetch_finding_by_id",
            description="Fetches a robusta finding. Findings are events, like a Prometheus alert or a deployment update",
            parameters={
                PARAM_FINDING_ID: ToolParameter(
                    description="The id of the finding to fetch",
                    type="string",
                    required=True,
                )
            },
        )
        self._dal = dal

    def _fetch_finding(self, finding_id: str) -> Optional[Dict]:
        if self._dal and self._dal.enabled:
            return self._dal.get_issue_data(finding_id)
        else:
            error = f"Failed to find a finding with finding_id={finding_id}: Holmes' data access layer is not enabled."
            logging.error(error)
            return {"error": error}

    def _invoke(self, params: Dict) -> StructuredToolResult:
        finding_id = params[PARAM_FINDING_ID]
        try:
            finding = self._fetch_finding(finding_id)
            if finding:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=finding,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.NO_DATA,
                    data=f"Could not find a finding with finding_id={finding_id}",
                    params=params,
                )
        except Exception as e:
            logging.error(e)
            logging.error(
                f"There was an internal error while fetching finding {finding_id}. {str(e)}"
            )

            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"There was an internal error while fetching finding {finding_id}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Fetch Alert Metadata"


class FetchResourceRecommendation(Tool):
    _dal: Optional[SupabaseDal]

    def __init__(self, dal: Optional[SupabaseDal]):
        super().__init__(
            name="fetch_resource_recommendation",
            description="Fetch workload recommendations for resources requests and limits. Returns the current configured resources, as well as recommendation based on actual historical usage.",
            parameters={
                "name": ToolParameter(
                    description="The name of the kubernetes workload.",
                    type="string",
                    required=True,
                ),
                "namespace": ToolParameter(
                    description="The namespace of the kubernetes resource.",
                    type="string",
                    required=True,
                ),
                "kind": ToolParameter(
                    description="The kind of the kubernetes resource. Must be one of: [Deployment, StatefulSet, DaemonSet, Job].",
                    type="string",
                    required=True,
                ),
            },
        )
        self._dal = dal

    def _resource_recommendation(self, params: Dict) -> Optional[List[Dict]]:
        if self._dal and self._dal.enabled:
            return self._dal.get_resource_recommendation(
                name=params["name"],
                namespace=params["namespace"],
                kind=params["kind"],
            )
        return None

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            recommendations = self._resource_recommendation(params)
            if recommendations:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=recommendations,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.NO_DATA,
                    data=f"Could not find recommendations for {params}",
                    params=params,
                )
        except Exception as e:
            msg = f"There was an internal error while fetching recommendations for {params}. {str(e)}"
            logging.exception(msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Check Historical Resource Utilization: ({str(params)})"


class FetchConfigurationChanges(Tool):
    _dal: Optional[SupabaseDal]

    def __init__(self, dal: Optional[SupabaseDal]):
        super().__init__(
            name="fetch_configuration_changes",
            description="Fetch configuration changes in a given time range. By default, fetch all cluster changes. Can be filtered on a given namespace or a specific workload",
            parameters={
                START_TIME: ToolParameter(
                    description="The starting time boundary for the search period. String in RFC3339 format.",
                    type="string",
                    required=True,
                ),
                END_TIME: ToolParameter(
                    description="The starting time boundary for the search period. String in RFC3339 format.",
                    type="string",
                    required=True,
                ),
            },
        )
        self._dal = dal

    def _fetch_change_history(self, params: Dict) -> Optional[List[Dict]]:
        if self._dal and self._dal.enabled:
            return self._dal.get_configuration_changes(
                start_datetime=params["start_datetime"],
                end_datetime=params["end_datetime"],
            )
        return None

    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            changes = self._fetch_change_history(params)
            if changes:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=changes,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.NO_DATA,
                    data=f"Could not find changes for {params}",
                    params=params,
                )
        except Exception as e:
            msg = f"There was an internal error while fetching changes for {params}. {str(e)}"
            logging.exception(msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Search Change History: ({str(params)})"


class RobustaToolset(Toolset):
    def __init__(self, dal: Optional[SupabaseDal]):
        dal_prereq = StaticPrerequisite(
            enabled=True if dal else False,
            disabled_reason="The data access layer is not available",
        )
        if dal:
            dal_prereq = StaticPrerequisite(
                enabled=dal.enabled, disabled_reason="Data access layer is disabled"
            )

        super().__init__(
            icon_url="https://cdn.prod.website-files.com/633e9bac8f71dfb7a8e4c9a6/646be7710db810b14133bdb5_logo.svg",
            description="Fetches alerts metadata and change history",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/robusta.html",
            name="robusta",
            prerequisites=[dal_prereq],
            tools=[
                FetchRobustaFinding(dal),
                FetchConfigurationChanges(dal),
                FetchResourceRecommendation(dal),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
            is_default=True,
        )
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "robusta_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")

    def get_example_config(self) -> Dict[str, Any]:
        return {}
