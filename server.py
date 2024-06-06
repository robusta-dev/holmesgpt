import os

import jinja2

from holmes.utils.auth import SessionManager
from holmes.utils.cert_utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")
if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY IMPORTS OR CODE ABOVE THIS LINE
# IMPORTING ABOVE MIGHT INITIALIZE AN HTTPS CLIENT THAT DOESN'T TRUST THE CUSTOM CERTIFICATEE

import logging
from typing import List, Union

import colorlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rich.console import Console

from holmes.common.env_vars import (
    HOLMES_HOST,
    HOLMES_PORT,
)
from holmes.config import Config
from holmes.core.issue import Issue
from holmes.core.supabase_dal import AuthToken, SupabaseDal
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
    prompt_template: str = "builtin://generic_investigation.jinja2"
    model: str = "gpt-4o"
    # TODO in the future
    # response_handler: ...


def init_logging():
    logging_level = os.environ.get("LOG_LEVEL", "INFO")
    logging_format = "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s"
    logging_datefmt = "%Y-%m-%d %H:%M:%S"

    print("setting up colored logging")
    colorlog.basicConfig(
        format=logging_format, level=logging_level, datefmt=logging_datefmt
    )
    logging.getLogger().setLevel(logging_level)

    httpx_logger = logging.getLogger("httpx")
    if httpx_logger:
        httpx_logger.setLevel(logging.WARNING)

    logging.info(f"logger initialized using {logging_level} log level")


init_logging()
dal = SupabaseDal()
session_manager = SessionManager("RelayHolmes")
app = FastAPI()

console = Console()
config = Config.load_from_env()


@app.post("/api/investigate")
def investigate_issue(request: InvestigateRequest):
    context = fetch_context_data(request.context)
    raw_data = request.model_dump()
    raw_data.pop("model")
    raw_data.pop("system_prompt")
    if context:
        raw_data["extra_context"] = context

    issue = Issue(
        id=context["id"] if context else "",
        name=request.title,
        source_type=request.source,
        source_instance_id=request.source_instance_id,
        raw=raw_data,
    )
    investigation = ai.investigate(
        issue,
        # TODO prompt should probably be configurable?
        prompt=load_prompt(request.prompt),
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
