import os
import sys

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
from fastapi import FastAPI
from rich.console import Console

from holmes.common.env_vars import (
    ALLOWED_TOOLSETS,
    HOLMES_HOST,
    HOLMES_PORT,
)
from holmes.config import BaseLLMConfig, LLMProviderType
from holmes.core.issue import Issue
from holmes.core.provider import LLMProviderFactory
from holmes.core.server_models import InvestigateContext, InvestigateRequest
from holmes.core.supabase_dal import SupabaseDal
from holmes.plugins.prompts import load_prompt
from holmes.utils.auth import SessionManager


def init_logging():
    logging_level = os.environ.get("LOG_LEVEL", "INFO")
    logging_format = "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s"
    logging_datefmt = "%Y-%m-%d %H:%M:%S"

    colorlog.basicConfig(
        format=logging_format, level=logging_level, datefmt=logging_datefmt
    )
    logging.getLogger().setLevel(logging_level)

    httpx_logger = logging.getLogger("httpx")
    if httpx_logger:
        httpx_logger.setLevel(logging.WARNING)

    logging.info(f"logger initialized using {logging_level} log level")


init_logging()
console = Console()
config = BaseLLMConfig.load_from_env()
logging.info(f"Starting AI server with config: {config}")
dal = SupabaseDal()

if not dal.initialized and config.llm_provider == LLMProviderType.ROBUSTA:
    logging.error("Holmes cannot run without store configuration when the LLM provider is Robusta AI")
    sys.exit(1)
session_manager = SessionManager(dal, "RelayHolmes")
provider_factory = LLMProviderFactory(config, session_manager)
app = FastAPI()



def fetch_context_data(context: List[InvestigateContext]) -> dict:
    for context_item in context:
        if context_item.type == "robusta_issue_id":
            # Note we only accept a single robusta_issue_id. I don't think it
            # makes sense to have several of them in the context structure.
            return dal.get_issue_data(context_item.value)


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
    investigator = provider_factory.create_issue_investigator(console, allowed_toolsets=ALLOWED_TOOLSETS)
    investigation = investigator.investigate(
        issue,
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


if __name__ == "__main__":
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT)
