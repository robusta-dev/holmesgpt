import os
from holmes.utils.cert_utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")
if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY IMPORTS OR CODE ABOVE THIS LINE
# IMPORTING ABOVE MIGHT INITIALIZE AN HTTPS CLIENT THAT DOESN'T TRUST THE CUSTOM CERTIFICATEE
import jinja2
import logging
import uvicorn
import colorlog

from litellm.exceptions import AuthenticationError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rich.console import Console

from holmes.common.env_vars import HOLMES_HOST, HOLMES_PORT, ALLOWED_TOOLSETS, HOLMES_POST_PROCESSING_PROMPT
from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes.core.issue import Issue
from holmes.core.models import (
    ConversationInvestigationResult, 
    InvestigationResult, 
    ConversationRequest, 
    InvestigateRequest, 
    WorkloadHealthRequest,
    ConversationInvestigationResponse)
from holmes.plugins.prompts import load_prompt
from holmes.utils.cache_utils import SummarizationsCache
from holmes.utils.summarization_utils import (
    summarize_tool_calls_for_conversation_history, 
    summarize_tool_calls_for_investigation_result, 
    conversation_message_exceeds_context_window
)
import jinja2


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
summarization_cache = SummarizationsCache()


@app.post("/api/investigate")
def investigate_issues(investigate_request: InvestigateRequest):
    try:
        context = dal.get_issue_data(investigate_request.context.get("robusta_issue_id"))

        instructions = dal.get_resource_instructions("alert", investigate_request.context.get("issue_type"))
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
            post_processing_prompt=HOLMES_POST_PROCESSING_PROMPT,
            instructions=instructions,
        )

        return InvestigationResult(
            analysis=investigation.result,
            tool_calls=investigation.tool_calls,
            instructions=investigation.instructions
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


@app.post("/api/workload_health_check")
def workload_health_check(request: WorkloadHealthRequest):

    try:
        workload_alerts: list[str] = []
        if request.alert_history:
            workload_alerts = dal.get_workload_issues(request.resource, request.alert_history_since_hours)

        system_prompt = load_prompt(request.prompt_template)
        system_prompt = jinja2.Environment().from_string(system_prompt)
        system_prompt = system_prompt.render(alerts=workload_alerts)

        ai = config.create_toolcalling_llm(console, allowed_toolsets=ALLOWED_TOOLSETS)

        ai_call = ai.call(system_prompt, request.ask, HOLMES_POST_PROCESSING_PROMPT)

        return InvestigationResult(
            analysis=ai_call.result,
            tool_calls=ai_call.tool_calls,
            instructions=ai_call.instructions
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)          


@app.post("/api/conversation")
def converstation(conversation_request: ConversationRequest):
    try:
        ai = config.create_toolcalling_llm(console, allowed_toolsets=ALLOWED_TOOLSETS)
        
        system_prompt = load_prompt(conversation_request.prompt_template)
        environment = jinja2.Environment()
        system_prompt_template = environment.from_string(system_prompt)
        template_context = {
            "investigation": conversation_request.context.investigation_result.result,
            "tools_called_for_investigation": conversation_request.context.investigation_result.tools,
            "conversation_history": conversation_request.context.conversation_history
        }
        if conversation_message_exceeds_context_window(
            ai, template_context, system_prompt_template, conversation_request.user_prompt
        ):
            summarized_conversation_history = summarize_tool_calls_for_conversation_history(conversation_request,
                                                summarization_cache,
                                                ai
                                                )
            template_context["conversation_history"] = summarized_conversation_history
            if conversation_message_exceeds_context_window(
            ai,template_context,system_prompt_template, conversation_request.user_prompt
                ):
                summarized_investigation_result = summarize_tool_calls_for_investigation_result(
                                     conversation_request,
                                     summarization_cache,
                                     ai
                                    )
                template_context["investigation"] = summarized_investigation_result
        
        system_prompt = system_prompt_template.render(
            **template_context
            )
        
        investigation = ai.call(system_prompt, conversation_request.user_prompt)

        return ConversationInvestigationResponse(
            analysis=investigation.result,
            tools=investigation.tool_calls,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


if __name__ == "__main__":
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT)
