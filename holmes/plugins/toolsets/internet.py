import re
import os
import logging

from typing import Any, Optional, Tuple

from requests import RequestException, Timeout
from holmes.core.tools import Tool, ToolParameter, Toolset, ToolsetTag
from markdownify import markdownify
from bs4 import BeautifulSoup

import requests

# TODO: change and make it holmes
INTERNET_TOOLSET_USER_AGENT = os.environ.get(
    "INTERNET_TOOLSET_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0; holmesgpt;) Gecko/20100101 Firefox/128.0",
)
INTERNET_TOOLSET_TIMEOUT_SECONDS = int(
    os.environ.get("INTERNET_TOOLSET_TIMEOUT_SECONDS", "60")
)

SELECTORS_TO_REMOVE = [
    "script",
    "style",
    "meta",
    "link",
    "noscript",
    "header",
    "footer",
    "nav",
    "iframe",
    "svg",
    "img",
    "button",
    "menu",
    "sidebar",
    "aside",
    ".header" ".footer" ".navigation",
    ".nav",
    ".menu",
    ".sidebar",
    ".ad",
    ".advertisement",
    ".social",
    ".popup",
    ".modal",
    ".banner",
    ".cookie-notice",
    ".social-share",
    ".related-articles",
    ".recommended",
    "#header" "#footer" "#navigation",
    "#nav",
    "#menu",
    "#sidebar",
    "#ad",
    "#advertisement",
    "#social",
    "#popup",
    "#modal",
    "#banner",
    "#cookie-notice",
    "#social-share",
    "#related-articles",
    "#recommended",
]


def scrape(url) -> Tuple[Optional[str], Optional[str]]:
    response = None
    content = None
    mime_type = None
    try:
        response = requests.get(
            url,
            headers={"User-Agent": INTERNET_TOOLSET_USER_AGENT},
            timeout=INTERNET_TOOLSET_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Timeout:
        error_message = f"Failed to load {url}. Timeout after {INTERNET_TOOLSET_TIMEOUT_SECONDS} seconds"
        logging.error(
            error_message,
            exc_info=True,
        )
        return error_message, None
    except RequestException as e:
        error_message = f"Failed to load {url}: {str(e)}"
        logging.warning(error_message, exc_info=True)
        return error_message, None

    if response:
        content = response.text
        try:
            content_type = response.headers["content-type"]
            if content_type:
                mime_type = content_type.split(";")[0]
        except Exception:
            logging.info(
                f"Failed to parse content type from headers {response.headers}"
            )

    return (content, mime_type)


def cleanup(soup: BeautifulSoup):
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


def html_to_markdown(page_source: str):
    soup = BeautifulSoup(page_source, "html.parser")
    soup = cleanup(soup)
    page_source = str(soup)

    try:
        md = markdownify(page_source)
    except OSError as e:
        logging.error(
            f"There was an error in converting the HTML to markdown. Falling back to returning the raw HTML. Error: {str(e)}"
        )
        return page_source

    md = re.sub(r"</div>", "      ", md)
    md = re.sub(r"<div>", "     ", md)

    md = re.sub(r"\n\s*\n", "\n\n", md)

    return md


def looks_like_html(content):
    """
    Check if the content looks like HTML.
    """
    if isinstance(content, str):
        # Check for common HTML tags
        html_patterns = [r"<!DOCTYPE\s+html", r"<html", r"<head", r"<body"]
        return any(
            re.search(pattern, content, re.IGNORECASE) for pattern in html_patterns
        )
    return False


class FetchWebpage(Tool):
    def __init__(self):
        super().__init__(
            name="fetch_webpage",
            description="Fetch a webpage. Use this to fetch runbooks if they are present before starting your investigation (if no other tool like confluence is more appropriate)",
            parameters={
                "url": ToolParameter(
                    description="The URL to fetch",
                    type="string",
                    required=True,
                )
            },
        )

    def _invoke(self, params: Any) -> str:
        url: str = params["url"]
        content, mime_type = scrape(url)

        if not content:
            logging.error(f"Failed to retrieve content from {url}")
            return ""

        # Check if the content is HTML based on MIME type or content
        if (mime_type and mime_type.startswith("text/html")) or (
            mime_type is None and looks_like_html(content)
        ):
            content = html_to_markdown(content)

        return content

    def get_parameterized_one_liner(self, params) -> str:
        url: str = params["url"]
        return f"fetched webpage {url}"


class InternetToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="internet",
            description="Fetch webpages",
            icon_url="https://platform.robusta.dev/demos/internet-access.svg",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/internet.html",
            prerequisites=[],
            tools=[FetchWebpage()],
            tags=[
                ToolsetTag.CORE,
            ],
            is_default=True,
        )
