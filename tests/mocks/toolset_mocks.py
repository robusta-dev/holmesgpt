from typing import Any, Dict, List

from holmes.core.tools import Tool, Toolset, StructuredToolResult, ToolResultStatus


class DummyTool(Tool):
    name: str = "dummy_tool"
    description: str = "A dummy tool"

    def _invoke(self, params: Dict) -> StructuredToolResult:
        return StructuredToolResult(status=ToolResultStatus.SUCCESS)

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return ""


class SampleToolset(Toolset):
    name: str = "sample_toolset"
    description: str = "A sample toolset for testing"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tools: List[Tool] = [DummyTool()]

    def get_example_config(self) -> Dict[str, Any]:
        return {}
