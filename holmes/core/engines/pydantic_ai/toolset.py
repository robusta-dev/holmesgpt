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
from holmes.core.models import ToolCallResult
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus

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
        *,
        request_context: Optional[Dict[str, Any]],
        trace_span: Any,
        cancel_event: Any,
        max_steps: int,
        tool_number_offset: int,
        executor: ThreadPoolExecutor,
        start_tool_callback,
    ) -> None:
        self._engine = engine
        self._request_context = request_context
        self._trace_span = trace_span
        self._cancel_event = cancel_event
        self._max_steps = max_steps
        self._tool_number = tool_number_offset
        self._executor = executor
        self._start_tool_callback = start_tool_callback
        self._lock = asyncio.Lock()
        self.previous_tool_calls: List[dict] = []
        self.all_tool_calls: List[dict] = []
        self.results: Dict[str, ToolCallResult] = {}

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
        )

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
            model_messages_to_chat(ctx.messages)
        )
        loop = asyncio.get_running_loop()
        try:
            result: ToolCallResult = await loop.run_in_executor(
                self._executor,
                lambda: self._engine._invoke_llm_tool_call(
                    tool_to_call=tool_call,
                    previous_tool_calls=self.previous_tool_calls,
                    trace_span=self._trace_span,
                    tool_number=tool_number,
                    user_approved=ctx.tool_call_approved,
                    session_approved_prefixes_by_agent=session_prefixes,
                    request_context=self._request_context,
                    enable_tool_approval=False,
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

        if result.result.status == StructuredToolResultStatus.APPROVAL_REQUIRED:
            self._engine._mark_approval_unavailable(result)
        elif result.result.status == StructuredToolResultStatus.FRONTEND_PAUSE:
            result.result.status = StructuredToolResultStatus.ERROR
            result.result.error = (
                "Frontend tools that pause the conversation are not supported by this agent engine."
            )

        client_dict = result.to_client_dict()
        self.previous_tool_calls.append(client_dict)
        self.all_tool_calls.append(client_dict)
        self.results[tool_call_id] = result
        llm_message = result.to_llm_message(supports_vision=self._engine._supports_vision())
        return ToolReturn(return_value=llm_message["content"], metadata=client_dict)
