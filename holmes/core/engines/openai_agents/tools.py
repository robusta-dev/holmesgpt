"""Wrap Holmes tools as SDK ``FunctionTool``s that run on worker threads."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, List

from agents import FunctionTool, ToolOutputImage, ToolOutputText
from agents.tool_context import ToolContext
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)

from holmes.core.engines.openai_agents.run_state import AgentRunState
from holmes.core.models import ToolCallResult
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.utils.stream import StreamEvents, StreamMessage

if TYPE_CHECKING:
    from holmes.core.tool_calling_llm import ToolCallingLLM


def _error_result(tool_call_id: str, tool_name: str, error: str) -> ToolCallResult:
    return ToolCallResult(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        description="",
        result=StructuredToolResult(
            status=StructuredToolResultStatus.ERROR, error=error, params=None
        ),
    )


async def invoke_holmes_tool(
    engine: "ToolCallingLLM",
    run: AgentRunState,
    tool_call_id: str,
    name: str,
    arguments: str,
) -> ToolCallResult:
    """Run one Holmes tool on a worker thread and publish its result.

    Reuses ``ToolCallingLLM._invoke_llm_tool_call`` (argument parsing, repeat
    guard, spill-to-disk, OTel) so behaviour matches the legacy loop.
    """
    from holmes.core.tool_calling_llm import (
        LLMInterruptedError,
        extract_bash_session_prefixes_by_agent,
    )

    if run.cancel_event and run.cancel_event.is_set():
        raise LLMInterruptedError()
    tool_number = run.next_tool_number()
    tool_call = ChatCompletionMessageFunctionToolCall(
        id=tool_call_id,
        type="function",
        function=Function(name=name, arguments=arguments or "{}"),
    )
    try:
        result: ToolCallResult = await asyncio.to_thread(
            engine._invoke_llm_tool_call,
            tool_to_call=tool_call,
            previous_tool_calls=run.tool_calls,
            trace_span=run.trace_span,
            tool_number=tool_number,
            session_approved_prefixes_by_agent=extract_bash_session_prefixes_by_agent(
                run.messages
            ),
            request_context=run.request_context,
            enable_tool_approval=False,
        )
    except LLMInterruptedError:
        raise
    except Exception as e:
        # The SDK aborts the whole run on a tool exception; the legacy
        # loop feeds the error back to the model instead.
        logging.error(f"Tool {name} raised: {e}", exc_info=True)
        result = _error_result(tool_call_id, name, str(e))

    if result.result.status == StructuredToolResultStatus.APPROVAL_REQUIRED:
        engine._mark_approval_unavailable(result)
    elif result.result.status == StructuredToolResultStatus.FRONTEND_PAUSE:
        result.result.status = StructuredToolResultStatus.ERROR
        result.result.error = (
            "Frontend tools that pause the conversation are not supported by this agent engine."
        )

    client_dict = result.to_client_dict()
    run.register_result(result, client_dict)
    run.emit(StreamMessage(event=StreamEvents.TOOL_RESULT, data=client_dict))
    return result


def build_function_tool(
    engine: "ToolCallingLLM", tool_openai: dict, run: AgentRunState
) -> FunctionTool:
    function = tool_openai["function"]
    name = function["name"]

    async def on_invoke(ctx: ToolContext[Any], args: str) -> Any:
        result = await invoke_holmes_tool(engine, run, ctx.tool_call_id, name, args)
        llm_message = result.to_llm_message(supports_vision=engine._supports_vision())
        content = llm_message["content"]
        if isinstance(content, str):
            return content
        outputs: List[Any] = []
        for part in content:
            if part.get("type") == "text":
                outputs.append(ToolOutputText(text=part["text"]))
            elif part.get("type") == "image_url":
                outputs.append(ToolOutputImage(image_url=part["image_url"]["url"]))
        return outputs

    return FunctionTool(
        name=name,
        description=function.get("description") or "",
        params_json_schema=function.get("parameters") or {"type": "object", "properties": {}},
        on_invoke_tool=on_invoke,
        # Holmes applies its own strict-mode rules when building the request;
        # the SDK's strict transform rejects dynamic-key schemas.
        strict_json_schema=False,
    )


def build_function_tools(
    engine: "ToolCallingLLM", tools_openai: list, run: AgentRunState
) -> List[FunctionTool]:
    return [build_function_tool(engine, t, run) for t in tools_openai]
