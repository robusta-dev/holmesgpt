import os
from holmes.core import investigation
from holmes.utils.cert_utils import add_custom_certificate
from contextlib import asynccontextmanager
from holmes.utils.holmes_status import update_holmes_status_in_db

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")
if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY IMPORTS OR CODE ABOVE THIS LINE
# IMPORTING ABOVE MIGHT INITIALIZE AN HTTPS CLIENT THAT DOESN'T TRUST THE CUSTOM CERTIFICATE


import jinja2
import logging
import uvicorn
import colorlog

from litellm.exceptions import AuthenticationError
from fastapi import FastAPI, HTTPException
from rich.console import Console
from holmes.utils.robusta import load_robusta_api_key

from holmes.common.env_vars import (
    HOLMES_HOST,
    HOLMES_PORT,
    HOLMES_POST_PROCESSING_PROMPT,
)
from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes.core.conversations import (
    build_chat_messages,
    build_issue_chat_messages,
    handle_issue_conversation,
)
from holmes.core.issue import Issue
from holmes.core.models import (
    InvestigationResult,
    ConversationRequest,
    InvestigateRequest,
    WorkloadHealthRequest,
    ConversationInvestigationResponse,
    ChatRequest,
    ChatResponse,
    IssueChatRequest,
)
from holmes.plugins.prompts import load_and_render_prompt
from holmes.utils.holmes_sync_toolsets import holmes_sync_toolsets_status


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
config = Config.load_from_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    update_holmes_status_in_db(dal, config)
    holmes_sync_toolsets_status(dal)
    yield


app = FastAPI(lifespan=lifespan)
console = Console()


@app.post("/api/investigate")
def investigate_issues(investigate_request: InvestigateRequest):
    try:
        result = investigation.investigate_issues(
            investigate_request=investigate_request,
            dal=dal,
            config=config,
            console=console
        )
        return result

    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


@app.post("/api/workload_health_check")
def workload_health_check(request: WorkloadHealthRequest):
    load_robusta_api_key(dal=dal, config=config)
    try:
        resource = request.resource
        workload_alerts: list[str] = []
        if request.alert_history:
            workload_alerts = dal.get_workload_issues(
                resource, request.alert_history_since_hours
            )

        instructions = request.instructions or []
        if request.stored_instrucitons:
            stored_instructions = dal.get_resource_instructions(
                resource.get("kind", "").lower(), resource.get("name")
            )
            if stored_instructions:
                instructions.extend(stored_instructions.instructions)

        nl = "\n"
        if instructions:
            request.ask = f"{request.ask}\n My instructions for the investigation '''{nl.join(instructions)}'''"

        system_prompt = load_and_render_prompt(request.prompt_template)
        system_prompt = jinja2.Environment().from_string(system_prompt)
        system_prompt = system_prompt.render(alerts=workload_alerts)

        ai = config.create_toolcalling_llm(console, dal=dal)

        structured_output = {"type": "json_object"}
        ai_call = ai.prompt_call(
            system_prompt, request.ask, HOLMES_POST_PROCESSING_PROMPT, structured_output
        )

        return InvestigationResult(
            analysis=ai_call.result,
            tool_calls=ai_call.tool_calls,
            instructions=instructions,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


# older api that does not support conversation history
@app.post("/api/conversation")
def issue_conversation(conversation_request: ConversationRequest):
    try:
        load_robusta_api_key(dal=dal, config=config)
        ai = config.create_toolcalling_llm(console, dal=dal)

        system_prompt = handle_issue_conversation(conversation_request, ai)

        investigation = ai.prompt_call(system_prompt, conversation_request.user_prompt)

        return ConversationInvestigationResponse(
            analysis=investigation.result,
            tool_calls=investigation.tool_calls,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


@app.post("/api/issue_chat")
def issue_conversation(issue_chat_request: IssueChatRequest):
    try:
        load_robusta_api_key(dal=dal, config=config)
        ai = config.create_toolcalling_llm(console, dal=dal)
        messages = build_issue_chat_messages(issue_chat_request, ai)
        llm_call = ai.messages_call(messages=messages)

        return ChatResponse(
            analysis=llm_call.result,
            tool_calls=llm_call.tool_calls,
            conversation_history=llm_call.messages,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


@app.post("/api/chat")
def chat(chat_request: ChatRequest):
    try:
        load_robusta_api_key(dal=dal, config=config)

        ai = config.create_toolcalling_llm(console, dal=dal)
        messages = build_chat_messages(
            chat_request.ask, chat_request.conversation_history, ai=ai
        )

        llm_call = ai.messages_call(messages=messages)
        return ChatResponse(
            analysis=llm_call.result,
            tool_calls=llm_call.tool_calls,
            conversation_history=llm_call.messages,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


@app.get("/api/model")
def get_model():
    return {"model_name": config.model}


if __name__ == "__main__":
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT)
