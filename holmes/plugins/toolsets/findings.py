import os
from typing import Any, Optional, cast
from typing_extensions import Dict
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import Tool, ToolParameter, Toolset, ToolsetCommandPrerequisite
from pydantic import SecretStr
#!/usr/bin/env python

import re
import sys
import logging
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource

PARAM_FINDING_ID = "finding_id"

class FetchRobustaFinding(Tool):

    _dal:SupabaseDal = SupabaseDal()

    def __init__(self):
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

    def _fetch_finding(self, finding_id:str) -> Optional[Dict]:
        if os.environ.get("ROBUSTA_AI"):
            account_id, token = self._dal.get_ai_credentials()
            secret_key = SecretStr(f"{account_id} {token}")
            return self._dal.get_issue_data(
                finding_id
            )
        return None

    def invoke(self, params: Dict) -> str:
        finding_id = params[PARAM_FINDING_ID]
        try:
            finding = self._fetch_finding(finding_id)
            if finding:
                return str(finding)
            else:
                return f"Could not find a finding with finding_id={finding_id}"
        except Exception as e:
            logging.error(e)
            logging.error("Failed to ")

        return f"There was an internal error while fetching finding {finding_id}"

    def get_parameterized_one_liner(self, params:Dict) -> str:
        return f"Fetched finding with finding_id={params[PARAM_FINDING_ID]}"

class FindingsToolset(Toolset):
    def __init__(self):
        super().__init__(
            name = "findings",
            prerequisites = [],
            tools = [FetchRobustaFinding()],
        )
        self.check_prerequisites()
