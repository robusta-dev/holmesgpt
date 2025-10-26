from typing import Any, Dict

from holmes.core.tools import (
    Tool,
    ToolInvokeContext,
    Toolset,
    StructuredToolResult,
    StructuredToolResultStatus,
)


class DummyTool(Tool):
    name: str = "dummy_tool"
    description: str = "A dummy tool"

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        return StructuredToolResult(status=StructuredToolResultStatus.SUCCESS)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return ""


class SampleToolset(Toolset):
    name: str = "sample_toolset"
    description: str = "A sample toolset for testing"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("tools", [DummyTool()])
        super().__init__(*args, **kwargs)

    def get_example_config(self) -> Dict[str, Any]:
        return {}
