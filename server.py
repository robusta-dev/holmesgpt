import logging
import os
import uvicorn
import colorlog

from typing import List, Union

from fastapi import FastAPI
from pydantic import BaseModel
from rich.console import Console

from holmes.common.env_vars import HOLMES_HOST, HOLMES_PORT, ALLOWED_TOOLSETS
from holmes.core.supabase_dal import SupabaseDal
from holmes.config import ConfigFile
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


def fetch_context_data(context: List[InvestigateContext]) -> dict:
    for context_item in context:
        if context_item.type == "robusta_issue_id":
            # Note we only accept a single robusta_issue_id. I don't think it
            # makes sense to have several of them in the context structure.
            return dal.get_issue_data(context_item.value)


@app.post("/api/investigate")
def investigate_issues(request: InvestigateRequest):
    console = Console()
    # TODO how should this be configurable? Like we'd probably want to have
    # a config file or something?
    config = ConfigFile(
        model='gpt-4o'
    )
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
    return {
        "analysis": ai.investigate(
            # TODO prompt should probably be configurable?
            issue, prompt=load_prompt("builtin://generic_investigation.jinja2"), console=console
        ).result
    }


if __name__ == "__main__":
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT)