import logging
import textwrap
from typing import Any, Dict, List, Optional

from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    StructuredToolResultStatus,
    Toolset,
    ToolsetTag,
)

from holmes.plugins.runbooks import get_runbook_by_path, DEFAULT_RUNBOOK_SEARCH_PATH
from holmes.plugins.toolsets.utils import toolset_name_for_one_liner


# TODO(mainred): currently we support fetch runbooks hosted internally, in the future we may want to support fetching
# runbooks from external sources as well.
class RunbookFetcher(Tool):
    toolset: "RunbookToolset"

    def __init__(self, toolset: "RunbookToolset"):
        super().__init__(
            name="fetch_runbook",
            description="Get runbook content by runbook link. Use this to get troubleshooting steps for incidents",
            parameters={
                # use link as a more generic term for runbook path, considering we may have external links in the future
                "link": ToolParameter(
                    description="The link to the runbook",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,  # type: ignore
        )

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        link: str = params["link"]

        search_paths = [DEFAULT_RUNBOOK_SEARCH_PATH]
        if self.toolset.config and "additional_search_paths" in self.toolset.config:
            search_paths.extend(self.toolset.config["additional_search_paths"])

        runbook_path = get_runbook_by_path(link, search_paths)

        if runbook_path is None:
            err_msg = (
                f"Runbook '{link}' not found in any of the search paths: {search_paths}"
            )
            logging.error(err_msg)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=err_msg,
                params=params,
            )

        # Read and return the runbook content
        try:
            with open(runbook_path, "r") as file:
                content = file.read()
                wrapped_content = textwrap.dedent(f"""\
                    <runbook>
{textwrap.indent(content, " " * 20)}
                    </runbook>
                    Note: the above are DIRECTIONS not ACTUAL RESULTS. You now need to follow the steps outlined in the runbook yourself USING TOOLS.
                    Anything that looks like an actual result in the above <runbook> is just an EXAMPLE.
                    Now follow those steps and report back what you find.
                    You must follow them by CALLING TOOLS YOURSELF.
                    If you are missing tools, follow your general instructions on how to enable them as present in your system prompt.

                    Assuming the above runbook is relevant, you MUST start your response (after calling tools to investigate) with:
                    "I found a runbook named [runbook name/description] and used it to troubleshoot:"

                    Then list each step with ✅ for completed steps and ❌ for steps you couldn't complete.

                    <example>
                        I found a runbook named **Troubleshooting Erlang Issues** and used it to troubleshoot:

                        1. ✅ *Check BEAM VM memory usage* - 87% allocated (3.2GB used of 4GB limit)
                        2. ✅ *Review GC logs* - 15 full GC cycles in last 30 minutes, avg pause time 2.3s
                        3. ✅ *Verify Erlang application logs* - `** exception error: out of memory in process <0.139.0> called by gen_server:handle_msg/6`
                        4. ❌ *Could not analyze process mailbox sizes* - Observer tool not enabled in container. Enable remote shell or observer_cli for process introspection.
                        5. ✅ *Check pod memory limits* - container limit 4Gi, requests 2Gi
                        6. ✅ *Verify BEAM startup arguments* - `+S 4:4 +P 1048576`, no memory instrumentation flags enabled
                        7. ❌ *Could not retrieve APM traces* - Datadog traces toolset is disabled. You can enable it by following https://holmesgpt.dev/data-sources/builtin-toolsets/datadog/
                        8. ❌ *Could not query Erlang metrics* - Prometheus integration is not connected. Enable it via https://holmesgpt.dev/data-sources/builtin-toolsets/prometheus/
                        9. ✅ *Examine recent deployments* - app version 2.1.3 deployed 4 hours ago, coincides with memory spike
                        10. ❌ *Could not check Stripe API status* - No toolset for Stripe integration exists. To monitor Stripe or similar third-party APIs, add a [custom toolset](https://holmesgpt.dev/data-sources/custom-toolsets/) or use a [remote MCP server](https://holmesgpt.dev/data-sources/remote-mcp-servers/)

                        **Root cause:** Memory leak in `gen_server` logic introduced in v2.1.3. BEAM VM hitting memory limit, causing out-of-memory crashes.

                        **Fix:** Roll back to v2.1.2 or increase memory limit to 6GB as a temporary workaround.
                    </example>
                """)
                return StructuredToolResult(
                    status=StructuredToolResultStatus.SUCCESS,
                    data=wrapped_content,
                    params=params,
                )
        except Exception as e:
            err_msg = f"Failed to read runbook {runbook_path}: {str(e)}"
            logging.error(err_msg)
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=err_msg,
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        path: str = params.get("link", "")
        return f"{toolset_name_for_one_liner(self.toolset.name)}: Fetch Runbook {path}"


class RunbookToolset(Toolset):
    def __init__(self, additional_search_paths: Optional[List[str]] = None):
        # Store additional search paths in config
        config = {}
        if additional_search_paths:
            config["additional_search_paths"] = additional_search_paths

        super().__init__(
            name="runbook",
            description="Fetch runbooks",
            icon_url="https://platform.robusta.dev/demos/runbook.svg",
            tools=[
                RunbookFetcher(self),
            ],
            docs_url="https://holmesgpt.dev/data-sources/",
            tags=[
                ToolsetTag.CORE,
            ],
            is_default=True,
            config=config,
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {}
