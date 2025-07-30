import json
from enum import Enum
from typing import Generator, Optional, List
from pydantic import BaseModel, Field
from holmes.core.investigation_structured_output import process_response_into_sections


class StreamEvents(str, Enum):
    ANSWER_END = "ai_answer_end"
    START_TOOL = "start_tool_calling"
    TOOL_RESULT = "tool_calling_result"


class StreamMessage(BaseModel):
    event: StreamEvents
    data: dict = Field(default={})


def create_sse_message(event_type: str, data: dict = {}):
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def stream_investigate_formatter(
    call_stream: Generator[StreamMessage, None, None], runbooks
):
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
                },
            )
        else:
            yield create_sse_message(message.event.value, message.data)


def stream_chat_formatter(
    call_stream: Generator[StreamMessage, None, None],
    followups: Optional[List[dict]] = None,
):
    for message in call_stream:
        if message.event == StreamEvents.ANSWER_END:
            yield create_sse_message(
                StreamEvents.ANSWER_END.value,
                {
                    "analysis": message.data.get("content"),
                    "conversation_history": message.data.get("messages"),
                    "follow_up_actions": followups,
                },
            )
        else:
            yield create_sse_message(message.event.value, message.data)
