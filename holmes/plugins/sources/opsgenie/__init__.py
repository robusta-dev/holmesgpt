import logging
from typing import Dict, List, Optional, Union

import markdown  # type: ignore
import requests  # type: ignore

from holmes.core.issue import Issue
from holmes.core.tool_calling_llm import LLMResult
from holmes.plugins.interfaces import SourcePlugin

OPSGENIE_TEAM_INTEGRATION_KEY_HELP = "OpsGenie Team Integration key for writing back results. (NOT a normal API Key.) Get it from Teams > YourTeamName > Integrations > Add Integration > API Key. Don't forget to turn on the integration!"


class OpsGenieSource(SourcePlugin):
    def __init__(
        self, api_key: str, query: str, team_integration_key: Optional[str] = None
    ):
        self.api_key = api_key
        self.query = query
        self.team_integration_key = team_integration_key

    def fetch_issues(self) -> List[Issue]:
        logging.info(f"Fetching alerts from OpsGenie with query: {self.query}")
        try:
            data = []
            url = "https://api.opsgenie.com/v2/alerts"
            headers = {
                "Authorization": f"GenieKey {self.api_key}",
                "Content-Type": "application/json",
            }
            params: Dict[str, Union[int, str]] = {"query": self.query, "limit": 100}
            while url:
                # TODO: also fetch notes and description
                response = requests.get(url, headers=headers, params=params)
                logging.debug(f"Got {response.json()}")
                if response.status_code != 200:
                    raise Exception(
                        f"Failed to get alerts: {response.status_code} {response.text}"
                    )
                response.raise_for_status()
                data.extend(response.json().get("data", []))
                next_url = response.json().get("paging", {}).get("next", None)
                url = next_url if next_url else None  # type: ignore
            return [self.convert_to_issue(alert) for alert in data]
        except requests.RequestException as e:
            raise ConnectionError("Failed to fetch data from OpsGenie.") from e

    def convert_to_issue(self, opsgenie_alert):
        return Issue(
            id=str(opsgenie_alert["id"]),
            name=opsgenie_alert["message"],
            source_type="opsgenie",
            source_instance_id="opsgenie",
            url=opsgenie_alert["tinyId"],
            raw=opsgenie_alert,
        )

    def write_back_result(self, issue_id: str, result_data: LLMResult) -> None:
        if self.team_integration_key is None:
            raise Exception(
                f"Please set '--opsgenie-team-integration-key' to write back results. This is an {OPSGENIE_TEAM_INTEGRATION_KEY_HELP}"
            )

        # TODO: update description to make this more visible (right now we add a comment)
        html_output = markdown.markdown(result_data.result)
        logging.debug(f"HTML output: {html_output}")

        url = f"https://api.opsgenie.com/v2/alerts/{issue_id}/notes?identifierType=id"
        headers = {
            "Authorization": f"GenieKey {self.team_integration_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url=url,
            json={"note": f"Automatic AI Investigation by Robusta:\n\n{html_output}\n"},
            headers=headers,
        )
        logging.debug(f"Response: {response.json()}")
        response.raise_for_status()

        # We get back a response like: {'result': 'Request will be processed', 'took': 0.006, 'requestId': '<request_id>'}
        # Now we need to lookup the request to see if it succeeded
        request_id = response.json().get("requestId", None)
        url = f"https://api.opsgenie.com/v2/alerts/requests/{request_id}"
        response = requests.get(url=url, headers=headers)

        logging.debug(f"Response: {response.json()}")
        response.raise_for_status()
        json_response = response.json()
        if not json_response["data"]["success"]:
            raise Exception(
                f"Failed to write back result to OpsGenie: {json_response['data']['status']}"
            )
