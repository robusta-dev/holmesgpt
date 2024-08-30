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

from typing import Dict, Callable
from litellm.exceptions import AuthenticationError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rich.console import Console

from holmes.common.env_vars import (
    HOLMES_HOST,
    HOLMES_PORT,
    ALLOWED_TOOLSETS,
    HOLMES_POST_PROCESSING_PROMPT,
)
from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes.core.issue import Issue
from holmes.core.models import (
    ConversationType,
    InvestigationResult,
    ConversationRequest,
    InvestigateRequest,
    WorkloadHealthRequest,
    ConversationInvestigationResponse,
    HolmesConversationHistory,
    ConversationInvestigationResult,
    ToolCallConversationResult,
)
from holmes.plugins.prompts import load_prompt
from holmes.core.tool_calling_llm import ToolCallingLLM
import jinja2


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
app = FastAPI()

console = Console()
config = Config.load_from_env()


@app.post("/api/investigate")
def investigate_issues(investigate_request: InvestigateRequest):
    try:
        context = dal.get_issue_data(
            investigate_request.context.get("robusta_issue_id")
        )

        instructions = dal.get_resource_instructions(
            "alert", investigate_request.context.get("issue_type")
        )
        raw_data = investigate_request.model_dump()
        if context:
            raw_data["extra_context"] = context

        ai = config.create_issue_investigator(
            console, allowed_toolsets=ALLOWED_TOOLSETS
        )
        issue = Issue(
            id=context["id"] if context else "",
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
            instructions=investigation.instructions,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


@app.post("/api/workload_health_check")
def workload_health_check(request: WorkloadHealthRequest):

    try:
        resource = request.resource
        workload_alerts: list[str] = []
        if request.alert_history:
            workload_alerts = dal.get_workload_issues(resource, request.alert_history_since_hours)

        instructions = request.instructions
        if request.stored_instrucitons:
            instructions = dal.get_resource_instructions(resource.get("kind"), resource.get("name"))

        nl = '\n'
        if instructions:
            request.ask = f"{request.ask}\n My instructions for the investigation '''{nl.join(instructions)}'''"

        system_prompt = load_prompt(request.prompt_template)
        system_prompt = jinja2.Environment().from_string(system_prompt)
        system_prompt = system_prompt.render(alerts=workload_alerts)

        ai = config.create_toolcalling_llm(console, allowed_toolsets=ALLOWED_TOOLSETS)

        structured_output = {"type": "json_object"}
        ai_call = ai.call(system_prompt, request.ask, HOLMES_POST_PROCESSING_PROMPT, structured_output)

        return InvestigationResult(
            analysis=ai_call.result,
            tool_calls=ai_call.tool_calls,
            instructions=instructions,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


def handle_issue_conversation(
    conversation_request: ConversationRequest, ai: ToolCallingLLM
):
    context_window = ai.get_context_window_size()
    system_prompt = load_prompt("builtin://generic_ask_for_issue_conversation.jinja2")
    system_prompt_template = jinja2.Environment().from_string(system_prompt)
    
    number_of_tools = len(
        conversation_request.context.investigation_result.tools
    ) + sum(
        [
            len(history.answer.tools)
            for history in conversation_request.context.conversation_history
        ]
    )
    if number_of_tools == 0:
        template_context = {
        "investigation": conversation_request.context.investigation_result.result,
        "tools_called_for_investigation": conversation_request.context.investigation_result.tools,
        "conversation_history": conversation_request.context.conversation_history,
    }
        system_prompt = system_prompt_template.render(**template_context)
        return system_prompt

    conversation_history_without_tools = [
        HolmesConversationHistory(
            ask=history.ask,
            answer=ConversationInvestigationResult(analysis=history.answer.analysis),
        )
        for history in conversation_request.context.conversation_history
    ]
    template_context = {
        "investigation": conversation_request.context.investigation_result.result,
        "tools_called_for_investigation": None,
        "conversation_history": conversation_history_without_tools,
    }
    system_prompt = system_prompt_template.render(**template_context)
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": conversation_request.user_prompt,
        },
    ]
    message_size_without_tools = ai.count_tokens_for_message(messages)
    
    tool_size = min(
        10000, int((context_window - message_size_without_tools) / number_of_tools)
    )
    
    truncated_conversation_history_without_tools = [
        HolmesConversationHistory(
            ask=history.ask,
            answer=ConversationInvestigationResult(
                analysis=history.answer.analysis,
                tools=[
                    ToolCallConversationResult(
                        name=tool.name,
                        description=tool.description,
                        output=tool.output[:tool_size],
                    )
                    for tool in history.answer.tools
                ],
            ),
        )
        for history in conversation_request.context.conversation_history
    ]
    truncated_investigation_result_tool_calls = [
        ToolCallConversationResult(
            name=tool.name, description=tool.description, output=tool.output[:tool_size]
        )
        for tool in conversation_request.context.investigation_result.tools
    ]
    
    template_context = {
        "investigation": conversation_request.context.investigation_result.result,
        "tools_called_for_investigation": truncated_investigation_result_tool_calls,
        "conversation_history": truncated_conversation_history_without_tools,
    }
    system_prompt = system_prompt_template.render(**template_context)
    
    return system_prompt


conversation_type_handlers: Dict[
    ConversationType, Callable[[ConversationRequest, any], str]
] = {
    ConversationType.ISSUE: handle_issue_conversation,
}


@app.post("/api/conversation")
def converstation(conversation_request: ConversationRequest):
    try:
        ai = config.create_toolcalling_llm(console, allowed_toolsets=ALLOWED_TOOLSETS)

        handler = conversation_type_handlers.get(conversation_request.conversation_type)
        system_prompt = handler(conversation_request, ai)

        investigation = ai.call(system_prompt, conversation_request.user_prompt)

        return ConversationInvestigationResponse(
            analysis=investigation.result,
            tools=investigation.tool_calls,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


@app.get("/api/model")
def get_model():
    return {"model_name": config.model}


if __name__ == "__main__":
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT)
