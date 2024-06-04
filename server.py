import os
from holmes.utils.cert_utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")
if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY IMPORTS OR CODE ABOVE THIS LINE
# IMPORTING ABOVE MIGHT INITIALIZE AN HTTPS CLIENT THAT DOESN'T TRUST THE CUSTOM CERTIFICATEE

import logging
import uvicorn
import colorlog

from typing import List, Union

from fastapi import FastAPI
from pydantic import BaseModel
from rich.console import Console

from holmes.common.env_vars import HOLMES_HOST, HOLMES_PORT, ALLOWED_TOOLSETS
from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes.core.issue import Issue
from holmes.plugins.prompts import load_prompt


class InvestigateContext(BaseModel):
    type: str
    value: Union[str, dict]


class InvestigateRequest(BaseModel):
    source: str  # "prometheus" etc
    title: str
    description: str
    subject: dict
    context: List[InvestigateContext]
    source_instance_id: str
    include_tool_calls: bool = False
    include_tool_call_results: bool = False
    # TODO in the future
    # response_handler: ...

def init_logging():
    logging_level = os.environ.get("LOG_LEVEL", "INFO")
    logging_format = "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s"
    logging_datefmt = "%Y-%m-%d %H:%M:%S"

    print("setting up colored logging")
    colorlog.basicConfig(format=logging_format, level=logging_level, datefmt=logging_datefmt)
    logging.getLogger().setLevel(logging_level)

    httpx_logger = logging.getLogger("httpx")
    if httpx_logger:
        httpx_logger.setLevel(logging.WARNING)

    logging.info(f"logger initialized using {logging_level} log level")


init_logging()
dal = SupabaseDal()
app = FastAPI()

console = Console()
config = Config.load_from_env()


@app.post("/api/investigate")
def investigate_issues(request: InvestigateRequest):
    context = fetch_context_data(request.context)
    raw_data = request.model_dump()
    if context:
        raw_data["extra_context"] = context

    ai = config.create_issue_investigator(console, allowed_toolsets=ALLOWED_TOOLSETS)
    issue = Issue(
        id=context['id'] if context else "",
        name=request.title,
        source_type=request.source,
        source_instance_id=request.source_instance_id,
        raw=raw_data,
    )
    investigation = ai.investigate(
        issue,
        # TODO prompt should probably be configurable?
        prompt=load_prompt("builtin://generic_investigation.jinja2"),
        console=console,
    )
    ret = {
        "analysis": investigation.result
    }
    if request.include_tool_calls:
        ret["tool_calls"] = [
            {
                "tool_name": tool.tool_name,
                "tool_call": tool.description,
            } | (
                {"call_result": tool.result} if request.include_tool_call_results else {}
            )
            for tool in investigation.tool_calls
        ]
    return ret


def fetch_context_data(context: List[InvestigateContext]) -> dict:
    for context_item in context:
        if context_item.type == "robusta_issue_id":
            # Note we only accept a single robusta_issue_id. I don't think it
            # makes sense to have several of them in the context structure.
            return dal.get_issue_data(context_item.value)

if __name__ == "__main__":
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT)