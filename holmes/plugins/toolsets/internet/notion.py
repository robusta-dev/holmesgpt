import re
import os
import logging
import json
from typing import Any, Dict
from holmes.core.tools import (
    Tool,
    ToolParameter,
    ToolsetTag,
    CallablePrerequisite,
)
from holmes.plugins.toolsets.internet.internet import InternetBaseToolset, 



class FetchNotion(Tool):
    toolset: "InternetBaseToolset"

    def __init__(self, toolset: "InternetBaseToolset"):
        super().__init__(
            name="fetch_notion_webpage",
            description="Fetch a Notion webpage with HTTP requests and authentication.",
            parameters={
                "url": ToolParameter(
                    description="The URL to fetch",
                    type="string",
                    required=True,
                ),
                "is_runbook": ToolParameter(
                    description="True if the url is a runbook",
                    type="boolean",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def convert_notion_url(self, url):
        if "api.notion.com" in url:
            return url
        match = re.search(r"-(\w{32})$", url)
        if match:
            notion_id = match.group(1)
            return f"https://api.notion.com/v1/blocks/{notion_id}/children"
        return url  # Return original URL if no match is found

    def invoke(self, params: Any) -> str:
        url: str = params["url"]
        is_runbook: bool = params.get("is_runbook", False)

        # Get headers from the toolset configuration
        additional_headers = self.toolset.runbook_headers if is_runbook else {}
        url = self.convert_notion_url(url)
        content, _ = scrape(url, additional_headers)

        if not content:
            logging.error(f"Failed to retrieve content from {url}")
            return ""

        return self.parse_notion_content(content)

    def parse_notion_content(self, content: Any) -> str:
        data = json.loads(content)
        texts = []
        for result in data["results"]:
            if "paragraph" in result and "rich_text" in result["paragraph"]:
                texts.extend(
                    [text["plain_text"] for text in result["paragraph"]["rich_text"]]
                )

        # Join and print the result
        return "".join(texts)

    def get_parameterized_one_liner(self, params) -> str:
        url: str = params["url"]
        is_runbook: bool = params["is_runbook"]
        return f"fetched notion webpage {url} {is_runbook}"


class NotionToolset(InternetBaseToolset):
    runbook_headers: Dict[str, str] = {}

    def __init__(self):
        super().__init__(
            name="notion",
            description="Fetch notion webpages",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/Notion-logo.svg/2048px-Notion-logo.svg.png",
            prerequisites=[
                CallablePrerequisite(callable=self.prerequisites_callable),
            ],
            tools=[
                FetchNotion(self),
            ],
            tags=[
                ToolsetTag.CORE,
            ],
            is_default=True,
        )
