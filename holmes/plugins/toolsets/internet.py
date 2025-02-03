import re
import os
import logging
import json
from typing import Any, Dict, Tuple, Optional

from typing import Any, Optional, Tuple

from requests import RequestException, Timeout
from holmes.core.tools import Tool, ToolParameter, Toolset, ToolsetTag
from markdownify import markdownify
from bs4 import BeautifulSoup

import requests

# TODO: change and make it holmes
INTERNET_TOOLSET_USER_AGENT = os.environ.get("INTERNET_TOOLSET_USER_AGENT", "Mozilla/5.0 (X11; Linux x86_64; rv:128.0; holmesgpt;) Gecko/20100101 Firefox/128.0")
INTERNET_TOOLSET_TIMEOUT_SECONDS = int(os.environ.get("INTERNET_TOOLSET_TIMEOUT_SECONDS", "60"))

SELECTORS_TO_REMOVE = [
    'script', 'style', 'meta', 'link', 'noscript',
    'header', 'footer', 'nav',
    'iframe', 'svg', 'img',
    'button',
    'menu', 'sidebar', 'aside',
    '.header'
    '.footer'
    '.navigation',
    '.nav',
    '.menu',
    '.sidebar',
    '.ad',
    '.advertisement',
    '.social',
    '.popup',
    '.modal',
    '.banner',
    '.cookie-notice',
    '.social-share',
    '.related-articles',
    '.recommended',
    '#header'
    '#footer'
    '#navigation',
    '#nav',
    '#menu',
    '#sidebar',
    '#ad',
    '#advertisement',
    '#social',
    '#popup',
    '#modal',
    '#banner',
    '#cookie-notice',
    '#social-share',
    '#related-articles',
    '#recommended'
]

    response = None
    content = None
    mime_type = None
    try:
        response = requests.get(
            url,
            headers={
                'User-Agent': INTERNET_TOOLSET_USER_AGENT
            },
            timeout=INTERNET_TOOLSET_TIMEOUT_SECONDS
        )
        response.raise_for_status()
    except Timeout:
        logging.error(
            f"Failed to load {url}. Timeout after {INTERNET_TOOLSET_TIMEOUT_SECONDS} seconds",
            exc_info=True
        )
    except RequestException as e:
        logging.error(f"Failed to load {url}: {str(e)}", exc_info=True)
        return None, None
def scrape(url: str, headers: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:

    if response:
        content = response.text
        try:
            content_type = response.headers['content-type']
            if content_type:
                mime_type = content_type.split(";")[0]
        except Exception:
            logging.info(f"Failed to parse content type from headers {response.headers}")

    return (content, mime_type)

def cleanup(soup:BeautifulSoup):
    """Remove all elements that are irrelevant to the textual representation of a web page.
    This includes images, extra data, even links as there is no intention to navigate from that page.
    """

    for selector in SELECTORS_TO_REMOVE:
        for element in soup.select(selector):
            element.decompose()

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr != "href":
                tag.attrs.pop(attr, None)
    return soup



def html_to_markdown(page_source:str):

    soup = BeautifulSoup(page_source, "html.parser")
    soup = cleanup(soup)
    page_source = str(soup)

    try:
        md = markdownify(page_source)
    except Exception as e:
        logging.error(f"Error converting HTML to markdown: {e}")
        return page_source

    return re.sub(r"\n\s*\n", "\n\n", md)

def looks_like_html(content: str) -> bool:
    """Determine if the content is HTML."""
    return any(re.search(pattern, content, re.IGNORECASE) for pattern in [r"<!DOCTYPE\s+html", r"<html", r"<head", r"<body"])

class FetchWebpage(Tool):
    toolset: "InternetToolset"
    
    def __init__(self, toolset: "InternetToolset"):
        super().__init__(
            name="fetch_webpage",
            description="Fetch a webpage. Use this to fetch runbooks if they are present before starting your investigation (if no other tool like confluence is more appropriate)",
            parameters={
                "url": ToolParameter(description="The URL to fetch", type="string", required=True),
                "is_runbook": ToolParameter(description="Is this a runbook URL?", type="boolean", required=False)
            },
            toolset=toolset,
        )

    def convert_notion_url(self, url):
        if "api.notion.com" in url:
            return url
        match = re.search(r'-(\w{32})$', url)
        if match:
            notion_id = match.group(1)
            return f"https://api.notion.com/v1/blocks/{notion_id}/children"
        return url  # Return original URL if no match is found

    def invoke(self, params: Any) -> str:
        url: str = params["url"]
        content, mime_type = scrape(url)
        is_runbook: bool = params.get("is_runbook", False)

        # Get headers from the toolset configuration
        additional_headers = self.toolset.runbook_headers if is_runbook else {}
        additional_headers["User-Agent"] = INTERNET_TOOLSET_USER_AGENT

        is_notion = "Notion-Version" in additional_headers
        if is_notion:
            url = self.convert_notion_url(url)
            
        content, mime_type = scrape(url, additional_headers)

        if not content:
            logging.error(f"Failed to retrieve content from {url}")
            return ""

        # Convert HTML to Markdown if applicable
        if (mime_type and mime_type.startswith("text/html")) or looks_like_html(content):
            content = html_to_markdown(content)

        if is_notion:
            return self.parse_notion_content(content)

        return content

    def parse_notion_content(self, content: Any) -> str:
        data = json.loads(content)
        texts = []
        for result in data['results']:
            if 'paragraph' in result and 'rich_text' in result['paragraph']:
                texts.extend([text['plain_text'] for text in result['paragraph']['rich_text']])

        # Join and print the result
        return ''.join(texts)

    def get_parameterized_one_liner(self, params) -> str:
        return f"Fetched webpage {params['url']}"

class InternetToolset(Toolset):
    runbook_headers: Dict[str, str] = {}

    def __init__(self):
        super().__init__(
            name="internet",
            description="Fetch webpages with optional authentication",
            icon_url="https://platform.robusta.dev/demos/internet-access.svg",
            prerequisites=[],
            tools=[FetchWebpage()],
            tags=[ToolsetTag.CORE,],
            is_default=True
            prerequisites=[
                CallablePrerequisite(callable=self.prerequisites_callable),
            ],
            tools=[FetchWebpage(self)],
            tags=[ToolsetTag.CORE],
            is_default=True
        )

    def prerequisites_callable(self, config: Dict[str, Any]) -> bool:
        if not config:
            return True
        self.runbook_headers = config.get("runbook_headers", {})
        return True
