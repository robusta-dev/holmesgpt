# ruff: noqa: E402
import os
from typing import List, Optional

import sentry_sdk
from holmes import get_version, is_official_release
from holmes.utils.cert_utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")
if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY IMPORTS OR CODE ABOVE THIS LINE
# IMPORTING ABOVE MIGHT INITIALIZE AN HTTPS CLIENT THAT DOESN'T TRUST THE CUSTOM CERTIFICATE
from holmes.core import investigation
from holmes.utils.holmes_status import update_holmes_status_in_db
import logging
import uvicorn
import colorlog
import time

from litellm.exceptions import AuthenticationError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from holmes.utils.robusta import load_robusta_api_key
from holmes.utils.stream import stream_investigate_formatter, stream_chat_formatter
from holmes.common.env_vars import (
    HOLMES_HOST,
    HOLMES_PORT,
    HOLMES_POST_PROCESSING_PROMPT,
    LOG_PERFORMANCE,
    SENTRY_DSN,
    ENABLE_TELEMETRY,
    SENTRY_TRACES_SAMPLE_RATE,
)
from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes.core.conversations import (
    build_chat_messages,
    build_issue_chat_messages,
    build_workload_health_chat_messages,
)
from holmes.core.models import (
    FollowUpAction,
    InvestigationResult,
    InvestigateRequest,
    WorkloadHealthRequest,
    ChatRequest,
    ChatResponse,
    IssueChatRequest,
    WorkloadHealthChatRequest,
    workload_health_structured_output,
)
from holmes.core.investigation_structured_output import clear_json_markdown
from holmes.plugins.prompts import load_and_render_prompt
from holmes.utils.holmes_sync_toolsets import holmes_sync_toolsets_status
from holmes.utils.global_instructions import add_global_instructions_to_user_prompt


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
config = Config.load_from_env()
dal = SupabaseDal(config.cluster_name)


def sync_before_server_start():
    try:
        update_holmes_status_in_db(dal, config)
    except Exception:
        logging.error("Failed to update holmes status", exc_info=True)
    try:
        holmes_sync_toolsets_status(dal, config)
    except Exception:
        logging.error("Failed to synchronise holmes toolsets", exc_info=True)


if ENABLE_TELEMETRY and SENTRY_DSN:
    if is_official_release():
        logging.info("Initializing sentry...")
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            send_default_pii=False,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=0,
        )
        sentry_sdk.set_tags(
            {
                "account_id": dal.account_id,
                "cluster_name": config.cluster_name,
                "model_name": config.model,
                "version": get_version(),
            }
        )
    else:
        logging.info("Skipping sentry initialization for custom version")

app = FastAPI()


if LOG_PERFORMANCE:

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            process_time = int((time.time() - start_time) * 1000)

            status_code = "unknown"
            if response:
                status_code = response.status_code
            logging.info(
                f"Request completed {request.method} {request.url.path} status={status_code} latency={process_time}ms"
            )


@app.post("/api/investigate")
def investigate_issues(investigate_request: InvestigateRequest):
    try:
        result = investigation.investigate_issues(
            investigate_request=investigate_request,
            dal=dal,
            config=config,
            model=investigate_request.model,
        )
        return result

    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logging.error(f"Error in /api/investigate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stream/investigate")
def stream_investigate_issues(req: InvestigateRequest):
    try:
        ai, system_prompt, user_prompt, response_format, sections, runbooks = (
            investigation.get_investigation_context(req, dal, config)
        )

        return StreamingResponse(
            stream_investigate_formatter(
                ai.call_stream(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_format=response_format,
                    sections=sections,
                ),
                runbooks,
            ),
            media_type="text/event-stream",
        )

    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logging.exception(f"Error in /api/stream/investigate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

        global_instructions = dal.get_global_instructions_for_account()
        request.ask = add_global_instructions_to_user_prompt(
            request.ask, global_instructions
        )

        ai = config.create_toolcalling_llm(dal=dal, model=request.model)

        system_prompt = load_and_render_prompt(
            request.prompt_template,
            context={
                "alerts": workload_alerts,
                "toolsets": ai.tool_executor.toolsets,
                "response_format": workload_health_structured_output,
                "cluster_name": config.cluster_name,
            },
        )

        ai_call = ai.prompt_call(
            system_prompt,
            request.ask,
            HOLMES_POST_PROCESSING_PROMPT,
            workload_health_structured_output,
        )

        ai_call.result = clear_json_markdown(ai_call.result)

        return InvestigationResult(
            analysis=ai_call.result,
            tool_calls=ai_call.tool_calls,
            instructions=instructions,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logging.exception(f"Error in /api/workload_health_check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workload_health_chat")
def workload_health_conversation(
    request: WorkloadHealthChatRequest,
):
    try:
        load_robusta_api_key(dal=dal, config=config)
        ai = config.create_toolcalling_llm(dal=dal, model=request.model)
        global_instructions = dal.get_global_instructions_for_account()

        messages = build_workload_health_chat_messages(
            workload_health_chat_request=request,
            ai=ai,
            config=config,
            global_instructions=global_instructions,
        )
        llm_call = ai.messages_call(messages=messages)

        return ChatResponse(
            analysis=llm_call.result,
            tool_calls=llm_call.tool_calls,
            conversation_history=llm_call.messages,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logging.error(f"Error in /api/workload_health_chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/issue_chat")
def issue_conversation(issue_chat_request: IssueChatRequest):
    try:
        load_robusta_api_key(dal=dal, config=config)
        ai = config.create_toolcalling_llm(dal=dal, model=issue_chat_request.model)
        global_instructions = dal.get_global_instructions_for_account()

        messages = build_issue_chat_messages(
            issue_chat_request=issue_chat_request,
            ai=ai,
            config=config,
            global_instructions=global_instructions,
        )
        llm_call = ai.messages_call(messages=messages)

        return ChatResponse(
            analysis=llm_call.result,
            tool_calls=llm_call.tool_calls,
            conversation_history=llm_call.messages,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logging.error(f"Error in /api/issue_chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def already_answered(conversation_history: Optional[List[dict]]) -> bool:
    if conversation_history is None:
        return False

    for message in conversation_history:
        if message["role"] == "assistant":
            return True
    return False


@app.post("/api/chat")
def chat(chat_request: ChatRequest):
    try:
        load_robusta_api_key(dal=dal, config=config)

        ai = config.create_toolcalling_llm(dal=dal, model=chat_request.model)
        global_instructions = dal.get_global_instructions_for_account()
        messages = build_chat_messages(
            chat_request.ask,
            chat_request.conversation_history,
            ai=ai,
            config=config,
            global_instructions=global_instructions,
        )
        follow_up_actions = []
        if not already_answered(chat_request.conversation_history):
            follow_up_actions = [
                FollowUpAction(
                    id="logs",
                    action_label="Logs",
                    prompt="Show me the relevant logs",
                    pre_action_notification_text="Fetching relevant logs...",
                ),
                FollowUpAction(
                    id="graphs",
                    action_label="Graphs",
                    prompt="Show me the relevant graphs. Use prometheus and make sure you embed the results with `<< >>` to display a graph",
                    pre_action_notification_text="Drawing some graphs...",
                ),
                FollowUpAction(
                    id="articles",
                    action_label="Articles",
                    prompt="List the relevant runbooks and links used. Write a short summary for each",
                    pre_action_notification_text="Looking up and summarizing runbooks and links...",
                ),
            ]

        if chat_request.stream:
            return StreamingResponse(
                stream_chat_formatter(
                    ai.call_stream(msgs=messages),
                    [f.model_dump() for f in follow_up_actions],
                ),
                media_type="text/event-stream",
            )
        else:
            llm_call = ai.messages_call(messages=messages)
            return ChatResponse(
                analysis=llm_call.result,
                tool_calls=llm_call.tool_calls,
                conversation_history=llm_call.messages,
                follow_up_actions=follow_up_actions,
            )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logging.error(f"Error in /api/chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/model")
def get_model():
    return {"model_name": config.get_models_list()}


if __name__ == "__main__":
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = (
        "%(asctime)s %(levelname)-8s %(message)s"
    )
    log_config["formatters"]["default"]["fmt"] = (
        "%(asctime)s %(levelname)-8s %(message)s"
    )
    sync_before_server_start()
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT, log_config=log_config)
