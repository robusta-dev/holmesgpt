"""``ToolCallingLLM`` whose loop is driven by the OpenAI Agents SDK ``Runner``.

The SDK runs on a private event loop in a driver thread; the sync
``call_stream`` generator drains a queue of Holmes events. Tools execute on
worker threads (so MCP tools can still call ``asyncio.run``), and every LLM
call goes through ``ToolCallingLLM._run_llm_iteration``.
"""

import asyncio
import contextvars
import json
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Type, Union

from agents import (
    Agent,
    MaxTurnsExceeded,
    RunConfig,
    Runner,
    ToolExecutionConfig,
    UserError,
    set_tracing_disabled,
)
from pydantic import BaseModel

from holmes.core.engines import AgentPauseRequested
from holmes.core.engines.openai_agents.hooks import HolmesRunHooks
from holmes.core.engines.openai_agents.model import HolmesOpenAIAgentsModel
from holmes.core.engines.openai_agents.run_state import AgentRunState
from holmes.core.engines.openai_agents.tools import build_function_tools
from holmes.core.models import FrontendToolResult, ToolApprovalDecision
from holmes.core.tool_calling_llm import LLMInterruptedError, ToolCallingLLM
from holmes.core.tracing import DummySpan
from holmes.utils.stream import StreamEvents, StreamMessage

# The SDK would otherwise try to export traces to OpenAI with whatever key it finds.
set_tracing_disabled(True)

_SENTINEL = object()
_TOOL_WORKERS = 16
_CANCEL_POLL_SECONDS = 0.25


def _to_sdk_input_items(messages: List[dict]) -> List[dict]:
    """Text-only view of the history for the SDK's bookkeeping.

    The real transcript the LLM sees is ``AgentRunState.messages``. Tool calls
    and their outputs are deliberately left out: the SDK would otherwise treat
    earlier calls (e.g. ones a resume just answered) as work to redo.
    """
    items: List[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "assistant":
            text = _as_text(m.get("content"))
            if text:
                items.append({"role": "assistant", "content": text})
        elif role in ("user", "system"):
            items.append({"role": role, "content": _as_text(m.get("content"))})
    if not items or items[-1].get("role") != "user":
        items.append({"role": "user", "content": "(continue)"})
    return items


def _as_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(content)


class OpenAIAgentsToolCallingLLM(ToolCallingLLM):
    engine_id = "openai_agents"

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

        events: "queue.Queue[Any]" = queue.Queue()
        run = AgentRunState(
            messages=list(msgs) if msgs else [],
            events=events,
            cancel_event=cancel_event,
            request_context=request_context,
            trace_span=trace_span,
            enable_tool_approval=enable_tool_approval,
            tool_number_offset=tool_number_offset,
            iteration=iteration_offset,
            all_tool_calls=all_tool_calls,
        )
        run.metadata["engine"] = self.engine_id
        max_steps = self.max_steps

        agent = Agent(name="holmes", instructions=None, tools=[])

        def set_agent_tools(tools_openai: list) -> None:
            agent.tools = build_function_tools(self, tools_openai, run)

        set_agent_tools(self._get_tools())
        agent.model = HolmesOpenAIAgentsModel(
            self,
            run,
            response_format=response_format,
            max_steps=max_steps,
            agent_tools_setter=set_agent_tools,
        )
        run_config = RunConfig(
            tracing_disabled=True,
            workflow_name="holmes",
            tool_not_found_behavior="return_error_to_model",
            tool_execution=ToolExecutionConfig(max_function_tool_concurrency=_TOOL_WORKERS),
        )
        holder: Dict[str, Any] = {}

        async def drive() -> None:
            loop = asyncio.get_running_loop()
            holder["loop"] = loop
            loop.set_default_executor(ThreadPoolExecutor(max_workers=_TOOL_WORKERS, thread_name_prefix="holmes-tool"))
            result = Runner.run_streamed(
                agent,
                input=_to_sdk_input_items(run.messages),
                context=run,
                max_turns=max(max_steps - iteration_offset, 1),
                hooks=HolmesRunHooks(run),
                run_config=run_config,
            )
            holder["result"] = result
            async for _ in result.stream_events():
                pass

        def thread_main() -> None:
            try:
                asyncio.run(drive())
            except BaseException as e:  # noqa: BLE001 - re-raised on the caller's thread
                holder["error"] = e
            finally:
                events.put(_SENTINEL)

        threading.Thread(
            target=contextvars.copy_context().run,
            args=(thread_main,),
            daemon=True,
            name="holmes-openai-agents",
        ).start()

        while True:
            try:
                item = events.get(timeout=_CANCEL_POLL_SECONDS)
            except queue.Empty:
                if cancel_event and cancel_event.is_set():
                    self._cancel(holder)
                    raise LLMInterruptedError()
                continue
            if item is _SENTINEL:
                break
            yield item

        error = holder.get("error")
        if isinstance(error, AgentPauseRequested):
            yield self._build_pause_event(
                run.messages, error.pending_approvals, error.pending_frontend_calls,
                run.iteration, run.stats,
            )
            return
        if error is not None:
            raise self._map_error(error, run.iteration)

        content = run.messages[-1].get("content") if run.messages else None
        yield StreamMessage(
            event=StreamEvents.ANSWER_END,
            data={
                "content": content,
                "messages": run.messages,
                "metadata": run.metadata,
                "tool_calls": run.all_tool_calls,
                "num_llm_calls": run.iteration,
                "prompt": json.dumps(run.messages, indent=2),
                "costs": run.stats.model_dump(),
            },
        )

    @staticmethod
    def _cancel(holder: Dict[str, Any]) -> None:
        loop = holder.get("loop")
        result = holder.get("result")
        if loop is not None and result is not None:
            try:
                loop.call_soon_threadsafe(result.cancel, "immediate")
            except RuntimeError:
                pass

    def _map_error(self, error: BaseException, iteration: int) -> BaseException:
        if isinstance(error, MaxTurnsExceeded):
            return Exception(
                f"Too many LLM calls - exceeded max_steps: {iteration}/{self.max_steps}"
            )
        if isinstance(error, UserError) and isinstance(error.__cause__, LLMInterruptedError):
            return error.__cause__
        if isinstance(error, LLMInterruptedError):
            return error
        logging.error(f"OpenAI Agents engine failed: {type(error).__name__}: {error}")
        return error
