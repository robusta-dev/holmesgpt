from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from rich.console import Console

from holmes.config import ConfigFile
from holmes.core.issue import Issue


class InvestigateRequest(BaseModel):
    source: str  # "prometheus" etc
    title: str
    description: str
    subject: dict
    context: List[dict]
    # TODO in the future
    # response_handler: ...


app = FastAPI()


@app.post("/api/investigate")
async def investigate_issues(request: InvestigateRequest):
    console = Console()
    # TODO how should this be configurable? Like we'd probably want to have
    # a config file or something?
    config = ConfigFile(
        model='gpt-4o'
    )
    # TODO allowed_toolsets should probably be configurable?
    ai = config.create_issue_investigator(console, allowed_toolsets="*")
    issue = Issue(
        # TODO we're generating unique ids because the request doesn't provide
        # them. Is this acceptable?
        id=str(uuid4()),
        name=request.title,
        source_type=request.source,
        source_instance_id=None,
        raw=request.dict(),
    )
    return {
        "analysis": ai.investigate(
            # TODO prompt should probably be configurable?
            issue, prompt="builtin://generic_ask.jinja2", console=console
        ).result
    }
