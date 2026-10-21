"""Per-request state shared by the Pydantic AI model adapter, toolset and engine."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from holmes.core.llm_usage import RequestStats
from holmes.core.models import PendingFrontendToolCall, PendingToolApproval, ToolCallResult
from holmes.core.tool_calling_llm import RepeatCallGuard
from holmes.utils.stream import StreamMessage


@dataclass
class PydanticRunState:
    emit: Callable[[StreamMessage], None]
    enable_tool_approval: bool = False
    stats: RequestStats = field(default_factory=RequestStats)
    metadata: Dict[Any, Any] = field(default_factory=dict)
    guard: RepeatCallGuard = field(default_factory=RepeatCallGuard)
    all_tool_calls: List[dict] = field(default_factory=list)
    results: Dict[str, ToolCallResult] = field(default_factory=dict)
    pending_call_ids: Set[str] = field(default_factory=set)
    pending_approvals: List[PendingToolApproval] = field(default_factory=list)
    pending_frontend_calls: List[PendingFrontendToolCall] = field(default_factory=list)
    max_context_size: Optional[int] = None
    maximum_output_token: Optional[int] = None
    # Compaction replaces a prefix of the history. Pydantic AI's state is
    # append-only and never stores a processed history, so the compacted
    # prefix is cached here and substituted for the first ``compacted_prefix_len``
    # state messages on every later call.
    compacted_prefix_len: int = 0
    compacted_prefix: List[dict] = field(default_factory=list)

    @property
    def tool_calls(self) -> List[dict]:
        return self.guard.tool_calls

    @property
    def has_pending(self) -> bool:
        return bool(self.pending_approvals or self.pending_frontend_calls)
