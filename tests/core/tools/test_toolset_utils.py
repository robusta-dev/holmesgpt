import pytest

from holmes.core.tools.logging_api import BasePodLoggingToolset, FetchPodLogsParams
from holmes.core.tools.tools import (
    StructuredToolResult,
    ToolResultStatus,
    Toolset,
    ToolsetStatusEnum,
)
from holmes.core.tools.toolset_utils import filter_out_default_logging_toolset


class DummyNonLoggingToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="non_logging_toolset", description="Dummy toolset", tools=[]
        )

    def _invoke(self, params: dict) -> StructuredToolResult:
        return StructuredToolResult(status=ToolResultStatus.SUCCESS)

    def get_parameterized_one_liner(self, params: dict) -> str:
        """Generate a one-line description of this tool invocation"""
        namespace = params.get("namespace", "unknown-namespace")
        pod_name = params.get("pod_name", "unknown-pod")
        return f"Fetching logs for pod {pod_name} in namespace {namespace}"

    def get_example_config(self):
        return {}


class DummyLoggingToolset(BasePodLoggingToolset):
    def __init__(self, name, enabled: bool = True):
        super().__init__(name=name, description=name, tools=[])
        if enabled:
            self._status = ToolsetStatusEnum.ENABLED

    def fetch_pod_logs(self, params: FetchPodLogsParams) -> StructuredToolResult:
        return StructuredToolResult(status=ToolResultStatus.SUCCESS)

    def get_example_config(self):
        return {}


@pytest.mark.parametrize(
    "unfiltered_toolsets, expected_toolsets",
    [
        # non logging toolsets are not filtered
        ([DummyNonLoggingToolset()], [DummyNonLoggingToolset()]),
        # disabled toolsets are returned as-is
        (
            [DummyLoggingToolset(name="toolset1", enabled=False)],
            [DummyLoggingToolset(name="toolset1", enabled=False)],
        ),
        (
            [
                DummyLoggingToolset(name="toolset1"),
                DummyLoggingToolset(name="toolset2", enabled=False),
            ],
            [
                DummyLoggingToolset(name="toolset1"),
                DummyLoggingToolset(name="toolset2", enabled=False),
            ],
        ),
        # kubernetes/logs is never favoured
        (
            [DummyLoggingToolset(name="kubernetes/logs")],
            [DummyLoggingToolset(name="kubernetes/logs")],
        ),
        (
            [
                DummyLoggingToolset(name="kubernetes/logs"),
                DummyLoggingToolset(name="toolset1"),
            ],
            [DummyLoggingToolset(name="toolset1")],
        ),
        (
            [
                DummyLoggingToolset(name="kubernetes/logs"),
                DummyLoggingToolset(name="toolset1", enabled=False),
            ],
            [
                DummyLoggingToolset(name="kubernetes/logs"),
                DummyLoggingToolset(name="toolset1", enabled=False),
            ],
        ),
        # enabled toolset is favoured in alphabetical order
        (
            [
                DummyLoggingToolset(name="toolset1"),
                DummyLoggingToolset(name="toolset2"),
            ],
            [
                DummyLoggingToolset(name="toolset1"),
            ],
        ),
        (
            [
                DummyLoggingToolset(name="toolset2"),
                DummyLoggingToolset(name="toolset1"),
            ],
            [
                DummyLoggingToolset(name="toolset1"),
            ],
        ),
    ],
)
def test_filter_out_default_toolset(unfiltered_toolsets, expected_toolsets):
    filtered_toolsets = filter_out_default_logging_toolset(unfiltered_toolsets)

    assert len(filtered_toolsets) == len(expected_toolsets)

    expected_toolsets_names = [t.name for t in expected_toolsets].sort()
    filtered_toolsets_names = [t.name for t in filtered_toolsets].sort()

    assert expected_toolsets_names == filtered_toolsets_names
