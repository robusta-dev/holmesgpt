import os
from collections.abc import Iterable
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from rich.console import Console

from holmes.core.supabase_dal import SupabaseDal
from holmes.config import ConfigFile
from holmes.core.issue import Issue
from holmes.plugins.prompts import load_prompt


class InvestigateRequest(BaseModel):
    source: str  # "prometheus" etc
    title: str
    description: str
    subject: dict
    context: List[dict]
    source_instance_id: str
    # TODO in the future
    # response_handler: ...


dal = SupabaseDal(
    url=os.getenv("SUPABASE_URL"),
    key=os.getenv("SUPABASE_KEY"),
    email=os.getenv("SUPABASE_EMAIL"),
    password=os.getenv("SUPABASE_PASSWORD"),
)
app = FastAPI()


def fetch_context_data(context: List[dict]) -> dict:
    for context_item in context:
        if context_item.get("type") == "robusta_issue_id":
            # Note we only accept a single robusta_issue_id. I don't think it
            # makes sense to have several of them in the context structure.
            return dal.get_issue_data(context_item.get("value"))


@app.post("/api/investigate")
def investigate_issues(request: InvestigateRequest):
    console = Console()
    # TODO how should this be configurable? Like we'd probably want to have
    # a config file or something?
    config = ConfigFile(
        model='gpt-4o'
    )
    context = fetch_context_data(request.context)
    raw_data = request.dict()
    if context:
        raw_data["extra_context"] = context
    # TODO allowed_toolsets should probably be configurable?
    ai = config.create_issue_investigator(console, allowed_toolsets="*")
    issue = Issue(
        id=context['id'] if context else None,
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
