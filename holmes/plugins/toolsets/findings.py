import yaml
import logging

from typing import Optional
from typing_extensions import Dict
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import StaticPrerequisite, Tool, ToolParameter, Toolset

PARAM_FINDING_ID = "id"

class FetchRobustaFinding(Tool):

    _dal:Optional[SupabaseDal]

    def __init__(self, dal:Optional[SupabaseDal]):
        super().__init__(
            name = "fetch_finding_by_id",
            description = "Fetches a robusta finding. Findings are events, like a Prometheus alert or a deployment update",
            parameters = {
                PARAM_FINDING_ID: ToolParameter(
                    description="The id of the finding to fetch",
                    type="string",
                    required=True,
                )
            },
        )
        self._dal = dal

    def _fetch_finding(self, finding_id:str) -> Optional[Dict]:
        if self._dal and self._dal.enabled:
            return self._dal.get_issue_data(
                finding_id
            )
        else:
            error = f"Failed to find a finding with finding_id={finding_id}: Holmes' data access layer is not enabled."
            logging.error(error)
            return {"error": error}

    def invoke(self, params: Dict) -> str:
        finding_id = params[PARAM_FINDING_ID]
        try:
            finding = self._fetch_finding(finding_id)
            if finding:
                return yaml.dump(finding)
            else:
                return f"Could not find a finding with finding_id={finding_id}"
        except Exception as e:
            logging.error(e)
            logging.error(f"There was an internal error while fetching finding {finding_id}. {str(e)}")

        return f"There was an internal error while fetching finding {finding_id}"

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched finding with finding_id={params[PARAM_FINDING_ID]}"

class FindingsToolset(Toolset):
    def __init__(self, dal:Optional[SupabaseDal]):
        dal_prereq = StaticPrerequisite(
            enabled=True if dal else False,
            disabled_reason="The data access layer is not available")
        if dal:
            dal_prereq = StaticPrerequisite(
                enabled=dal.enabled,
                disabled_reason="Data access layer is disabled")

        super().__init__(
            docs_url="",
            icon_url="",
            description = "Fetches a robusta finding. Findings are events, like a Prometheus alert or a deployment update",
            name = "findings",
            prerequisites = [dal_prereq],
            tools = [FetchRobustaFinding(dal)],
        )
        self.check_prerequisites()
