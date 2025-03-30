import os

import yaml
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

    def _invoke(self, params: Dict) -> str:
        finding_id = params[PARAM_FINDING_ID]
        try:
            finding = self._fetch_finding(finding_id)
            if finding:
                return yaml.dump(finding)
            else:
                return f"Could not find a finding with finding_id={finding_id}"
        except Exception as e:
            logging.error(e)
            logging.error(
                f"There was an internal error while fetching finding {finding_id}. {str(e)}"
            )

        return f"There was an internal error while fetching finding {finding_id}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return "Fetch metadata and history"


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

    def _invoke(self, params: Dict) -> str:
        try:
            changes = self._fetch_change_history(params)
            if changes:
                return yaml.dump(changes)
            else:
                return f"Could not find changes for {params}"
        except Exception as e:
            logging.error(e)
            msg = f"There was an internal error while fetching changes for {params}. {str(e)}"
            logging.error(msg)
            return msg

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"Fetch change history ({str(params)})"


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
            ],
            tags=[
                ToolsetTag.CORE,
            ],
            is_default=True,
        )
        self._load_llm_instructions(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "robusta_instructions.jinja2")
            )
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {}
