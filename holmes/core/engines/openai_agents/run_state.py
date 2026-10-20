"""Per-request state shared by the model adapter, tool wrappers and hooks."""

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from holmes.core.llm_usage import RequestStats
from holmes.core.models import ToolCallResult
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
    tool_number_offset: int = 0
    iteration: int = 0
    stats: RequestStats = field(default_factory=RequestStats)
    metadata: Dict[Any, Any] = field(default_factory=dict)
    tool_calls: List[dict] = field(default_factory=list)
    all_tool_calls: List[dict] = field(default_factory=list)
    results: Dict[str, ToolCallResult] = field(default_factory=dict)
    absorbed_call_ids: set = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_response: Any = None
    last_tools: Optional[list] = None

    def emit(self, message: StreamMessage) -> None:
        self.events.put(message)

    def next_tool_number(self) -> int:
        with self.lock:
            self.tool_number_offset += 1
            return self.tool_number_offset

    def register_result(self, result: ToolCallResult, client_dict: dict) -> None:
        with self.lock:
            self.results[result.tool_call_id] = result
            self.tool_calls.append(client_dict)
            self.all_tool_calls.append(client_dict)
