"""``ToolCallingLLM`` whose loop is LangChain's ``create_agent`` graph on LangGraph.

Fully synchronous: ``graph.stream`` runs the model node on the calling thread
and tool calls on a thread pool, so no event loop is involved and MCP tools
can still call ``asyncio.run``.
"""

import json
import logging
import threading
from typing import Any, Dict, List, Optional, Type, Union

from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from holmes.core.engines.langgraph.chat_model import HolmesChatModel
from holmes.core.engines.langgraph.messages import from_openai_dicts
from holmes.core.engines.langgraph.middleware import HolmesLoopMiddleware
from holmes.core.engines.langgraph.run_state import LangGraphRunState
from holmes.core.engines.langgraph.tools import build_langchain_tools
from holmes.core.models import FrontendToolResult, ToolApprovalDecision
from holmes.core.tool_calling_llm import LLMInterruptedError, ToolCallingLLM
from holmes.core.tracing import DummySpan
from holmes.utils.stream import StreamEvents, StreamMessage

_TOOL_WORKERS = 16


class LangGraphToolCallingLLM(ToolCallingLLM):
    engine_id = "langgraph"

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

        run = LangGraphRunState(
            messages=list(msgs) if msgs else [],
            cancel_event=cancel_event,
            request_context=request_context,
            trace_span=trace_span,
            max_steps=self.max_steps,
            tool_number_offset=tool_number_offset,
            iteration=iteration_offset,
            all_tool_calls=all_tool_calls,
        )
        run.metadata["engine"] = self.engine_id

        model = HolmesChatModel(engine=self, run=run, response_format=response_format)
        tools = build_langchain_tools(self._get_tools())
        # system_prompt=None: the history already starts with Holmes's own system message.
        graph = create_agent(
            model,
            tools=tools,
            system_prompt=None,
            middleware=[HolmesLoopMiddleware(self, run)],
            name="holmes",
        )
        lc_input = from_openai_dicts(run.messages)
        remaining = max(self.max_steps - iteration_offset, 1)
        config = {
            # One model step plus one tools step per iteration, plus slack.
            "recursion_limit": 2 * remaining + 2,
            "max_concurrency": _TOOL_WORKERS,
        }

        try:
            for mode, chunk in graph.stream(
                {"messages": lc_input}, config=config, stream_mode=["updates", "custom"]
            ):
                if mode == "custom" and isinstance(chunk, StreamMessage):
                    yield chunk
                if cancel_event and cancel_event.is_set():
                    raise LLMInterruptedError()
        except GraphRecursionError as e:
            raise Exception(
                f"Too many LLM calls - exceeded max_steps: {run.iteration}/{self.max_steps}"
            ) from e
        except LLMInterruptedError:
            raise
        except Exception as e:
            logging.error(f"LangGraph engine failed: {type(e).__name__}: {e}")
            raise

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
