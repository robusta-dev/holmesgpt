import json
from enum import Enum
from typing import Generator, Optional, List
import litellm
from pydantic import BaseModel, Field
from holmes.core.investigation_structured_output import process_response_into_sections
from functools import partial
import logging


class StreamEvents(str, Enum):
    ANSWER_END = "ai_answer_end"
    START_TOOL = "start_tool_calling"
    TOOL_RESULT = "tool_calling_result"
    ERROR = "error"
    AI_MESSAGE = "ai_message"
    APPROVAL_REQUIRED = "approval_required"


class StreamMessage(BaseModel):
    event: StreamEvents
    data: dict = Field(default={})


def create_sse_message(event_type: str, data: Optional[dict] = None):
    if data is None:
        data = {}
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def create_sse_error_message(description: str, error_code: int, msg: str):
    return create_sse_message(
        StreamEvents.ERROR.value,
        {
            "description": description,
            "error_code": error_code,
            "msg": msg,
            "success": False,
        },
    )


create_rate_limit_error_message = partial(
    create_sse_error_message,
    error_code=5204,
    msg="Rate limit exceeded",
)


def stream_investigate_formatter(
    call_stream: Generator[StreamMessage, None, None], runbooks
):
    try:
        for message in call_stream:
            if message.event == StreamEvents.ANSWER_END:
                (text_response, sections) = process_response_into_sections(  # type: ignore
                    message.data.get("content")
                )

                yield create_sse_message(
                    StreamEvents.ANSWER_END.value,
                    {
                        "sections": sections or {},
                        "analysis": text_response,
                        "instructions": runbooks or [],
                        "metadata": message.data.get("metadata") or {},
                    },
                )
            else:
                yield create_sse_message(message.event.value, message.data)
    except litellm.exceptions.RateLimitError as e:
        yield create_rate_limit_error_message(str(e))


def stream_chat_formatter(
    call_stream: Generator[StreamMessage, None, None],
    followups: Optional[List[dict]] = None,
):
    try:
        for message in call_stream:
            if message.event == StreamEvents.ANSWER_END:
                response_data = {
                    "analysis": message.data.get("content"),
                    "conversation_history": message.data.get("messages"),
                    "follow_up_actions": followups,
                    "metadata": message.data.get("metadata") or {},
                }

                yield create_sse_message(StreamEvents.ANSWER_END.value, response_data)
            elif message.event == StreamEvents.APPROVAL_REQUIRED:
                response_data = {
                    "analysis": message.data.get("content"),
                    "conversation_history": message.data.get("messages"),
                    "follow_up_actions": followups,
                }

                response_data["requires_approval"] = True
                response_data["pending_approvals"] = message.data.get(
                    "pending_approvals", []
                )

                yield create_sse_message(
                    StreamEvents.APPROVAL_REQUIRED.value, response_data
                )
            else:
                yield create_sse_message(message.event.value, message.data)
    except litellm.exceptions.RateLimitError as e:
        yield create_rate_limit_error_message(str(e))
    except Exception as e:
        logging.error(e)
        if "Model is getting throttled" in str(e):  # happens for bedrock
            yield create_rate_limit_error_message(str(e))
        else:
            yield create_sse_error_message(description=str(e), error_code=1, msg=str(e))
