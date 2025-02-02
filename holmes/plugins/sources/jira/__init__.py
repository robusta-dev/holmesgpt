import logging
from typing import List

import requests
from requests.auth import HTTPBasicAuth

from holmes.core.issue import Issue
from holmes.core.tool_calling_llm import LLMResult
from holmes.plugins.interfaces import SourcePlugin


class JiraSource(SourcePlugin):
    def __init__(self, url: str, username: str, api_key: str, jql_query: str):
        self.url = url
        self.username = username
        self.api_key = api_key
        self.jql_query = jql_query

    def fetch_issues(self) -> List[Issue]:
        logging.info(f"Fetching issues from {self.url} with JQL='{self.jql_query}'")
        try:
            response = requests.get(
                f"{self.url}/rest/api/2/search",
                params={"jql": self.jql_query},
                auth=HTTPBasicAuth(self.username, self.api_key),
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200:
                raise Exception(
                    f"Failed to get issues: {response.status_code} {response.text}"
                )
            logging.info(f"Got {response}")
            response.raise_for_status()
            data = response.json()
            return [self.convert_to_issue(issue) for issue in data.get("issues", [])]
        except requests.RequestException as e:
            raise ConnectionError("Failed to fetch data from Jira.") from e

    def convert_to_issue(self, jira_issue):
        return Issue(
            id=jira_issue["id"],
            name=jira_issue["fields"]["summary"],
            source_type="jira",
            source_instance_id=self.url,
            url=f"{self.url}/browse/{jira_issue['key']}",
            raw=jira_issue,
        )

        # status=jira_issue["fields"]["status"]["name"],
        # description=jira_issue.get("fields", {}).get("description", ""),

    def write_back_result(self, issue_id: str, result_data: LLMResult) -> None:
        # TODO: upload files and show tool usage
        comment_url = f"{self.url}/rest/api/2/issue/{issue_id}/comment"
        comment_data = {
            "body": f"Automatic AI Investigation by Robusta:\n\n{result_data.result}\n"
        }
        response = requests.post(
            comment_url,
            json=comment_data,
            auth=HTTPBasicAuth(self.username, self.api_key),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        logging.debug(f"Comment added to issue {issue_id}: {data}")
