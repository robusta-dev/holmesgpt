"""Middleware that enforces Holmes's loop rules and executes Holmes tools."""

import json
import logging
from typing import TYPE_CHECKING, Any, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)

from holmes.core.engines.langgraph.messages import RAW_KEY
from holmes.core.engines.langgraph.run_state import LangGraphRunState
from holmes.core.engines.langgraph.tools import build_langchain_tools
from holmes.core.models import ToolCallResult
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.utils.stream import StreamEvents, StreamMessage

if TYPE_CHECKING:
    from holmes.core.tool_calling_llm import ToolCallingLLM


class HolmesLoopMiddleware(AgentMiddleware):
    def __init__(self, engine: "ToolCallingLLM", run: LangGraphRunState) -> None:
        super().__init__()
        self.engine = engine
        self.run = run

    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        from holmes.core.tool_calling_llm import LLMInterruptedError

        run = self.run
        if run.cancel_event and run.cancel_event.is_set():
            raise LLMInterruptedError()
        i = run.iteration + 1
        if i > run.max_steps:
            raise Exception(f"Too many LLM calls - exceeded max_steps: {i}/{run.max_steps}")
        if i == run.max_steps:
            # Same rule as the legacy loop: no tools on the last step.
            request = request.override(tools=[])
        else:
            # Tool list can change mid-run (OAuth discovery, skill activation).
            current = self.engine._get_tools()
            if run.last_tools is not None:
                old_names = {t["function"]["name"] for t in run.last_tools}
                new_names = {t["function"]["name"] for t in current}
                if old_names != new_names:
                    logging.warning(
                        f"Tool list changed - refreshing ({len(run.last_tools)} -> {len(current)} tools)"
                    )
                    request = request.override(tools=build_langchain_tools(current))
        return handler(request)

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        from holmes.core.tool_calling_llm import (
            LLMInterruptedError,
            extract_bash_session_prefixes_by_agent,
            frontend_call_dict_from_result,
            pending_approval_from_result,
            pending_frontend_from_result,
        )

        run = self.run
        engine = self.engine
        if run.cancel_event and run.cancel_event.is_set():
            raise LLMInterruptedError()
        tc = request.tool_call
        name = tc["name"]
        call_id = tc["id"]
        tool_number = run.next_tool_number()
        writer = request.runtime.stream_writer
        writer(StreamMessage(event=StreamEvents.START_TOOL, data={"tool_name": name, "id": call_id}))

        litellm_call = ChatCompletionMessageFunctionToolCall(
            id=call_id,
            type="function",
            function=Function(name=name, arguments=json.dumps(tc.get("args") or {})),
        )
        try:
            with run.lock:
                history_snapshot = list(run.messages)
            result: ToolCallResult = engine._invoke_llm_tool_call(
                tool_to_call=litellm_call,
                previous_tool_calls=run.tool_calls,
                trace_span=run.trace_span,
                tool_number=tool_number,
                session_approved_prefixes_by_agent=extract_bash_session_prefixes_by_agent(
                    history_snapshot
                ),
                request_context=run.request_context,
                enable_tool_approval=run.enable_tool_approval,
            )
        except LLMInterruptedError:
            raise
        except Exception as e:
            logging.error(f"Tool {name} raised: {e}", exc_info=True)
            result = ToolCallResult(
                tool_call_id=call_id,
                tool_name=name,
                description="",
                result=StructuredToolResult(
                    status=StructuredToolResultStatus.ERROR, error=str(e), params=None
                ),
            )

        outcome = engine._classify_tool_result(result, run.enable_tool_approval)
        client_dict = result.to_client_dict()
        if outcome != "done":
            # Waiting for a human or the client: no tool message in the transcript;
            # the model adapter stops the run at the next model call.
            with run.lock:
                run.pending_call_ids.add(call_id)
                if outcome == "pending_approval":
                    run.pending_approvals.append(pending_approval_from_result(result))
                    run.all_tool_calls.append(client_dict)
                else:
                    run.pending_frontend_calls.append(pending_frontend_from_result(result))
                    call_dict = frontend_call_dict_from_result(result)
                    run.tool_calls.append(call_dict)
                    run.all_tool_calls.append(call_dict)
            if outcome == "pending_approval":
                writer(StreamMessage(event=StreamEvents.TOOL_RESULT, data=client_dict))
            return ToolMessage(
                content="pending: waiting for the user",
                tool_call_id=call_id,
                name=name,
                additional_kwargs={"holmes_pending": True},
            )

        llm_message = result.to_llm_message(supports_vision=engine._supports_vision())
        with run.lock:
            run.tool_calls.append(client_dict)
            run.all_tool_calls.append(client_dict)
            run.messages.append(llm_message)
        writer(StreamMessage(event=StreamEvents.TOOL_RESULT, data=client_dict))
        return ToolMessage(
            content=llm_message["content"],
            tool_call_id=call_id,
            name=name,
            status="error" if result.result.status == StructuredToolResultStatus.ERROR else "success",
            additional_kwargs={RAW_KEY: llm_message},
        )
