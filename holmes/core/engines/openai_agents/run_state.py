"""Per-request state shared by the model adapter, tool wrappers and hooks."""

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from holmes.core.llm_usage import RequestStats
from holmes.core.models import PendingFrontendToolCall, PendingToolApproval, ToolCallResult
from holmes.core.tool_calling_llm import RepeatCallGuard
from holmes.utils.stream import StreamMessage


@dataclass
class AgentRunState:
    """Mutable state of one ``call_stream`` run.

    The OpenAI-format ``messages`` list is the authoritative transcript: it is
    what the LLM sees and what ``ai_answer_end.messages`` returns. The SDK's
    own Responses-style items are only its bookkeeping.
    """

    messages: List[dict]
    events: "queue.Queue[Any]"
    cancel_event: Optional[threading.Event]
    request_context: Optional[Dict[str, Any]]
    trace_span: Any
    enable_tool_approval: bool = False
    tool_number_offset: int = 0
    iteration: int = 0
    stats: RequestStats = field(default_factory=RequestStats)
    metadata: Dict[Any, Any] = field(default_factory=dict)
    guard: RepeatCallGuard = field(default_factory=RepeatCallGuard)
    all_tool_calls: List[dict] = field(default_factory=list)
    results: Dict[str, ToolCallResult] = field(default_factory=dict)
    absorbed_call_ids: Set[str] = field(default_factory=set)
    pending_call_ids: Set[str] = field(default_factory=set)
    pending_approvals: List[PendingToolApproval] = field(default_factory=list)
    pending_frontend_calls: List[PendingFrontendToolCall] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_response: Any = None
    last_tools: Optional[list] = None
    max_context_size: Optional[int] = None
    maximum_output_token: Optional[int] = None

    @property
    def tool_calls(self) -> List[dict]:
        """Calls the repeat-call safeguard compares against (narrowed after compaction)."""
        return self.guard.tool_calls

    @property
    def has_pending(self) -> bool:
        return bool(self.pending_approvals or self.pending_frontend_calls)

    def emit(self, message: StreamMessage) -> None:
        self.events.put(message)

    def next_tool_number(self) -> int:
        with self.lock:
            self.tool_number_offset += 1
            return self.tool_number_offset

    def register_result(self, result: ToolCallResult, client_dict: dict) -> None:
        with self.lock:
            self.results[result.tool_call_id] = result
            self.guard.tool_calls.append(client_dict)
            self.all_tool_calls.append(client_dict)

    def register_pending_approval(self, result: ToolCallResult, approval: PendingToolApproval, client_dict: dict) -> None:
        with self.lock:
            self.pending_call_ids.add(result.tool_call_id)
            self.pending_approvals.append(approval)
            self.all_tool_calls.append(client_dict)

    def register_pending_frontend(self, result: ToolCallResult, call: PendingFrontendToolCall, call_dict: dict) -> None:
        with self.lock:
            self.pending_call_ids.add(result.tool_call_id)
            self.pending_frontend_calls.append(call)
            self.guard.tool_calls.append(call_dict)
            self.all_tool_calls.append(call_dict)
