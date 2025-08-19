import logging
from typing import List, Optional

import requests  # type: ignore
from requests.auth import HTTPBasicAuth  # type: ignore

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

    def convert_to_issue(self, jira_issue, description: Optional[str] = None):
        # If a description was provided, use it. Otherwise extract from the jira issue.
        if description is None:
            description = self.extract_description(jira_issue)
        return Issue(
            id=jira_issue["id"],
            name=jira_issue["fields"]["summary"],
            source_type="jira",
            source_instance_id=self.url,
            url=f"{self.url}/browse/{jira_issue['key']}",
            description=description,
            raw=jira_issue,
        )

        # status=jira_issue["fields"]["status"]["name"],

    def extract_description(self, jira_issue) -> str:
        """
        Extracts and formats the issue description.
        """
        # Defensive handling: Jira may return a plain string for the description
        # or a dict with a `content` structure. Also guard if jira_issue isn't a dict.
        description_text = []

        if not isinstance(jira_issue, dict):
            # Unexpected shape, return the string representation
            return str(jira_issue)

        fields = jira_issue.get("fields", {}) or {}
        desc = fields.get("description")

        # If description is a plain string, return it directly
        if isinstance(desc, str):
            return desc

        # If description is missing or falsy, return default
        if not desc:
            return "No description available."

        # Otherwise assume it's the newer Atlassian rich text structure
        description_blocks = desc.get("content", []) if isinstance(desc, dict) else []

        for block in description_blocks:
            if block["type"] == "paragraph":
                text = " ".join(
                    [c["text"] for c in block.get("content", []) if "text" in c]
                )
                description_text.append(text)
            elif block["type"] == "orderedList":
                for idx, item in enumerate(block["content"], start=1):
                    text = " ".join(
                        [
                            c["text"]
                            for c in item["content"][0].get("content", [])
                            if "text" in c
                        ]
                    )
                    description_text.append(f"{idx}. {text}")

        return (
            "\n".join(description_text)
            if description_text
            else "No description available."
        )

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


class JiraServiceManagementSource(JiraSource):
    def __init__(self, url: str, username: str, api_key: str, jql_query: str):
        super().__init__(url, username, api_key, jql_query)

    def fetch_issue(self, id: str) -> Issue:
        """
        Might also be the same in jira, needs additional testing
        """
        logging.info(f"Fetching Jira Service Management issue {id} from {self.url}")

        try:
            response = requests.get(
                f"{self.url}/rest/api/3/issue/{id}",
                auth=HTTPBasicAuth(self.username, self.api_key),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            jsm_issue = response.json()
            description = self.extract_description(jsm_issue)
            return self.convert_to_issue(jsm_issue, description)
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to fetch JSM ticket {id}") from e
