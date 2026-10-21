"""``BaseChatModel`` that delegates every call to ``DefaultLLM.completion``."""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, InvalidToolCall, ToolCall
from langchain_core.messages.ai import InputTokenDetails, OutputTokenDetails, UsageMetadata
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.config import get_stream_writer
from pydantic import ConfigDict, Field

from holmes.core.engines import AgentPauseRequested
from holmes.core.engines.langgraph.messages import RAW_KEY
from holmes.core.engines.langgraph.tools import HolmesLangChainTool
from holmes.core.llm_usage import extract_usage_from_response
from holmes.utils.stream import StreamEvents, StreamMessage

if TYPE_CHECKING:
    from holmes.core.tool_calling_llm import ToolCallingLLM


def _parse_args(arguments: Optional[str]) -> dict:
    """Bad JSON runs the tool with no params, as the legacy loop does."""
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
    except Exception:
        logging.warning(f"Failed to parse tool arguments: {arguments}")
        return {}
    return parsed if isinstance(parsed, dict) else {}


class HolmesChatModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    engine: Any = Field(exclude=True)
    run: Any = Field(exclude=True)  # LangGraphRunState; holds a Lock, so no pydantic schema
    response_format: Any = None

    @property
    def _llm_type(self) -> str:
        return "holmes-litellm"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model": self.engine.llm.model}

    def _token_count_event(self) -> StreamMessage:
        run = self.run
        engine = self.engine
        return engine._emit_token_count(
            run.messages,
            run.last_tools,
            run.last_response,
            run.max_context_size or engine.llm.get_context_window_size(),
            run.maximum_output_token or engine.llm.get_maximum_output_token(),
            run.metadata,
            run.stats,
        )

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> Runnable:
        openai_tools: List[dict] = []
        for t in tools:
            if isinstance(t, HolmesLangChainTool):
                openai_tools.append(t.openai_tool)
            elif isinstance(t, dict):
                openai_tools.append(t)
            else:
                openai_tools.append(convert_to_openai_tool(t))
        return self.bind(tools=openai_tools, tool_choice=tool_choice)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        from holmes.core.tool_calling_llm import LLMInterruptedError

        engine: "ToolCallingLLM" = self.engine
        run = self.run
        if run.cancel_event and run.cancel_event.is_set():
            raise LLMInterruptedError()

        tools = kwargs.get("tools") or None
        if kwargs.get("tool_choice") not in (None, "auto") and tools:
            logging.debug(f"Coercing tool_choice {kwargs.get('tool_choice')!r} to 'auto'")
        tool_choice = "auto" if tools else None

        # run.messages is the authoritative transcript (the graph's messages are
        # the same conversation, minus compaction and pending placeholders).
        writer = get_stream_writer()
        if run.last_response is not None:
            # Token count after the previous turn's tool results (legacy parity).
            # Emitted here rather than on the tools node's update: LangGraph may
            # deliver a worker thread's custom events after that update.
            writer(self._token_count_event())
        if run.has_pending:
            raise AgentPauseRequested(run.pending_approvals, run.pending_frontend_calls)

        run.iteration += 1
        with run.lock:
            chat_messages = list(run.messages)
        chat_messages, metadata, limit_result = engine._compact_before_call(
            chat_messages, tools, run.stats, run.metadata, run.guard, writer
        )
        with run.lock:
            run.messages = chat_messages
            run.metadata.update(metadata)
            run.max_context_size = limit_result.max_context_size
            run.maximum_output_token = limit_result.maximum_output_token
        full_response, _ = engine._run_llm_iteration(
            messages=chat_messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=self.response_format,
            trace_span=run.trace_span,
            iteration=run.iteration,
            stats=run.stats,
        )
        if run.cancel_event and run.cancel_event.is_set():
            raise LLMInterruptedError()

        msg = full_response.choices[0].message
        raw = msg.model_dump(exclude_defaults=True, exclude_unset=True, exclude_none=True)
        with run.lock:
            run.messages.append(raw)
            run.last_response = full_response
            run.last_tools = tools

        writer(self._token_count_event())

        tool_calls: List[ToolCall] = []
        invalid: List[InvalidToolCall] = []
        for tc in getattr(msg, "tool_calls", None) or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                logging.error(f"Unsupported custom tool call skipped: {tc}")
                continue
            tool_calls.append(ToolCall(name=fn.name, args=_parse_args(fn.arguments), id=tc.id, type="tool_call"))

        content = msg.content if isinstance(msg.content, str) else ""
        reasoning = getattr(msg, "reasoning_content", None)
        try:
            finish_reason = full_response.choices[0].finish_reason
        except (AttributeError, IndexError):
            finish_reason = None
        if tool_calls:
            if reasoning or content:
                writer(
                    StreamMessage(
                        event=StreamEvents.AI_MESSAGE,
                        data={"content": content or None, "reasoning": reasoning, "metadata": run.metadata},
                    )
                )
        else:
            if isinstance(finish_reason, str):
                run.metadata["finish_reason"] = finish_reason
            if content:
                run.trace_span.log(output=content)

        u = extract_usage_from_response(full_response)
        input_details = InputTokenDetails()
        if u.get("cached_tokens") is not None:
            input_details["cache_read"] = u["cached_tokens"]
        if u.get("cache_creation_tokens") is not None:
            input_details["cache_creation"] = u["cache_creation_tokens"]
        output_details = OutputTokenDetails()
        if u.get("reasoning_tokens"):
            output_details["reasoning"] = u["reasoning_tokens"]
        usage_metadata = UsageMetadata(
            input_tokens=u["prompt_tokens"],
            output_tokens=u["completion_tokens"],
            total_tokens=u["total_tokens"] or (u["prompt_tokens"] + u["completion_tokens"]),
            input_token_details=input_details,
            output_token_details=output_details,
        )
        ai_message = AIMessage(
            content=content,
            tool_calls=tool_calls,
            invalid_tool_calls=invalid,
            additional_kwargs={RAW_KEY: raw, "reasoning_content": reasoning},
            response_metadata={
                "finish_reason": finish_reason if isinstance(finish_reason, str) else None,
                "model_name": getattr(full_response, "model", None) or engine.llm.model,
            },
            usage_metadata=usage_metadata,
        )
        return ChatResult(
            generations=[ChatGeneration(message=ai_message, generation_info={"finish_reason": finish_reason})],
            llm_output={"model_name": engine.llm.model},
        )
