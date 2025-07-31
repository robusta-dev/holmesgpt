from typing import Any, Dict

from holmes.core.tools import Toolset, ToolsetTag
from holmes.core.hypothesis_tracking import UpdateHypotheses


class HypothesisTrackingToolset(Toolset):
    """Toolset for tracking and managing investigation hypotheses"""

    def __init__(self):
        tools = [UpdateHypotheses()]
        super().__init__(
            name="hypothesis_tracking",
            description="Track and manage investigation hypotheses with evidence",
            tools=tools,
            tags=[ToolsetTag.CORE, ToolsetTag.CLI],
            experimental=True,
            llm_instructions=self._get_llm_instructions(),
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {}

    def _get_llm_instructions(self) -> str:
        return """
## Hypothesis Tracking Tool

Use update_hypotheses to systematically track your investigation progress.

**Status Types:**
- `pending`: Not yet investigated
- `investigating`: Actively gathering evidence
- `confirmed`: Proven with definitive evidence
- `refuted`: Disproven by evidence

**Key Points:**
- The tool preserves all hypotheses - only include ones you're updating
- Be specific about evidence from each tool
- Never remove hypotheses, only change their status

**Example Usage:**
```json
{
  "hypotheses": [
    {
      "id": "h1",
      "description": "Memory leak in application code",
      "status": "investigating",
      "evidence_for": ["Memory usage increases linearly over 6 hours"],
      "evidence_against": [],
      "next_steps": ["Check heap dumps"],
      "tool_calls_made": ["prometheus_query"]
    }
  ]
}
```
"""
