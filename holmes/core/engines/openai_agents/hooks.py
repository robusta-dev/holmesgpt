"""Run hooks that translate SDK lifecycle points into Holmes stream events."""

from typing import Any

from agents import RunHooks

from holmes.core.engines.openai_agents.run_state import AgentRunState
from holmes.utils.stream import StreamEvents, StreamMessage


class HolmesRunHooks(RunHooks):
    def __init__(self, run: AgentRunState) -> None:
        super().__init__()
        self.run = run

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        self.run.emit(
            StreamMessage(
                event=StreamEvents.START_TOOL,
                data={
                    "tool_name": tool.name,
                    "id": getattr(context, "tool_call_id", None),
                },
            )
        )
