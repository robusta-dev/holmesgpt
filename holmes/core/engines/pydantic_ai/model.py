"""``pydantic_ai.models.Model`` that delegates every request to ``DefaultLLM.completion``."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ThinkingPart, ToolCallPart
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

from holmes.core.engines.pydantic_ai.convert import (
    PROVIDER_NAME,
    RAW_KEY,
    UNKNOWN_TOOL,
    is_internal_tool,
    map_finish_reason,
    model_messages_to_chat,
    tool_def_to_openai,
)
from holmes.core.llm_usage import RequestStats, extract_usage_from_response

if TYPE_CHECKING:
    from holmes.core.tool_calling_llm import ToolCallingLLM


@dataclass
class ModelCallRecord:
    """What one LLM call sent and got back, for TOKEN_COUNT / AI_MESSAGE events."""

    chat_messages: List[dict]
    tools: Optional[list]
    raw_response: Any
    assistant_message: dict
    finish_reason: Optional[str]
    reasoning: Optional[str]
    content: Optional[str]
    had_tool_calls: bool


class HolmesPydanticModel(Model):
    def __init__(
        self,
        engine: "ToolCallingLLM",
        *,
        response_format: Any,
        trace_span: Any,
        cancel_event: Any,
        max_steps: int,
        stats: RequestStats,
    ) -> None:
        super().__init__(
            settings=None,
            profile=ModelProfile(
                supports_tools=True,
                supports_json_schema_output=True,
                supports_json_object_output=True,
                supports_inline_system_prompts=True,
                default_structured_output_mode="native",
                json_schema_transformer=None,
            ),
        )
        self.engine = engine
        self.response_format = response_format
        self.trace_span = trace_span
        self.cancel_event = cancel_event
        self.max_steps = max_steps
        self.stats = stats
        self.records: List[ModelCallRecord] = []
        self.iteration = 0

    @property
    def model_name(self) -> str:
        return self.engine.llm.model

    @property
    def system(self) -> str:
        return PROVIDER_NAME

    @property
    def provider(self):  # type: ignore[override]
        return None

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        from holmes.core.tool_calling_llm import LLMInterruptedError

        if self.cancel_event and self.cancel_event.is_set():
            raise LLMInterruptedError()
        model_settings, params = self.prepare_request(model_settings, model_request_parameters)

        chat_messages = model_messages_to_chat(messages)
        known_names = {t.name for t in params.function_tools}
        tools = [tool_def_to_openai(t) for t in params.function_tools if not is_internal_tool(t)] or None
        tool_choice = "auto" if tools else None

        self.iteration += 1
        # Blocking is fine: nothing else runs on the private loop during a model
        # call, and it keeps the OTel/Sentry context on the calling thread.
        full_response, _ = self.engine._run_llm_iteration(
            messages=chat_messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=self.response_format,
            trace_span=self.trace_span,
            iteration=self.iteration,
            stats=self.stats,
        )
        if self.cancel_event and self.cancel_event.is_set():
            raise LLMInterruptedError()

        msg = full_response.choices[0].message
        assistant_dict = msg.model_dump(exclude_defaults=True, exclude_unset=True, exclude_none=True)
        try:
            finish_reason = full_response.choices[0].finish_reason
        except (AttributeError, IndexError):
            finish_reason = None
        finish_reason = finish_reason if isinstance(finish_reason, str) else None

        parts: List[Any] = []
        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning:
            parts.append(ThinkingPart(content=reasoning, provider_name=PROVIDER_NAME))
        content = msg.content if isinstance(msg.content, str) else None
        if content:
            parts.append(TextPart(content=content))
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            fn = getattr(tc, "function", None)
            if fn is None:
                parts.append(ToolCallPart(tool_name="Unknown_Custom_Tool", args="{}", tool_call_id=tc.id))
                continue
            if fn.name not in known_names and UNKNOWN_TOOL in known_names:
                parts.append(
                    ToolCallPart(
                        tool_name=UNKNOWN_TOOL,
                        args={"name": fn.name, "arguments": fn.arguments or "{}"},
                        tool_call_id=tc.id,
                    )
                )
                continue
            parts.append(
                ToolCallPart(tool_name=fn.name, args=fn.arguments or "{}", tool_call_id=tc.id)
            )

        self.records.append(
            ModelCallRecord(
                chat_messages=chat_messages,
                tools=tools,
                raw_response=full_response,
                assistant_message=assistant_dict,
                finish_reason=finish_reason,
                reasoning=reasoning,
                content=content,
                had_tool_calls=bool(tool_calls),
            )
        )

        u = extract_usage_from_response(full_response)
        usage = RequestUsage(
            input_tokens=u["prompt_tokens"],
            output_tokens=u["completion_tokens"],
            cache_read_tokens=u.get("cached_tokens") or 0,
            cache_write_tokens=u.get("cache_creation_tokens") or 0,
            details={"reasoning_tokens": u.get("reasoning_tokens") or 0},
        )
        return ModelResponse(
            parts=parts,
            usage=usage,
            model_name=getattr(full_response, "model", None) or self.model_name,
            provider_name=PROVIDER_NAME,
            provider_response_id=getattr(full_response, "id", None),
            finish_reason=map_finish_reason(finish_reason),  # type: ignore[arg-type]
            metadata={RAW_KEY: assistant_dict},
        )
