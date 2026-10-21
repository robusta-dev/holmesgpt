"""``ToolCallingLLM`` whose loop is driven by Pydantic AI's ``Agent.iter``.

The agent runs as one task on a private event loop owned by the calling
thread; the sync ``call_stream`` generator pulls Holmes events from an
asyncio queue between loop runs. One task matters: pydantic-graph uses anyio
cancel scopes, which must exit in the task that entered them. Tools run on a
bounded thread pool because MCP tools call ``asyncio.run`` internally.
"""

import asyncio
import json
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_graph import End

from holmes.core.engines import AgentPauseRequested
from holmes.core.engines.pydantic_ai.convert import chat_to_model_messages
from holmes.core.engines.pydantic_ai.run_state import PydanticRunState
from holmes.core.engines.pydantic_ai.model import HolmesPydanticModel
from holmes.core.engines.pydantic_ai.toolset import HolmesToolset
from holmes.core.models import FrontendToolResult, ToolApprovalDecision
from holmes.core.tool_calling_llm import LLMInterruptedError, ToolCallingLLM
from holmes.core.tracing import DummySpan
from holmes.utils.stream import StreamEvents, StreamMessage

_TOOL_WORKERS = 16
_CANCEL_POLL_SECONDS = 0.25
_SENTINEL = object()


def _unwrap(error: BaseException) -> BaseException:
    """Pydantic AI's exit stacks may wrap one error in an exception group."""
    group_type = getattr(sys.modules.get("builtins"), "BaseExceptionGroup", None)
    while group_type is not None and isinstance(error, group_type) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    return error


class PydanticAIToolCallingLLM(ToolCallingLLM):
    engine_id = "pydantic_ai"

    def call_stream(  # type: ignore[override]
        self,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        msgs: Optional[list[dict]] = None,
        enable_tool_approval: bool = False,
        tool_decisions: List[ToolApprovalDecision] | None = None,
        frontend_tool_results: Optional[List[FrontendToolResult]] = None,
        request_context: Optional[Dict[str, Any]] = None,
        trace_span: Any = None,
        cancel_event: Optional[threading.Event] = None,
        tool_number_offset: int = 0,
        iteration_offset: int = 0,
    ):
        if trace_span is None:
            trace_span = DummySpan()
        self._request_context = request_context
        if iteration_offset < 0:
            raise ValueError("iteration_offset must be non-negative")

        all_tool_calls: list[dict] = []
        msgs, preamble_events = self._run_resume_preambles(
            msgs, tool_decisions, frontend_tool_results, request_context, trace_span
        )
        for ev in preamble_events:
            yield ev
            if ev.event == StreamEvents.TOOL_RESULT:
                all_tool_calls.append(ev.data)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "The pydantic_ai engine must be called from a thread without a running event loop"
            )

        loop = asyncio.new_event_loop()
        events: "asyncio.Queue[Any]" = asyncio.Queue()
        run = PydanticRunState(
            emit=events.put_nowait,
            enable_tool_approval=enable_tool_approval,
            all_tool_calls=all_tool_calls,
        )
        run.metadata["engine"] = self.engine_id
        stats = run.stats
        metadata = run.metadata
        executor = ThreadPoolExecutor(max_workers=_TOOL_WORKERS, thread_name_prefix="holmes-tool")
        model = HolmesPydanticModel(
            self,
            run,
            response_format=response_format,
            trace_span=trace_span,
            cancel_event=cancel_event,
            max_steps=self.max_steps,
        )
        toolset = HolmesToolset(
            self,
            run,
            request_context=request_context,
            trace_span=trace_span,
            cancel_event=cancel_event,
            max_steps=self.max_steps,
            tool_number_offset=tool_number_offset,
            executor=executor,
            model=model,
            start_tool_callback=lambda name, call_id: events.put_nowait(
                StreamMessage(event=StreamEvents.START_TOOL, data={"tool_name": name, "id": call_id})
            ),
        )
        agent = Agent(
            model,
            output_type=[str, None],  # an empty answer is a valid end, as in the legacy loop
            toolsets=[toolset],
            retries={"tools": self.max_steps, "output": 1},
            name="holmes",
        )
        history = chat_to_model_messages(list(msgs) if msgs else [], self.llm.model)

        def token_count(messages_for_count: List[dict]) -> StreamMessage:
            record = model.records[-1]
            return self._emit_token_count(
                messages_for_count,
                record.tools,
                record.raw_response,
                run.max_context_size or self.llm.get_context_window_size(),
                run.maximum_output_token or self.llm.get_maximum_output_token(),
                metadata,
                stats,
            )

        holder: Dict[str, Any] = {}

        async def drive() -> None:
            try:
                async with agent.iter(
                    None,
                    message_history=history,
                    usage_limits=UsageLimits(request_limit=self.max_steps),
                    usage=RunUsage(requests=iteration_offset),
                ) as agent_run:
                    holder["agent_run"] = agent_run
                    node = agent_run.next_node
                    while not isinstance(node, End):
                        if cancel_event and cancel_event.is_set():
                            raise LLMInterruptedError()
                        # The final text answer also passes through CallToolsNode;
                        # only a response with tool calls produces tool events.
                        if Agent.is_call_tools_node(node) and node.model_response.tool_calls:
                            async with node.stream(agent_run.ctx) as stream:
                                async for event in stream:
                                    if isinstance(event, FunctionToolResultEvent):
                                        tool_event = self._tool_result_event(event.part)
                                        if tool_event is not None:
                                            events.put_nowait(tool_event)
                            events.put_nowait(
                                token_count(
                                    model.render_history(
                                        agent_run.ctx.state.message_history, run.pending_call_ids
                                    )
                                )
                            )
                        node = await agent_run.next(node)
                        if Agent.is_call_tools_node(node):
                            # A model request just completed.
                            record = model.records[-1]
                            events.put_nowait(
                                token_count(record.chat_messages + [record.assistant_message])
                            )
                            if record.had_tool_calls and (record.reasoning or record.content):
                                events.put_nowait(
                                    StreamMessage(
                                        event=StreamEvents.AI_MESSAGE,
                                        data={
                                            "content": record.content,
                                            "reasoning": record.reasoning,
                                            "metadata": metadata,
                                        },
                                    )
                                )
                    result = agent_run.result
                    assert result is not None
                    holder["messages"] = model.render_history(result.all_messages())
                    holder["num_llm_calls"] = result.usage.requests
            except BaseException as e:  # noqa: BLE001 - re-raised on the generator
                holder["error"] = e
            finally:
                events.put_nowait(_SENTINEL)

        task = loop.create_task(drive())
        try:
            while True:
                try:
                    item = loop.run_until_complete(
                        asyncio.wait_for(events.get(), timeout=_CANCEL_POLL_SECONDS)
                    )
                except asyncio.TimeoutError:
                    if cancel_event and cancel_event.is_set():
                        task.cancel()
                        try:
                            loop.run_until_complete(task)
                        except BaseException:  # noqa: BLE001
                            pass
                        raise LLMInterruptedError()
                    continue
                if item is _SENTINEL:
                    break
                yield item

            error = _unwrap(holder["error"]) if holder.get("error") is not None else None
            if isinstance(error, AgentPauseRequested):
                agent_run = holder["agent_run"]
                history = model.render_history(
                    agent_run.ctx.state.message_history, run.pending_call_ids
                )
                yield self._build_pause_event(
                    history,
                    error.pending_approvals,
                    error.pending_frontend_calls,
                    model.iteration + iteration_offset,
                    stats,
                )
                return
            if error is not None:
                raise self._map_error(error, model.iteration + iteration_offset)

            messages = holder["messages"]
            last_record = model.records[-1]
            if last_record.finish_reason:
                metadata["finish_reason"] = last_record.finish_reason
            content = last_record.assistant_message.get("content")
            if content:
                trace_span.log(output=content)
            yield StreamMessage(
                event=StreamEvents.ANSWER_END,
                data={
                    "content": content,
                    "messages": messages,
                    "metadata": metadata,
                    "tool_calls": run.all_tool_calls,
                    "num_llm_calls": holder["num_llm_calls"],
                    "prompt": json.dumps(messages, indent=2),
                    "costs": stats.model_dump(),
                },
            )
        finally:
            if not task.done():
                task.cancel()
                try:
                    loop.run_until_complete(task)
                except BaseException:  # noqa: BLE001
                    pass
            executor.shutdown(wait=False, cancel_futures=True)
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

    @staticmethod
    def _tool_result_event(part: Any) -> Optional[StreamMessage]:
        if isinstance(part, ToolReturnPart) and isinstance(part.metadata, dict):
            if part.metadata.get("holmes_pending"):
                return None  # already emitted (approval) or not emitted at all (frontend)
            return StreamMessage(event=StreamEvents.TOOL_RESULT, data=part.metadata)
        # Pydantic AI produced this itself (e.g. an unknown tool name retry prompt).
        return StreamMessage(
            event=StreamEvents.TOOL_RESULT,
            data={
                "tool_call_id": part.tool_call_id,
                "tool_name": part.tool_name or "",
                "name": part.tool_name or "",
                "description": "",
                "role": "tool",
                "result": {"status": "error", "error": part.model_response(), "data": None},
            },
        )

    def _map_error(self, error: BaseException, iteration: int) -> BaseException:
        if isinstance(error, UsageLimitExceeded):
            return Exception(
                f"Too many LLM calls - exceeded max_steps: {iteration}/{self.max_steps}"
            )
        if not isinstance(error, LLMInterruptedError):
            logging.error(f"Pydantic AI engine failed: {type(error).__name__}: {error}")
        return error
