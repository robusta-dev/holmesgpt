"""Scripted LLM and tools for exercising agent engines without a provider."""

import asyncio
import json
import threading
import time
from typing import Any, Dict, List, Optional

from litellm import ModelResponse
from pydantic import ConfigDict, Field

from holmes.core.engines import get_engine_class
from holmes.core.llm import LLM, ContextWindowUsage
from holmes.core.tools import (
    StructuredToolResult,
    StructuredToolResultStatus,
    Tool,
    ToolInvokeContext,
    ToolParameter,
    Toolset,
    ToolsetStatusEnum,
    ToolsetTag,
)
from holmes.core.tools_utils.tool_executor import ToolExecutor


def llm_response(
    content: Optional[str] = None,
    tool_calls: Optional[List[tuple]] = None,
    *,
    finish_reason: Optional[str] = None,
    cost: float = 0.001,
    prompt_tokens: int = 50,
    completion_tokens: int = 20,
    cached_tokens: Optional[int] = None,
    reasoning_tokens: int = 0,
    reasoning_content: Optional[str] = None,
) -> ModelResponse:
    """Build a real litellm ModelResponse. ``tool_calls`` is [(id, name, args_json)]."""
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {"id": tc_id, "type": "function", "function": {"name": name, "arguments": args}}
            for tc_id, name, args in tool_calls
        ]
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    usage: Dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    if cached_tokens is not None:
        usage["prompt_tokens_details"] = {"cached_tokens": cached_tokens}
    if reasoning_tokens:
        usage["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
    response = ModelResponse(
        id="resp",
        model="scripted",
        choices=[
            {
                "index": 0,
                "finish_reason": finish_reason or ("tool_calls" if tool_calls else "stop"),
                "message": message,
            }
        ],
        usage=usage,
    )
    response._hidden_params = {"response_cost": cost}
    return response


class ScriptedLLM(LLM):
    """Returns pre-built responses in order and records every request."""

    def __init__(self, responses: List[ModelResponse], model: str = "scripted"):
        self.model = model
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def get_context_window_size(self) -> int:
        return 128000

    def get_maximum_output_token(self) -> int:
        return 4096

    def count_tokens(self, messages, tools=None) -> ContextWindowUsage:
        total = len(json.dumps(messages, default=str)) // 4
        return ContextWindowUsage(
            total_tokens=total,
            system_tokens=0,
            tools_to_call_tokens=0,
            tools_tokens=0,
            user_tokens=0,
            assistant_tokens=0,
            other_tokens=0,
        )

    def completion(self, messages, tools=[], tool_choice=None, response_format=None, temperature=None, drop_params=None, stream=None):
        with self._lock:
            self.calls.append(
                {
                    "messages": json.loads(json.dumps(messages, default=str)),
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "response_format": response_format,
                }
            )
            if not self._responses:
                raise AssertionError("ScriptedLLM ran out of responses")
            return self._responses.pop(0)


class _FakeTool(Tool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Tools that honour the toolset's approval_required_tools patterns carry a
    # back-reference to their toolset (as the Prometheus and MCP tools do).
    toolset: Any = Field(default=None, exclude=True)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"{self.name}({json.dumps(params, sort_keys=True)})"


class EchoTool(_FakeTool):
    name: str = "echo"
    description: str = "Echo the params back"
    parameters: Dict[str, ToolParameter] = {
        "text": ToolParameter(description="text to echo", type="string", required=False)
    }

    def _invoke(self, params: Dict, context: ToolInvokeContext) -> StructuredToolResult:
        return StructuredToolResult(
            status=StructuredToolResultStatus.SUCCESS,
            data=f"echo:{json.dumps(params, sort_keys=True)}",
            params=params,
        )


class AsyncInsideTool(_FakeTool):
    """Mimics MCP tools, which run their own event loop per call."""

    name: str = "async_inside"
    description: str = "Runs asyncio.run internally"
    parameters: Dict[str, ToolParameter] = {}

    def _invoke(self, params: Dict, context: ToolInvokeContext) -> StructuredToolResult:
        asyncio.run(asyncio.sleep(0.01))
        return StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data="async ok", params=params)


class BoomTool(_FakeTool):
    name: str = "boom"
    description: str = "Always raises"
    parameters: Dict[str, ToolParameter] = {}

    def _invoke(self, params: Dict, context: ToolInvokeContext) -> StructuredToolResult:
        raise RuntimeError("boom")


class ImageTool(_FakeTool):
    name: str = "image"
    description: str = "Returns an image"
    parameters: Dict[str, ToolParameter] = {}

    def _invoke(self, params: Dict, context: ToolInvokeContext) -> StructuredToolResult:
        return StructuredToolResult(
            status=StructuredToolResultStatus.SUCCESS,
            data="chart",
            params=params,
            images=[{"mimeType": "image/png", "data": "AAAA"}],
            url="http://grafana/panel/1",
        )


class SlowTool(_FakeTool):
    name: str = "slow"
    description: str = "Sleeps"
    parameters: Dict[str, ToolParameter] = {
        "seconds": ToolParameter(description="seconds", type="number", required=True)
    }

    def _invoke(self, params: Dict, context: ToolInvokeContext) -> StructuredToolResult:
        time.sleep(float(params.get("seconds", 0)))
        return StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data="slept", params=params)


class FakeToolset(Toolset):
    model_config = ConfigDict(extra="forbid")


def make_toolset() -> Toolset:
    toolset = FakeToolset(
        name="fake",
        description="fake toolset",
        enabled=True,
        tools=[EchoTool(), AsyncInsideTool(), BoomTool(), ImageTool(), SlowTool()],
        tags=[ToolsetTag.CORE],
    )
    toolset.status = ToolsetStatusEnum.ENABLED
    for tool in toolset.tools:
        tool.toolset = toolset
    return toolset


def make_engine(engine_id: str, responses: List[ModelResponse], max_steps: int = 10):
    llm = ScriptedLLM(responses)
    executor = ToolExecutor([make_toolset()])
    engine = get_engine_class(engine_id)(
        tool_executor=executor, max_steps=max_steps, llm=llm, tool_results_dir=None
    )
    return engine, llm


BASE_MESSAGES = [
    {"role": "system", "content": "You are Holmes."},
    {"role": "user", "content": "What is wrong?"},
]


class OAuthTool(_FakeTool):
    """Mimics an MCP ``_connect`` tool: always needs the user to authenticate."""

    name: str = "connect_service"
    description: str = "Connect to a service"
    parameters: Dict[str, ToolParameter] = {}

    def _invoke(self, params: Dict, context: ToolInvokeContext) -> StructuredToolResult:
        return StructuredToolResult(
            status=StructuredToolResultStatus.APPROVAL_REQUIRED,
            error="Authentication required",
            params={"__oauth_metadata": {"authorization_url": "https://example/auth"}},
        )


class BigAnswerTool(_FakeTool):
    name: str = "big"
    description: str = "Returns a lot of text"
    parameters: Dict[str, ToolParameter] = {
        "chars": ToolParameter(description="size", type="integer", required=True)
    }

    def _invoke(self, params: Dict, context: ToolInvokeContext) -> StructuredToolResult:
        return StructuredToolResult(
            status=StructuredToolResultStatus.SUCCESS,
            data="x" * int(params.get("chars", 100)),
            params=params,
        )


def make_toolset_with(*extra_tools, approval_required_tools=None) -> Toolset:
    toolset = FakeToolset(
        name="fake",
        description="fake toolset",
        enabled=True,
        tools=[EchoTool(), AsyncInsideTool(), BoomTool(), ImageTool(), SlowTool(), *extra_tools],
        tags=[ToolsetTag.CORE],
        approval_required_tools=list(approval_required_tools or []),
    )
    toolset.status = ToolsetStatusEnum.ENABLED
    for tool in toolset.tools:
        tool.toolset = toolset
    return toolset


class SmallWindowLLM(ScriptedLLM):
    """A scripted LLM with a tiny context window so compaction triggers."""

    def __init__(self, responses, context_window: int = 2500, max_output: int = 200):
        super().__init__(responses)
        self._context_window = context_window
        self._max_output = max_output

    def get_context_window_size(self) -> int:
        return self._context_window

    def get_maximum_output_token(self) -> int:
        return self._max_output


def make_engine_with(engine_id: str, llm, toolset, max_steps: int = 10):
    executor = ToolExecutor([toolset])
    return get_engine_class(engine_id)(
        tool_executor=executor, max_steps=max_steps, llm=llm, tool_results_dir=None
    )
