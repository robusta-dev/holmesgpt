"""Lossless conversion between OpenAI chat-completions dicts and Pydantic AI messages.

Assistant turns carry the original dict in ``ModelResponse.metadata['holmes_raw']``
and are emitted verbatim on the way back, so provider-specific fields
(thinking blocks, reasoning_content, approval markers) survive the round trip.
"""

import copy
import json
from typing import Any, Dict, List, Optional

from pydantic_ai.messages import (
    BinaryContent,
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

RAW_KEY = "holmes_raw"
PROVIDER_NAME = "litellm"
# Hidden tool that executes a call by its original name. Pydantic AI would
# otherwise answer unknown tool names itself, and withhold every call on the
# last step; routing through this tool keeps the legacy loop's behaviour.
UNKNOWN_TOOL = "__holmes_execute_by_name__"

_FINISH_REASON_MAP = {
    "stop": "stop",
    "length": "length",
    "content_filter": "content_filter",
    "tool_calls": "tool_call",
    "function_call": "tool_call",
}


def _user_content(content: Any):
    if isinstance(content, str) or content is None:
        return content or ""
    parts: List[Any] = []
    for block in content:
        if not isinstance(block, dict):
            parts.append(str(block))
        elif block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "image_url":
            url = (block.get("image_url") or {}).get("url", "")
            if url.startswith("data:"):
                parts.append(BinaryContent.from_data_uri(url))
            else:
                parts.append(ImageUrl(url=url))
    return parts


def chat_to_model_messages(messages: List[dict], model_name: str) -> List[ModelMessage]:
    """Group consecutive system/user/tool dicts into one ``ModelRequest`` each."""
    out: List[ModelMessage] = []
    pending: List[Any] = []

    def flush() -> None:
        nonlocal pending
        if pending:
            out.append(ModelRequest(parts=pending))
            pending = []

    for m in messages:
        role = m.get("role")
        if role == "system":
            pending.append(SystemPromptPart(content=_as_text(m.get("content"))))
        elif role == "user":
            pending.append(UserPromptPart(content=_user_content(m.get("content"))))
        elif role == "tool":
            pending.append(
                ToolReturnPart(
                    tool_name=m.get("name") or "",
                    tool_call_id=m.get("tool_call_id") or "",
                    content=m.get("content"),
                )
            )
        elif role == "assistant":
            flush()
            out.append(assistant_dict_to_model_response(m, model_name))
    flush()
    return out


def assistant_dict_to_model_response(m: dict, model_name: str) -> ModelResponse:
    parts: List[Any] = []
    reasoning = m.get("reasoning_content")
    if reasoning:
        parts.append(ThinkingPart(content=reasoning))
    text = _as_text(m.get("content"))
    if text:
        parts.append(TextPart(content=text))
    for tc in m.get("tool_calls") or []:
        fn = tc.get("function") or {}
        parts.append(
            ToolCallPart(
                tool_name=fn.get("name") or "",
                args=fn.get("arguments") or "{}",
                tool_call_id=tc.get("id") or "",
            )
        )
    # model_name/provider_name stop the graph from merging adjacent responses.
    return ModelResponse(
        parts=parts,
        model_name=model_name,
        provider_name=PROVIDER_NAME,
        metadata={RAW_KEY: copy.deepcopy(m)},
    )


def _as_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return str(content)


def _user_part_to_content(part: UserPromptPart) -> Any:
    if isinstance(part.content, str):
        return part.content
    blocks: List[Dict[str, Any]] = []
    for item in part.content:
        if isinstance(item, str):
            blocks.append({"type": "text", "text": item})
        elif isinstance(item, ImageUrl):
            blocks.append({"type": "image_url", "image_url": {"url": item.url}})
        elif isinstance(item, BinaryContent):
            blocks.append({"type": "image_url", "image_url": {"url": item.data_uri}})
        else:
            blocks.append({"type": "text", "text": str(item)})
    return blocks


def model_messages_to_chat(messages: List[ModelMessage]) -> List[dict]:
    out: List[dict] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            raw = (message.metadata or {}).get(RAW_KEY)
            if raw is not None:
                out.append(copy.deepcopy(raw))
            else:
                out.append(_rebuild_assistant(message))
            continue
        for part in message.parts:
            if isinstance(part, SystemPromptPart):
                out.append({"role": "system", "content": part.content})
            elif isinstance(part, UserPromptPart):
                out.append({"role": "user", "content": _user_part_to_content(part)})
            elif isinstance(part, ToolReturnPart):
                content = part.content
                if not isinstance(content, (str, list)):
                    content = part.model_response_str()
                name = part.tool_name
                if isinstance(part.metadata, dict) and part.metadata.get("tool_name"):
                    name = part.metadata["tool_name"]
                out.append(
                    {
                        "tool_call_id": part.tool_call_id,
                        "role": "tool",
                        "name": name,
                        "content": content,
                    }
                )
            elif isinstance(part, RetryPromptPart):
                if part.tool_name:
                    out.append(
                        {
                            "tool_call_id": part.tool_call_id,
                            "role": "tool",
                            "name": part.tool_name,
                            "content": part.model_response(),
                        }
                    )
                else:
                    out.append({"role": "user", "content": part.model_response()})
    return out


def _rebuild_assistant(message: ModelResponse) -> dict:
    texts = [p.content for p in message.parts if isinstance(p, TextPart)]
    thinking = [p.content for p in message.parts if isinstance(p, ThinkingPart)]
    d: Dict[str, Any] = {"role": "assistant", "content": "\n\n".join(texts) if texts else None}
    tool_calls = [
        {
            "id": p.tool_call_id,
            "type": "function",
            "function": {"name": p.tool_name, "arguments": p.args_as_json_str()},
        }
        for p in message.parts
        if isinstance(p, ToolCallPart)
    ]
    if tool_calls:
        d["tool_calls"] = tool_calls
    if thinking:
        d["reasoning_content"] = "\n\n".join(thinking)
    return d


def is_internal_tool(tool_def) -> bool:
    return bool((tool_def.metadata or {}).get("holmes_internal"))


def tool_def_to_openai(tool_def) -> dict:
    raw = (tool_def.metadata or {}).get("holmes_openai_tool")
    if raw is not None:
        return raw
    function: Dict[str, Any] = {
        "name": tool_def.name,
        "description": tool_def.description or "",
        "parameters": tool_def.parameters_json_schema,
    }
    if tool_def.strict is not None:
        function["strict"] = tool_def.strict
    return {"type": "function", "function": function}


def map_finish_reason(finish_reason: Optional[str]) -> Optional[str]:
    if not isinstance(finish_reason, str):
        return None
    return _FINISH_REASON_MAP.get(finish_reason)


def parse_args_leniently(raw: Any) -> dict:
    """Bad JSON from the model runs the tool with no params, as the legacy loop does."""
    if isinstance(raw, dict):
        return raw
    if raw is None or raw == "":
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}
