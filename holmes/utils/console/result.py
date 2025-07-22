from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from holmes.config import Config
from holmes.core.tool_calling_llm import LLMResult
from holmes.plugins.destinations import DestinationType
from holmes.plugins.interfaces import Issue


def handle_result(
    result: LLMResult,
    console: Console,
    destination: DestinationType,
    config: Config,
    issue: Issue,
    show_tool_output: bool,
    add_separator: bool,
):
    if destination == DestinationType.CLI:
        if show_tool_output and result.tool_calls:
            for tool_call in result.tool_calls:
                console.print("[bold magenta]Used Tool:[/bold magenta]", end="")
                # we need to print this separately with markup=False because it contains arbitrary text and we don't want console.print to interpret it
                console.print(
                    f"{tool_call.description}. Output=\n{tool_call.result}",
                    markup=False,
                )

        console.print("[bold green]AI:[/bold green]", end=" ")
        console.print(Markdown(result.result))  # type: ignore
        if add_separator:
            console.print(Rule())

    elif destination == DestinationType.SLACK:
        slack = config.create_slack_destination()
        slack.send_issue(issue, result)
