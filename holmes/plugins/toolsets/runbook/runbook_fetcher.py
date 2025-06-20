import logging
from typing import Any, Dict

from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.runbooks import get_runbook_by_path


# TODO(mainred): currently we support fetch runbooks hosted internally, in the future we may want to support fetching
# runbooks from external sources as well.
class RunbookFetcher(Tool):
    toolset: "RunbookToolset"

    def __init__(self, toolset: "RunbookToolset"):
        super().__init__(
            name="fetch_runbook",
            description="Reads a runbook from the runbook catalog",
            parameters={
                "path": ToolParameter(
                    description="The path to the runbook",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,  # type: ignore
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        path: str = params["path"]

        runbook_path = get_runbook_by_path(path)
        try:
            with open(runbook_path, "r") as file:
                content = file.read()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=content,
                    params=params,
                )
        except Exception as e:
            err_msg = f"Failed to read runbook {runbook_path}: {str(e)}"
            logging.error(err_msg)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=err_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        path: str = params["path"]
        return f"fetched runbook {path}"


class RunbookToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="runbook",
            description="Fetch runbooks",
            icon_url="https://platform.robusta.dev/demos/runbook.svg",
            tools=[
                RunbookFetcher(self),
            ],
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/runbook.html",
            tags=[
                ToolsetTag.CORE,
            ],
            is_default=True,
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {}
