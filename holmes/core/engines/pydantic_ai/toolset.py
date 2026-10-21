"""Expose Holmes tools to Pydantic AI through a custom ``AbstractToolset``."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)
from pydantic_ai.messages import ToolReturn
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import ToolsetTool

from holmes.core.engines.pydantic_ai.convert import (
    UNKNOWN_TOOL,
    model_messages_to_chat,
    parse_args_leniently,
)
from holmes.core.engines.pydantic_ai.run_state import PydanticRunState
from holmes.core.models import ToolCallResult
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.utils.stream import StreamEvents, StreamMessage

PENDING_PLACEHOLDER = "pending: waiting for the user"

if TYPE_CHECKING:
    from holmes.core.tool_calling_llm import ToolCallingLLM


class _LenientArgsValidator:
    """Accept whatever the model sent; ``Tool.invoke`` coerces parameters itself."""

    def validate_json(self, input: Any, **kwargs: Any) -> Any:
        return parse_args_leniently(input)

    def validate_python(self, input: Any, **kwargs: Any) -> Any:
        return parse_args_leniently(input)


class HolmesToolset(AbstractToolset[None]):
    def __init__(
        self,
        engine: "ToolCallingLLM",
        run: PydanticRunState,
        *,
        request_context: Optional[Dict[str, Any]],
        trace_span: Any,
        cancel_event: Any,
        max_steps: int,
        tool_number_offset: int,
        executor: ThreadPoolExecutor,
        model: Any,
        start_tool_callback,
    ) -> None:
        self._engine = engine
        self._run = run
        self._request_context = request_context
        self._trace_span = trace_span
        self._cancel_event = cancel_event
        self._max_steps = max_steps
        self._tool_number = tool_number_offset
        self._executor = executor
        self._model = model  # for render_history (compacted prefix) in bash prefix scoping
        self._start_tool_callback = start_tool_callback
        self._lock = asyncio.Lock()

    @property
    def id(self) -> str:
        return "holmes"

    def _internal_tool(self) -> ToolsetTool[None]:
        return ToolsetTool(
            toolset=self,
            max_retries=self._max_steps,
            tool_def=ToolDefinition(
                name=UNKNOWN_TOOL,
                description="internal",
                parameters_json_schema={"type": "object", "properties": {}},
                metadata={"holmes_internal": True},
            ),
            args_validator=_LenientArgsValidator(),  # type: ignore[arg-type]
        )

    async def get_tools(self, ctx: RunContext[None]) -> dict[str, ToolsetTool[None]]:
        tools: dict[str, ToolsetTool[None]] = {UNKNOWN_TOOL: self._internal_tool()}
        # Same rule as the legacy loop: on the last allowed step the model gets
        # no tools so it has to answer (calls it makes anyway still execute).
        if ctx.usage.requests + 1 >= self._max_steps:
            return tools
        for d in self._engine._get_tools():
            fn = d["function"]
            tools[fn["name"]] = ToolsetTool(
                toolset=self,
                max_retries=self._max_steps,
                tool_def=ToolDefinition(
                    name=fn["name"],
                    description=fn.get("description"),
                    parameters_json_schema=fn.get("parameters") or {"type": "object", "properties": {}},
                    strict=fn.get("strict"),
                    metadata={"holmes_openai_tool": d},
                ),
                args_validator=_LenientArgsValidator(),  # type: ignore[arg-type]
            )
        return tools

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[None], tool: ToolsetTool[None]
    ) -> Any:
        from holmes.core.tool_calling_llm import (
            LLMInterruptedError,
            extract_bash_session_prefixes_by_agent,
            frontend_call_dict_from_result,
            pending_approval_from_result,
            pending_frontend_from_result,
        )

        run = self._run
        if self._cancel_event and self._cancel_event.is_set():
            raise LLMInterruptedError()
        arguments = json.dumps(tool_args)
        if name == UNKNOWN_TOOL:
            name = str(tool_args.get("name") or "unknown_tool")
            raw = tool_args.get("arguments")
            arguments = raw if isinstance(raw, str) else json.dumps(raw or {})
        async with self._lock:
            self._tool_number += 1
            tool_number = self._tool_number
        tool_call_id = ctx.tool_call_id or ""
        self._start_tool_callback(name, tool_call_id)

        tool_call = ChatCompletionMessageFunctionToolCall(
            id=tool_call_id,
            type="function",
            function=Function(name=name, arguments=arguments),
        )
        session_prefixes = extract_bash_session_prefixes_by_agent(
            self._model.render_history(ctx.messages)
        )
        loop = asyncio.get_running_loop()
        try:
            result: ToolCallResult = await loop.run_in_executor(
                self._executor,
                lambda: self._engine._invoke_llm_tool_call(
                    tool_to_call=tool_call,
                    previous_tool_calls=run.tool_calls,
                    trace_span=self._trace_span,
                    tool_number=tool_number,
                    user_approved=ctx.tool_call_approved,
                    session_approved_prefixes_by_agent=session_prefixes,
                    request_context=self._request_context,
                    enable_tool_approval=run.enable_tool_approval,
                ),
            )
        except LLMInterruptedError:
            raise
        except Exception as e:
            logging.error(f"Tool {name} raised: {e}", exc_info=True)
            result = ToolCallResult(
                tool_call_id=tool_call_id,
                tool_name=name,
                description="",
                result=StructuredToolResult(
                    status=StructuredToolResultStatus.ERROR, error=str(e), params=None
                ),
            )

        outcome = self._engine._classify_tool_result(result, run.enable_tool_approval)
        client_dict = result.to_client_dict()
        if outcome == "pending_approval":
            run.pending_call_ids.add(tool_call_id)
            run.pending_approvals.append(pending_approval_from_result(result))
            run.all_tool_calls.append(client_dict)
            # Legacy emits TOOL_RESULT for a pending approval; the metadata marks
            # it so the engine does not emit a second one from the stream event.
            run.emit(StreamMessage(event=StreamEvents.TOOL_RESULT, data=client_dict))
            return ToolReturn(return_value=PENDING_PLACEHOLDER, metadata={"holmes_pending": True})
        if outcome == "pending_frontend":
            run.pending_call_ids.add(tool_call_id)
            run.pending_frontend_calls.append(pending_frontend_from_result(result))
            call_dict = frontend_call_dict_from_result(result)
            run.tool_calls.append(call_dict)
            run.all_tool_calls.append(call_dict)
            return ToolReturn(return_value=PENDING_PLACEHOLDER, metadata={"holmes_pending": True})

        run.tool_calls.append(client_dict)
        run.all_tool_calls.append(client_dict)
        run.results[tool_call_id] = result
        llm_message = result.to_llm_message(supports_vision=self._engine._supports_vision())
        return ToolReturn(return_value=llm_message["content"], metadata=client_dict)
