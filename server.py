import os
from typing import List, Union

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from rich.console import Console

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
    # TODO in the future
    # response_handler: ...


dal = SupabaseDal(
    url=os.getenv("SUPABASE_URL"),
    key=os.getenv("SUPABASE_KEY"),
    email=os.getenv("SUPABASE_EMAIL"),
    password=os.getenv("SUPABASE_PASSWORD"),
)
app = FastAPI()

console = Console()
config = Config.load_from_env()


@app.post("/api/investigate")
def investigate_issue(request: InvestigateRequest):
    context = fetch_context_data(request.context)
    raw_data = request.model_dump()
    if context:
        raw_data["extra_context"] = context
    # TODO allowed_toolsets should probably be configurable?
    ai = config.create_issue_investigator(console, allowed_toolsets="*")
    issue = Issue(
        id=context["id"] if context else None,
        name=request.title,
        source_type=request.source,
        source_instance_id=request.source_instance_id,
        raw=raw_data,
    )
    return {
        "analysis": ai.investigate(
            issue,
            # TODO prompt should probably be configurable?
            prompt=load_prompt("builtin://generic_investigation.jinja2"),
            console=console,
        ).result
    }


def fetch_context_data(context: List[InvestigateContext]) -> dict:
    for context_item in context:
        if context_item.type == "robusta_issue_id":
            # Note we only accept a single robusta_issue_id. I don't think it
            # makes sense to have several of them in the context structure.
            return dal.get_issue_data(context_item.value)


def run_server():
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
    )


if __name__ == "__main__":
    run_server()
