import re
import os
import logging
import json
from typing import Any, Dict, Tuple, Optional

import requests
from markdownify import markdownify
from bs4 import BeautifulSoup

from holmes.core.tools import (
    Tool,
    ToolParameter,
    Toolset,
    ToolsetCommandPrerequisite,
    ToolsetTag,
    CallablePrerequisite,
)

# Constants
INTERNET_TOOLSET_USER_AGENT = os.environ.get(
    "INTERNET_TOOLSET_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0; holmesgpt;) Gecko/20100101 Firefox/128.0"
)
INTERNET_TOOLSET_TIMEOUT_SECONDS = int(os.environ.get("INTERNET_TOOLSET_TIMEOUT_SECONDS", "60"))

# Selectors to remove from HTML
SELECTORS_TO_REMOVE = [
    'script', 'style', 'meta', 'link', 'noscript',
    'header', 'footer', 'nav', 'iframe', 'svg', 'img', 'button',
    'menu', 'sidebar', 'aside', '.header', '.footer', '.navigation',
    '.nav', '.menu', '.sidebar', '.ad', '.advertisement', '.social',
    '.popup', '.modal', '.banner', '.cookie-notice', '.social-share',
    '.related-articles', '.recommended', '#header', '#footer',
    '#navigation', '#nav', '#menu', '#sidebar', '#ad', '#advertisement',
    '#social', '#popup', '#modal', '#banner', '#cookie-notice',
    '#social-share', '#related-articles', '#recommended'
]

def scrape(url: str, headers: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """Fetch a webpage with custom headers, logging redirections."""
    session = requests.Session()
    session.headers.update(headers)


    try:
        response = session.get(url, timeout=INTERNET_TOOLSET_TIMEOUT_SECONDS, allow_redirects=True)
        response.raise_for_status()

        # Log redirection info
        if response.history:
            for resp in response.history:
                logging.info(f"Redirected from {resp.url} → {response.url}")

        content_type = response.headers.get('Content-Type', '').split(";")[0]
        logging.error(f"Final URL: {response.url}, Content Type: {content_type}")
        return response.text, content_type

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to load {url}: {e}")
        return None, None

def cleanup(soup: BeautifulSoup):
    """Remove unnecessary elements from the HTML page."""
    for selector in SELECTORS_TO_REMOVE:
        for element in soup.select(selector):
            element.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr != "href":
                tag.attrs.pop(attr, None)
    return soup

def html_to_markdown(page_source: str):
    """Convert HTML content to Markdown."""
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
            description="Fetch a webpage with HTTP requests and optional authentication.",
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
