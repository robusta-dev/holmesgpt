from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.runbook.runbook_fetcher import (
    RunbookFetcher,
    RunbookToolset,
)


def test_RunbookFetcher():
    runbook_fetch_tool = RunbookFetcher(RunbookToolset())
    result = runbook_fetch_tool._invoke({"link": "wrong_runbook_path"})
    assert result.status == ToolResultStatus.ERROR
    assert result.error is not None

    result = runbook_fetch_tool._invoke(
        {"link": "networking/dns_troubleshooting_instructions.md"}
    )

    assert result.status == ToolResultStatus.SUCCESS
    assert result.error is None
    assert result.data is not None
    assert (
        runbook_fetch_tool.get_parameterized_one_liner(
            {"link": "networking/dns_troubleshooting_instructions.md"}
        )
        == "Runbook: Fetch Runbook networking/dns_troubleshooting_instructions.md"
    )
