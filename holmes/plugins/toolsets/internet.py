from typing import Any, cast
from typing_extensions import Dict
from holmes.core.tools import Tool, ToolParameter, Toolset, ToolsetCommandPrerequisite

#!/usr/bin/env python

import re
import sys
import logging
import playwright
from markdownify import markdownify
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# TODO: change and make it holmes
USER_AGENT_STR = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0; holmesgpt;) Gecko/20100101 Firefox/128.0"
PAGE_LOAD_TIMEOUT_SECONDS = 60000

def scrape_with_playwright(url):

    with sync_playwright() as p:
        try:
            browser = p.firefox.launch()
        except Exception as e:
            logging.error(str(e))
            return None, None

        try:
            context = browser.new_context(ignore_https_errors=False)
            page = context.new_page()

            page.set_extra_http_headers({"User-Agent": USER_AGENT_STR})

            response = None
            try:
                response = page.goto(url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT_SECONDS)
                context.cookies() # Reading cookies allows to load some pages checking that cookies are enabled
            except PlaywrightTimeoutError:
                logging.error(f"Failed to load {url}. Timeout after {PAGE_LOAD_TIMEOUT_SECONDS} seconds")
            except PlaywrightError as e:
                logging.error(f"Failed to load {url}: {str(e)}")
                return None, None

            try:
                content = page.content()
                mime_type = None
                if response:
                    content_type = response.header_value("content-type")
                    if content_type:
                        mime_type = content_type.split(";")[0]
            except PlaywrightError as e:
                logging.error(f"Error retrieving page content: {str(e)}")
                content = None
                mime_type = None
        finally:
            browser.close()

    return content, mime_type

def cleanup(soup):
    """Remove all elements that are irrelevant to the textual representation of a web page.
    This includes images, extra data, even links as there is no intention to navigate from that page.
    """
    for svg in soup.find_all("svg"):
        svg.decompose()

    if soup.img:
        soup.img.decompose()

    for tag in soup.find_all("a"):
        tag.unwrap()

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr != "href":
                tag.attrs.pop(attr, None)

    return soup

def html_to_markdown(page_source):

    soup = BeautifulSoup(page_source, "html.parser")
    soup = cleanup(soup)
    page_source = str(soup)

    try:
        md = markdownify(page_source)
    except OSError as e:
        logging.error(f"There was an error in converting the HTML to markdown. Falling back to returning the raw HTML. Error: {str(e)}")
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
        html_patterns = [
            r"<!DOCTYPE\s+html",
            r"<html",
            r"<head",
            r"<body"
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in html_patterns)
    return False

class FetchWebpage(Tool):
    def __init__(self):
        super().__init__(
            name = "fetch_webpage",
            description = "Fetch a webpage with w3m. Use this to fetch runbooks if they are present before starting your investigation (if no other tool like confluence is more appropriate)",
            parameters = {
                "url": ToolParameter(
                    description="The URL to fetch",
                    type="string",
                    required=True,
                )
            },
        )

    def invoke(self, params:Any) -> str:

        url:str = params["url"]
        content, mime_type = scrape_with_playwright(url)

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
        url:str = params["url"]
        return f"fetched webpage {url}"

class InternetToolset(Toolset):
    def __init__(self):
        super().__init__(
            name = "internet/core",
            prerequisites = [
                # Take a screenshot sucessfuly ensures playwright is correctly installed
                ToolsetCommandPrerequisite(command="python -m playwright screenshot --browser firefox https://www.example.com playwright.png"),
            ],
            tools = [FetchWebpage()],
        )
        self.check_prerequisites()
