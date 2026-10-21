"""``agents.Model`` implementation that delegates to ``DefaultLLM.completion``."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from agents import Model, ModelResponse, ModelTracing, Usage
from agents.models.fake_id import FAKE_RESPONSES_ID
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseUsage,
)
from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails

from holmes.core.engines import AgentPauseRequested
from holmes.core.engines.openai_agents.run_state import AgentRunState
from holmes.core.llm_usage import extract_usage_from_response
from holmes.utils.stream import StreamEvents, StreamMessage

if TYPE_CHECKING:
    from holmes.core.tool_calling_llm import ToolCallingLLM


def _input_tokens_details(cached: int, cache_write: int) -> InputTokensDetails:
    kwargs: dict = {"cached_tokens": cached}
    # Newer openai releases made cache_write_tokens required.
    if "cache_write_tokens" in InputTokensDetails.model_fields:
        kwargs["cache_write_tokens"] = cache_write
    return InputTokensDetails(**kwargs)


def _text_content(content: Any) -> Optional[str]:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "".join(parts) if parts else None
    return None


class HolmesOpenAIAgentsModel(Model):
    """One Holmes iteration per ``get_response``.

    Owns the chat-completions transcript ("shadow history") so the LLM request
    is byte-identical to the legacy loop's, and emits Holmes stream events for
    token counts and intermediate assistant text.
    """

    def __init__(
        self,
        engine: "ToolCallingLLM",
        run: AgentRunState,
        *,
        response_format: Any,
        max_steps: int,
        agent_tools_setter,
    ) -> None:
        self.engine = engine
        self.run = run
        self.response_format = response_format
        self.max_steps = max_steps
        # Callable that replaces the SDK agent's tool list when ours changes
        # mid-run (OAuth discovery, skill activation).
        self._set_agent_tools = agent_tools_setter

    async def _absorb_tool_outputs(self, input: Any) -> None:
        """Append tool results the SDK has collected since the last call."""
        if not isinstance(input, list):
            return
        for item in input:
            if not isinstance(item, dict) or item.get("type") != "function_call_output":
                continue
            call_id = item.get("call_id")
            if not call_id or call_id in self.run.absorbed_call_ids:
                continue
            if call_id in self.run.pending_call_ids:
                # Waiting for a human or the client; no tool message until then.
                continue
            self.run.absorbed_call_ids.add(call_id)
            result = self.run.results.get(call_id)
            if result is None:
                # The SDK produced this output itself (unknown tool name). Run
                # it through our invoker so the model sees the same error the
                # legacy loop produces, and clients see a TOOL_RESULT event.
                result = await self._invoke_unregistered_call(call_id)
            self.run.messages.append(
                result.to_llm_message(supports_vision=self.engine._supports_vision())
            )

    async def _invoke_unregistered_call(self, call_id: str):
        from holmes.core.engines.openai_agents.tools import invoke_holmes_tool

        name, arguments = "unknown_tool", "{}"
        for message in reversed(self.run.messages):
            if message.get("role") != "assistant":
                continue
            for tc in message.get("tool_calls") or []:
                if tc.get("id") == call_id:
                    fn = tc.get("function") or {}
                    name = fn.get("name") or name
                    arguments = fn.get("arguments") or arguments
                    break
        self.run.emit(
            StreamMessage(event=StreamEvents.START_TOOL, data={"tool_name": name, "id": call_id})
        )
        return await invoke_holmes_tool(self.engine, self.run, call_id, name, arguments)

    def _token_count_event(self) -> StreamMessage:
        run = self.run
        return self.engine._emit_token_count(
            run.messages,
            run.last_tools,
            run.last_response,
            run.max_context_size or self.engine.llm.get_context_window_size(),
            run.maximum_output_token or self.engine.llm.get_maximum_output_token(),
            run.metadata,
            run.stats,
        )

    async def get_response(
        self,
        system_instructions,
        input,
        model_settings,
        tools,
        output_schema,
        handoffs,
        tracing,
        *,
        previous_response_id,
        conversation_id,
        prompt,
    ) -> ModelResponse:
        from holmes.core.tool_calling_llm import LLMInterruptedError

        run = self.run
        if run.cancel_event and run.cancel_event.is_set():
            raise LLMInterruptedError()

        await self._absorb_tool_outputs(input)
        if run.last_response is not None:
            # Token count after the previous turn's tool results (legacy parity).
            run.emit(self._token_count_event())
        if run.has_pending:
            raise AgentPauseRequested(run.pending_approvals, run.pending_frontend_calls)

        run.iteration += 1
        i = run.iteration
        holmes_tools = self.engine._get_tools()
        if run.last_tools is not None:
            old_names = {t["function"]["name"] for t in run.last_tools}
            new_names = {t["function"]["name"] for t in holmes_tools}
            if old_names != new_names:
                logging.warning(
                    f"Tool list changed - refreshing ({len(run.last_tools)} -> {len(holmes_tools)} tools)"
                )
                self._set_agent_tools(holmes_tools)
        llm_tools = None if i == self.max_steps else holmes_tools
        tool_choice = "auto" if llm_tools else None

        # Compaction mutates the shadow history; the SDK's own items are bookkeeping.
        compacted, metadata, limit_result = await asyncio.to_thread(
            self.engine._compact_before_call,
            run.messages,
            llm_tools,
            run.stats,
            run.metadata,
            run.guard,
            run.emit,
        )
        run.messages = compacted
        run.metadata.update(metadata)
        run.max_context_size = limit_result.max_context_size
        run.maximum_output_token = limit_result.maximum_output_token

        full_response, _ = await asyncio.to_thread(
            self.engine._run_llm_iteration,
            messages=run.messages,
            tools=llm_tools,
            tool_choice=tool_choice,
            response_format=self.response_format,
            trace_span=run.trace_span,
            iteration=i,
            stats=run.stats,
        )
        if run.cancel_event and run.cancel_event.is_set():
            raise LLMInterruptedError()

        response_message = full_response.choices[0].message
        assistant_dict = response_message.model_dump(
            exclude_defaults=True, exclude_unset=True, exclude_none=True
        )
        run.messages.append(assistant_dict)
        run.last_response = full_response
        run.last_tools = llm_tools
        run.emit(self._token_count_event())

        tool_calls = getattr(response_message, "tool_calls", None) or []
        content = _text_content(getattr(response_message, "content", None))
        reasoning = getattr(response_message, "reasoning_content", None)
        if tool_calls:
            if reasoning or content:
                run.emit(
                    StreamMessage(
                        event=StreamEvents.AI_MESSAGE,
                        data={"content": content, "reasoning": reasoning, "metadata": run.metadata},
                    )
                )
        else:
            try:
                finish_reason = full_response.choices[0].finish_reason
                if isinstance(finish_reason, str):
                    run.metadata["finish_reason"] = finish_reason
            except (AttributeError, IndexError, TypeError):
                pass
            if content:
                run.trace_span.log(output=content)

        output: list = []
        if content:
            output.append(
                ResponseOutputMessage(
                    id=FAKE_RESPONSES_ID,
                    content=[ResponseOutputText(text=content, type="output_text", annotations=[])],
                    role="assistant",
                    status="completed",
                    type="message",
                )
            )
        for tc in tool_calls:
            function = getattr(tc, "function", None)
            if function is None:
                logging.error(f"Unsupported custom tool call skipped: {tc}")
                continue
            output.append(
                ResponseFunctionToolCall(
                    id=FAKE_RESPONSES_ID,
                    call_id=tc.id,
                    arguments=function.arguments or "{}",
                    name=function.name,
                    type="function_call",
                )
            )

        u = extract_usage_from_response(full_response)
        usage = Usage(
            requests=1,
            input_tokens=u["prompt_tokens"],
            output_tokens=u["completion_tokens"],
            total_tokens=u["total_tokens"],
            input_tokens_details=_input_tokens_details(
                u.get("cached_tokens") or 0, u.get("cache_creation_tokens") or 0
            ),
            output_tokens_details=OutputTokensDetails(reasoning_tokens=u.get("reasoning_tokens") or 0),
        )
        return ModelResponse(output=output, usage=usage, response_id=None)

    def stream_response(
        self,
        system_instructions,
        input,
        model_settings,
        tools,
        output_schema,
        handoffs,
        tracing,
        *,
        previous_response_id,
        conversation_id,
        prompt,
    ) -> AsyncIterator[Any]:
        async def gen():
            model_response = await self.get_response(
                system_instructions,
                input,
                model_settings,
                tools,
                output_schema,
                handoffs,
                tracing,
                previous_response_id=previous_response_id,
                conversation_id=conversation_id,
                prompt=prompt,
            )
            usage = model_response.usage
            yield ResponseCompletedEvent(
                type="response.completed",
                sequence_number=0,
                response=Response(
                    id=FAKE_RESPONSES_ID,
                    created_at=time.time(),
                    model=self.engine.llm.model,
                    object="response",
                    output=model_response.output,
                    parallel_tool_calls=True,
                    tool_choice="auto",
                    tools=[],
                    usage=ResponseUsage(
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        total_tokens=usage.total_tokens,
                        input_tokens_details=usage.input_tokens_details,
                        output_tokens_details=usage.output_tokens_details,
                    ),
                ),
            )

        return gen()
