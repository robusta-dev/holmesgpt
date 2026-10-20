"""Per-request state shared by the chat model, middleware and engine."""

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from holmes.core.llm_usage import RequestStats


@dataclass
class LangGraphRunState:
    messages: List[dict]  # authoritative OpenAI-format transcript
    cancel_event: Optional[threading.Event]
    request_context: Optional[Dict[str, Any]]
    trace_span: Any
    max_steps: int
    tool_number_offset: int = 0
    iteration: int = 0
    stats: RequestStats = field(default_factory=RequestStats)
    metadata: Dict[Any, Any] = field(default_factory=dict)
    tool_calls: List[dict] = field(default_factory=list)
    all_tool_calls: List[dict] = field(default_factory=list)
    last_response: Any = None
    last_tools: Optional[list] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def next_tool_number(self) -> int:
        with self.lock:
            self.tool_number_offset += 1
            return self.tool_number_offset
