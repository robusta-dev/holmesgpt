import logging
from typing import List, Pattern, Optional

import requests
from pydantic import BaseModel

from holmes.core.issue import Issue
from holmes.core.tool_calling_llm import LLMResult
from holmes.plugins.interfaces import SourcePlugin
from holmes.utils.markdown_utils import markdown_to_plain_text

class PagerDutySource(SourcePlugin):

    def __init__(self, api_key: str, user_email: str, incident_key: Optional[str] = None):
        self.api_url = "https://api.pagerduty.com"  # currently hard-coded, can expose it if useful
        self.api_key = api_key
        self.user_email = user_email
        self.incident_key = incident_key

    def fetch_issues(self) -> List[Issue]:
        logging.info(f"Fetching issues from {self.api_url}")
        try:
            headers = {
                "Authorization": f"Token token={self.api_key}",
                "Accept": "application/vnd.pagerduty+json;version=2"
            }

            # excludes resolved
            query_params = "?statuses[]=triggered&statuses[]=acknowledged"

            if self.incident_key:
                query_params =f"{query_params}&incident_key={self.incident_key}"

            response = requests.get(
                f"{self.api_url}/incidents{query_params}",
                headers=headers
            )
            if response.status_code != 200:
                print(f"Got response: {response}")
                raise Exception(
                    f"Failed to get issues: {response.status_code} {response.text}"
                )
            logging.debug(f"Got response: {response}")
            response.raise_for_status()
            data = response.json()
            return [self.convert_to_issue(issue) for issue in data.get("incidents", [])]
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to fetch data from PagerDuty.") from e

    def convert_to_issue(self, source_issue):
        return Issue(
            id=source_issue["id"],
            name=source_issue["summary"],
            source_type="PagerDuty",
            source_instance_id=self.api_url,
            url=f"{source_issue['html_url']}",
            raw=source_issue,
        )

    def write_back_result(self, issue_id: str, result_data: LLMResult) -> None:
        logging.info(f"Writing back result to issue {issue_id}")
        if not self.user_email:
            raise Exception(f"When using --update mode, --pagerduty-user-email must be provided")

        try:
            url = f"{self.api_url}/incidents/{issue_id}/notes"
            headers = {
                "Authorization": f"Token token={self.api_key}",
                "Content-Type": "application/json",
                "From": self.user_email,
            }
            comment = markdown_to_plain_text(result_data.result)
            comment_data = {
                "note": {
                    "content": f"Automatic AI Investigation by HolmesGPT:\n\n{comment}"
                }
            }
            response = requests.post(
                url,
                json=comment_data,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            logging.debug(f"Comment added to issue {issue_id}: {data}")
        except requests.RequestException as e:
            logging.error(f"Failed to write back result to PagerDuty: {e}; {e.response.text}")
            raise

# Run with:
# poetry run python3 -m holmes.plugins.sources.pagerduty <api-key> <user-email>
if __name__ == "__main__":
    import sys
    pd_source = PagerDutySource(api_key=sys.argv[1], user_email=sys.argv[2])
    issues = pd_source.fetch_issues()
    for issue in issues:
        pd_source.write_back_result(issue.id, LLMResult(result="This is a test"))
        print(issue)
