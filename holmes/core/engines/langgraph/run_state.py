"""Per-request state shared by the chat model, middleware and engine."""

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from holmes.core.llm_usage import RequestStats
from holmes.core.models import PendingFrontendToolCall, PendingToolApproval
from holmes.core.tool_calling_llm import RepeatCallGuard


@dataclass
class LangGraphRunState:
    messages: List[dict]  # authoritative OpenAI-format transcript
    cancel_event: Optional[threading.Event]
    request_context: Optional[Dict[str, Any]]
    trace_span: Any
    max_steps: int
    enable_tool_approval: bool = False
    tool_number_offset: int = 0
    iteration: int = 0
    stats: RequestStats = field(default_factory=RequestStats)
    metadata: Dict[Any, Any] = field(default_factory=dict)
    guard: RepeatCallGuard = field(default_factory=RepeatCallGuard)
    all_tool_calls: List[dict] = field(default_factory=list)
    pending_call_ids: Set[str] = field(default_factory=set)
    pending_approvals: List[PendingToolApproval] = field(default_factory=list)
    pending_frontend_calls: List[PendingFrontendToolCall] = field(default_factory=list)
    last_response: Any = None
    last_tools: Optional[list] = None
    max_context_size: Optional[int] = None
    maximum_output_token: Optional[int] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def tool_calls(self) -> List[dict]:
        return self.guard.tool_calls

    @property
    def has_pending(self) -> bool:
        return bool(self.pending_approvals or self.pending_frontend_calls)

    def next_tool_number(self) -> int:
        with self.lock:
            self.tool_number_offset += 1
            return self.tool_number_offset
