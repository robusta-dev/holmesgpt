"""Lossless conversion between OpenAI chat-completions dicts and LangChain messages.

Every message created from or by this engine carries its OpenAI-format dict in
``additional_kwargs['holmes_raw']``; that dict is what goes back to the LLM
and into ``ai_answer_end.messages``. ``convert_to_openai_messages`` is only a
fallback because it drops fields such as ``reasoning_content`` and the
approval markers Holmes keeps on tool calls.
"""

import copy
from typing import List

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    convert_to_messages,
    convert_to_openai_messages,
)

RAW_KEY = "holmes_raw"


def from_openai_dicts(messages: List[dict]) -> List[BaseMessage]:
    converted = convert_to_messages(messages)
    if len(converted) != len(messages):
        raise ValueError(
            f"History conversion changed message count ({len(messages)} -> {len(converted)})"
        )
    for lc_message, raw in zip(converted, messages):
        lc_message.additional_kwargs[RAW_KEY] = copy.deepcopy(raw)
    return converted


def to_openai_dict(message: BaseMessage) -> dict:
    raw = message.additional_kwargs.get(RAW_KEY)
    if raw is not None:
        return copy.deepcopy(raw)
    converted = convert_to_openai_messages([message])
    return converted[0] if isinstance(converted, list) else converted


def to_openai_dicts(messages) -> List[dict]:
    return [to_openai_dict(m) for m in messages]


def bookkeeping_messages(messages: List[dict]) -> List[BaseMessage]:
    """Text-only view of the history to seed the graph state.

    The chat model reads ``run.messages`` (the real transcript), so the graph
    only needs a plausible conversation to route on. Tool calls and results
    are left out: the graph would otherwise re-run calls that a resume has
    already answered.
    """
    out: List[BaseMessage] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        text = content if isinstance(content, str) else _as_text(content)
        if role == "system":
            out.append(SystemMessage(content=text))
        elif role == "user":
            out.append(HumanMessage(content=text))
        elif role == "assistant" and text:
            out.append(AIMessage(content=text))
    if not out or not isinstance(out[-1], HumanMessage):
        out.append(HumanMessage(content="(continue)"))
    return out


def _as_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return str(content)
