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

from holmes.core.tool_calling_llm import ToolCallResult
from typing import List, Union, Dict, Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from rich.console import Console

from holmes.common.env_vars import HOLMES_HOST, HOLMES_PORT, ALLOWED_TOOLSETS, HOLMES_POST_PROCESSING_PROMPT
from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes.core.issue import Issue
from holmes.plugins.prompts import load_prompt

import uuid
import jinja2
import textwrap


class InvestigateRequest(BaseModel):
    source: str  # "prometheus" etc
    title: str
    description: str
    subject: dict
    context: Dict[str, Any]
    source_instance_id: str = "ApiRequest"
    include_tool_calls: bool = False
    include_tool_call_results: bool = False
    prompt_template: str = "builtin://generic_investigation.jinja2"
    # TODO in the future
    # response_handler: ...


class IssueInvestigationResult(BaseModel):
    """
    :var result: A dictionary containing the summary of the issue investigation.
    :var tools: A list of dictionaries where each dictionary contains information
                about the tool, its name, description and output.
    
    It is based on the holmes investigation saved to Evidence table. 
    """
    result: str
    tools: list[dict]


class HolmesConversationHistory(BaseModel):
    """
    """
    id: str
    ask: str
    answer: IssueInvestigationResult


class HolmesConversationIssueContext(BaseModel):
    investigation_result: IssueInvestigationResult
    conversation_history: list[HolmesConversationHistory]
    issue_type: str
    robusta_issue_id: str
    source: str


class ConversationRequest(BaseModel):
    user_prompt: str
    source: str
    resource: dict
    conversation_type: str
    context: HolmesConversationIssueContext
    include_tool_calls: bool = False
    include_tool_call_results: bool = False
    prompt_template: str = "builtin://generic_ask_for_issue_conversation.jinja2"


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


class InvestigationResult(BaseModel):
    analysis: Optional[str] = None
    tool_calls: List[ToolCallResult] = []

class ConversationInvestigationResult(BaseModel):
    analysis: Optional[str] = None
    tool_calls: List[ToolCallResult] = []
    id: str

@app.post("/api/investigate")
def investigate_issues(investigate_request: InvestigateRequest):
    context = fetch_context_data(investigate_request.context)
    raw_data = investigate_request.model_dump()
    if context:
        raw_data["extra_context"] = context

    ai = config.create_issue_investigator(console, allowed_toolsets=ALLOWED_TOOLSETS)
    issue = Issue(
        id=context['id'] if context else "",
        name=investigate_request.title,
        source_type=investigate_request.source,
        source_instance_id=investigate_request.source_instance_id,
        raw=raw_data,
    )
    investigation = ai.investigate(
        issue,
        prompt=load_prompt(investigate_request.prompt_template),
        console=console,
        post_processing_prompt=HOLMES_POST_PROCESSING_PROMPT
    )
    return InvestigationResult(
        analysis=investigation.result,
        tool_calls=investigation.tool_calls,
    )


@app.post("/api/conversation")
def investigate_issues(follow_up_request: ConversationRequest):
    ai = config.create_toolcalling_llm(console, allowed_toolsets=ALLOWED_TOOLSETS)
    system_prompt = load_prompt(follow_up_request.prompt_template)
    environment = jinja2.Environment()
    system_prompt_template = environment.from_string(system_prompt)
    system_prompt = system_prompt_template.render(investigation=follow_up_request.context.investigation_result.result, 
                                                  tools_called_for_investigation=follow_up_request.context.investigation_result.tools,
                                                  conversation_history=follow_up_request.context.conversation_history)
    
    investigation = ai.call(system_prompt, follow_up_request.user_prompt)
    
    return InvestigationResult(
        analysis=investigation.result,
        tool_calls=investigation.tool_calls,
        id=uuid.uuid4()
    )



def fetch_context_data(context: Dict[str, Any]) -> dict:
    for context_item in context.keys():
        if context_item == "robusta_issue_id":
            # Note we only accept a single robusta_issue_id. I don't think it
            # makes sense to have several of them in the context structure.
            return dal.get_issue_data(context[context_item])


if __name__ == "__main__":
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT)