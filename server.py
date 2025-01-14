import os
import uuid
from holmes.utils.cert_utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")
if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY IMPORTS OR CODE ABOVE THIS LINE
# IMPORTING ABOVE MIGHT INITIALIZE AN HTTPS CLIENT THAT DOESN'T TRUST THE CUSTOM CERTIFICATE
from holmes.core import investigation
from contextlib import asynccontextmanager
from holmes.utils.holmes_status import update_holmes_status_in_db
import jinja2
import logging
import uvicorn
import colorlog
import time
import sys

from litellm.exceptions import AuthenticationError
from fastapi import FastAPI, HTTPException, Request
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
from holmes.core.perf_timing import PerfTiming
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
from holmes.utils.global_instructions import add_global_instructions_to_user_prompt
import string
import random
import tracemalloc
import psutil

tracemalloc.start()

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
    try:
        update_holmes_status_in_db(dal, config)
    except Exception as error:
        logging.error("Failed to update holmes status", exc_info=True)
    try:
        holmes_sync_toolsets_status(dal, config)
    except Exception as error:
        logging.error("Failed to synchronise holmes toolsets", exc_info=True)
    yield


app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()

    logging.info(
        f"Request received - ID: {request_id} - "
        f"Method: {request.method} - "
        f"URL: {request.url}"
    )

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    logging.info(
        f"Request completed - ID: {request_id} - "
        f"Status: {response.status_code} - "
        f"Process Time: {process_time:.2f}ms"
    )

    return response

base_investigate_snapshot = None
@app.post("/api/investigate")
def investigate_issues(investigate_request: InvestigateRequest):
    t = PerfTiming("/api/investigate")
    # print(f"POST /api/investigate {json.dumps(investigate_request)}")
    global base_investigate_snapshot

    try:
        result = investigation.investigate_issues(
            investigate_request=investigate_request,
            dal=dal,
            config=config
        )
        t.end()
        return result

    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    finally:
        log_memory_diff(base_investigate_snapshot)

def log_memory_diff(base_snapshot):
    if not base_snapshot:
        return
    id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.compare_to(base_snapshot, 'lineno')

    print(f"(*)(*)(*)(*) {id}")
    cnt = 0
    i = 0
    while cnt < 10:
        stat = top_stats[i]
        i = i+1
        stat_str = str(stat)
        if not stat_str.startswith("/usr/local/lib/python3.11/tracemalloc.py"):
            print(f"(*)(*)(*)(*) ({id}) {stat}")
            cnt = cnt + 1
    # for stat in top_stats[:10]:
    #     print(f"(*)(*)(*)(*) ({id}) {stat}")
    print(f"(*)(*)(*)(*) {id} END")
    print(f"(*)(*)(*) MEM={psutil.Process().memory_info().rss / 1024 ** 2}MB")

# class LeakyObject:
#     def __init__(self):
#         # Create a larger object (1KB of data)
#         self.data = b'x' * 1024
# memory_leak = []

# def leaky_function():
#     # Create a 1-byte object and store it in our global list
#     memory_leak.append(LeakyObject())

#     # Calculate current memory usage
#     memory_usage = sys.getsizeof(memory_leak) + sum(sys.getsizeof(item) for item in memory_leak)

#     # Print status
#     logging.info(f"Leak count: {len(memory_leak)}. Approximate memory usage: {memory_usage} bytes")

base_workload_health_check_snapshot = None
@app.post("/api/workload_health_check")
def workload_health_check(request: WorkloadHealthRequest):
    logging.info(request)
    global base_workload_health_check_snapshot

    if not base_workload_health_check_snapshot:
        base_workload_health_check_snapshot = tracemalloc.take_snapshot()

    load_robusta_api_key(dal=dal, config=config)
    try:
        # leaky_function()
        # return {
        #     "hello": "world"
        # }
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
        request.ask = add_global_instructions_to_user_prompt(request.ask, global_instructions)

        system_prompt = load_and_render_prompt(request.prompt_template, context={'alerts': workload_alerts})


        ai = config.create_toolcalling_llm(dal=dal)

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
    finally:
        log_memory_diff(base_workload_health_check_snapshot)

# older api that does not support conversation history
@app.post("/api/conversation")
def issue_conversation_deprecated(conversation_request: ConversationRequest):
    try:
        load_robusta_api_key(dal=dal, config=config)
        ai = config.create_toolcalling_llm(dal=dal)

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
    print(f"** ** ** ** ** {issue_chat_request}")
    try:
        load_robusta_api_key(dal=dal, config=config)
        ai = config.create_toolcalling_llm(dal=dal)
        global_instructions = dal.get_global_instructions_for_account()

        messages = build_issue_chat_messages(issue_chat_request, ai, global_instructions)
        llm_call = ai.messages_call(messages=messages)

        return ChatResponse(
            analysis=llm_call.result,
            tool_calls=llm_call.tool_calls,
            conversation_history=llm_call.messages,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)


base_chat_snapshot = None
@app.post("/api/chat")
def chat(chat_request: ChatRequest):
    t = PerfTiming("/api/chat")
    global base_chat_snapshot

    if not base_chat_snapshot:
        base_chat_snapshot = tracemalloc.take_snapshot()
    t.measure("tracemalloc.take_snapshot")
    try:
        load_robusta_api_key(dal=dal, config=config)
        t.measure("load_robusta_api_key")
        ai = config.create_toolcalling_llm(dal=dal)

        t.measure("config.create_toolcalling_llm")
        global_instructions = dal.get_global_instructions_for_account()

        t.measure("dal.get_global_instructions_for_account")
        messages = build_chat_messages(
            chat_request.ask, chat_request.conversation_history, ai=ai, global_instructions=global_instructions
        )
        t.measure("build_chat_messages")

        llm_call = ai.messages_call(messages=messages)
        t.measure("ai.messages_call")
        t.end()
        return ChatResponse(
            analysis=llm_call.result,
            tool_calls=llm_call.tool_calls,
            conversation_history=llm_call.messages,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=e.message)
    finally:
        log_memory_diff(base_chat_snapshot)


@app.get("/api/model")
def get_model():
    return {"model_name": config.model}


if __name__ == "__main__":
    log_config = uvicorn.config.LOGGING_CONFIG
    #log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s %(levelname)-8s %(message)s"
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s %(levelname)-8s %(message)s"
    uvicorn.run(app, host=HOLMES_HOST, port=HOLMES_PORT, log_config=log_config)
