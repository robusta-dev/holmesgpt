import os

import logging

from typing import Optional, Dict, Any, List
from holmes.common.env_vars import load_bool
from holmes.core.supabase_dal import SupabaseDal, FindingType
from holmes.core.tools import (
    StaticPrerequisite,
    Tool,
    ToolInvokeContext,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus

PULL_EXTERNAL_FINDINGS = load_bool("PULL_EXTERNAL_FINDINGS", False)

PARAM_FINDING_ID = "id"
START_TIME = "start_datetime"
END_TIME = "end_datetime"
NAMESPACE = "namespace"
WORKLOAD = "workload"
DEFAULT_LIMIT_CHANGE_ROWS = 100
MAX_LIMIT_CHANGE_ROWS = 200


class FetchRobustaFinding(Tool):
    _dal: Optional[SupabaseDal]

    def __init__(self, dal: Optional[SupabaseDal]):
        super().__init__(
            name="fetch_finding_by_id",
            description="Fetches a robusta finding. Findings are events, like a Prometheus alert or a deployment update and configuration change.",
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

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        finding_id = params[PARAM_FINDING_ID]
        try:
            finding = self._fetch_finding(finding_id)
            if finding:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.SUCCESS,
                    data=finding,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.NO_DATA,
                    data=f"Could not find a finding with finding_id={finding_id}",
                    params=params,
                )
        except Exception as e:
            logging.error(e)
            logging.error(
                f"There was an internal error while fetching finding {finding_id}. {str(e)}"
            )

            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                data=f"There was an internal error while fetching finding {finding_id}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Robusta: Fetch finding data {params}"


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

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        try:
            recommendations = self._resource_recommendation(params)
            if recommendations:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.SUCCESS,
                    data=recommendations,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.NO_DATA,
                    data=f"Could not find recommendations for {params}",
                    params=params,
                )
        except Exception as e:
            msg = f"There was an internal error while fetching recommendations for {params}. {str(e)}"
            logging.exception(msg)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                data=msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Robusta: Check Historical Resource Utilization: ({str(params)})"


class FetchConfigurationChangesMetadataBase(Tool):
    _dal: Optional[SupabaseDal]

    def __init__(
        self,
        dal: Optional[SupabaseDal],
        name: str,
        description: str,
        add_cluster_filter: bool = True,
    ):
        """
        We need seperate tools for external and cluster configuration changes due to the different cluster parameters that are not on "external" changes like 'workload' and 'namespace'.
        add_cluster_filter: adds the namespace and workload parameters for configuration changes tool.
        """
        parameters = {
            START_TIME: ToolParameter(
                description="The starting time boundary for the search period. String in RFC3339 format.",
                type="string",
                required=True,
            ),
            END_TIME: ToolParameter(
                description="The ending time boundary for the search period. String in RFC3339 format.",
                type="string",
                required=True,
            ),
            "limit": ToolParameter(
                description=f"Maximum number of rows to return. Default is {DEFAULT_LIMIT_CHANGE_ROWS} and the maximum is 200",
                type="integer",
                required=False,
            ),
        }

        if add_cluster_filter:
            parameters.update(
                {
                    "namespace": ToolParameter(
                        description="The Kubernetes namespace name for filtering configuration changes",
                        type="string",
                        required=False,
                    ),
                    "workload": ToolParameter(
                        description="Kubernetes resource name to filter configuration changes (e.g., Pod, Deployment, Job, etc.). Must be the full name. For Pods, include the exact generated suffix.",
                        type="string",
                        required=False,
                    ),
                }
            )

        super().__init__(
            name=name,
            description=description,
            parameters=parameters,
        )
        self._dal = dal

    def _fetch_change_history(
        self,
        params: Dict,
        cluster: Optional[str] = None,
        finding_type: FindingType = FindingType.CONFIGURATION_CHANGE,
    ) -> Optional[List[Dict]]:
        if self._dal and self._dal.enabled:
            return self._dal.get_issues_metadata(
                start_datetime=params["start_datetime"],
                end_datetime=params["end_datetime"],
                limit=min(
                    params.get("limit") or DEFAULT_LIMIT_CHANGE_ROWS,
                    MAX_LIMIT_CHANGE_ROWS,
                ),
                ns=params.get("namespace"),
                workload=params.get("workload"),
                cluster=cluster,
                finding_type=finding_type,
            )
        return None

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        try:
            changes = self._fetch_change_history(params)
            if changes:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.SUCCESS,
                    data=changes,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=StructuredToolResultStatus.NO_DATA,
                    data=f"{self.name} found no data. {params}",
                    params=params,
                )
        except Exception as e:
            msg = f"There was an internal error while fetching changes for {params}. {str(e)}"
            logging.exception(msg)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                data=msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Robusta: Search Change History {params}"


class FetchConfigurationChangesMetadata(FetchConfigurationChangesMetadataBase):
    def __init__(self, dal: Optional[SupabaseDal]):
        super().__init__(
            dal=dal,
            name="fetch_configuration_changes_metadata",
            description=(
                "Fetch configuration changes metadata in a given time range. "
                "By default, fetch all cluster changes. Can be filtered on a given namespace or a specific kubernetes resource. "
                "Use fetch_finding_by_id to get detailed change of one specific configuration change."
            ),
        )


class FetchExternalConfigurationChangesMetadata(FetchConfigurationChangesMetadataBase):
    """
    Fetch configuration changes from external sources, e.g., LaunchDarkly changes.
    It needs to be a seperate tool due to the different cluster parameter used in the DAL method like workload and namespace.
    """

    def __init__(self, dal: Optional[SupabaseDal]):
        super().__init__(
            dal=dal,
            name="fetch_external_configuration_changes_metadata",
            description=(
                "Fetch external configuration changes metadata in a given time range. "
                "Fetches configuration changes from external sources. "
                "Use fetch_finding_by_id to get detailed change of one specific configuration change."
            ),
            add_cluster_filter=False,
        )

    def _fetch_change_history(self, params: Dict) -> Optional[List[Dict]]:  # type: ignore
        return super()._fetch_change_history(params, cluster="external")

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Robusta: Search External Change History {params}"


class FetchResourceIssuesMetadata(FetchConfigurationChangesMetadataBase):
    def __init__(self, dal: Optional[SupabaseDal]):
        super().__init__(
            dal=dal,
            name="fetch_resource_issues_metadata",
            description=(
                "Fetch issues and alert metadata in a given time range. "
                "Must be filtered on a given namespace and specific kubernetes resource such as pod, deployment, job, etc."
                "Use fetch_finding_by_id to get further information on a specific issue or alert."
            ),
            add_cluster_filter=True,
        )

    def _fetch_resource_issues(self, params: Dict) -> Optional[List[Dict]]:  # type: ignore
        return super()._fetch_change_history(params, finding_type=FindingType.ISSUE)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Robusta: fetch resource issues metadata {params}"


class RobustaToolset(Toolset):
    def __init__(self, dal: Optional[SupabaseDal]):
        dal_prereq = StaticPrerequisite(
            enabled=True if dal else False,
            disabled_reason="Integration with Robusta cloud is disabled",
        )
        if dal:
            dal_prereq = StaticPrerequisite(
                enabled=dal.enabled, disabled_reason="Data access layer is disabled"
            )

        tools = [
            FetchRobustaFinding(dal),
            FetchConfigurationChangesMetadata(dal),
            FetchResourceRecommendation(dal),
            FetchResourceIssuesMetadata(dal),
        ]

        if PULL_EXTERNAL_FINDINGS:
            tools.append(FetchExternalConfigurationChangesMetadata(dal))

        super().__init__(
            icon_url="https://cdn.prod.website-files.com/633e9bac8f71dfb7a8e4c9a6/646be7710db810b14133bdb5_logo.svg",
            description="Fetches alerts metadata and change history",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/robusta/",
            name="robusta",
            prerequisites=[dal_prereq],
            tools=tools,
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
