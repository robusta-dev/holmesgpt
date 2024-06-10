# from holmes.ssh_utils import add_custom_certificate
# add_custom_certificate("cert goes here as a string (not path to the cert rather the cert itself)")

import logging
import re
import warnings
from pathlib import Path
from typing import List, Optional, Pattern

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.rule import Rule

from holmes.config import Config, LLMType
from holmes.plugins.destinations import DestinationType
from holmes.plugins.prompts import load_prompt
from holmes import get_version

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
investigate_app = typer.Typer(
    add_completion=False,
    name="investigate",
    no_args_is_help=True,
    help="Investigate firing alerts or tickets",
)
app.add_typer(investigate_app, name="investigate")

def init_logging(verbose = False):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s", handlers=[RichHandler(show_level=False, show_time=False)])
    # disable INFO logs from OpenAI
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # when running in --verbose mode we don't want to see DEBUG logs from these libraries
    logging.getLogger("openai._base_client").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("markdown_it").setLevel(logging.INFO)
    # Suppress UserWarnings from the slack_sdk module
    warnings.filterwarnings("ignore", category=UserWarning, module="slack_sdk.*")
    return Console()

# Common cli options
opt_llm: Optional[LLMType] = typer.Option(
    LLMType.OPENAI,
    help="Which LLM to use ('openai' or 'azure')",
)
opt_api_key: Optional[str] = typer.Option(
    None,
    help="API key to use for the LLM (if not given, uses environment variables OPENAI_API_KEY or AZURE_OPENAI_API_KEY)",
)
opt_azure_endpoint: Optional[str] = typer.Option(
    None,
    help="Endpoint to use for Azure AI (if not given, uses environment variable AZURE_OPENAI_ENDPOINT)",
)
opt_model: Optional[str] = typer.Option("gpt-4o", help="Model to use for the LLM")
opt_config_file: Optional[Path] = typer.Option(
    None,
    "--config",
    help="Path to the config file. Defaults to config.yaml when it exists. Command line arguments take precedence over config file settings",
)
opt_custom_toolsets: Optional[List[Path]] = typer.Option(
    [],
    "--custom-toolsets",
    "-t",
    help="Path to a custom toolsets (can specify -t multiple times to add multiple toolsets)",
)
opt_allowed_toolsets: Optional[str] = typer.Option(
    "*",
    help="Toolsets the LLM is allowed to use to investigate (default is * for all available toolsets, can be comma separated list of toolset names)",
)
opt_custom_runbooks: Optional[List[Path]] = typer.Option(
    [],
    "--custom-runbooks",
    "-r",
    help="Path to a custom runbooks (can specify -r multiple times to add multiple runbooks)",
)
opt_max_steps: Optional[int] = typer.Option(
    10,
    "--max-steps",
    help="Advanced. Maximum number of steps the LLM can take to investigate the issue",
)
opt_verbose: Optional[bool] = typer.Option(
    False,
    "--verbose",
    "-v",
    help="Verbose output",
)
opt_destination: Optional[DestinationType] = typer.Option(
    DestinationType.CLI,
    "--destination",
    help="Destination for the results of the investigation (defaults to STDOUT)",
)
opt_slack_token: Optional[str] = typer.Option(
    None,
    "--slack-token",
    help="Slack API key if --destination=slack (experimental). Can generate with `pip install robusta-cli && robusta integrations slack`",
)
opt_slack_channel: Optional[str] = typer.Option(
    None,
    "--slack-channel",
    help="Slack channel if --destination=slack (experimental). E.g. #devops",
)

# Common help texts
system_prompt_help = "Advanced. System prompt for LLM. Values starting with builtin:// are loaded from holmes/plugins/prompts, values starting with file:// are loaded from the given path, other values are interpreted as a prompt string"


# TODO: add interactive interpreter mode
# TODO: add streaming output
@app.command()
def ask(
    prompt: str = typer.Argument(help="What to ask the LLM (user prompt)"),
    # common options
    llm=opt_llm,
    api_key: Optional[str] = opt_api_key,
    azure_endpoint: Optional[str] = opt_azure_endpoint,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[bool] = opt_verbose,
    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_ask.jinja2", help=system_prompt_help
    ),
    show_tool_output: bool = typer.Option(
        False,
        "--show-tool-output",
        help="Advanced. Show the output of each tool that was called",
    ),
):
    """
    Ask any question and answer using available tools
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        llm=llm,
        azure_endpoint=azure_endpoint,
        model=model,
        max_steps=max_steps,
        custom_toolsets=custom_toolsets,
    )
    system_prompt = load_prompt(system_prompt)
    ai = config.create_toolcalling_llm(console, allowed_toolsets)
    console.print("[bold yellow]User:[/bold yellow] " + prompt)
    response = ai.call(system_prompt, prompt)
    text_result = Markdown(response.result)
    if show_tool_output and response.tool_calls:
        for tool_call in response.tool_calls:
            console.print(f"[bold magenta]Used Tool:[/bold magenta]", end="")
            # we need to print this separately with markup=False because it contains arbitrary text and we don't want console.print to interpret it
            console.print(f"{tool_call.description}. Output=\n{tool_call.result}", markup=False)
    console.print(f"[bold green]AI:[/bold green]", end=" ")
    console.print(text_result, soft_wrap=True)


@investigate_app.command()
def alertmanager(
    alertmanager_url: Optional[str] = typer.Option(None, help="AlertManager url"),
    alertname: Optional[str] = typer.Option(
        None,
        help="Investigate all alerts with this name (can be regex that matches multiple alerts). If not given, defaults to all firing alerts",
    ),
    alertmanager_username: Optional[str] = typer.Option(
        None, help="Username to use for basic auth"
    ),
    alertmanager_password: Optional[str] = typer.Option(
        None, help="Password to use for basic auth"
    ),
    # common options
    llm: Optional[LLMType] = opt_llm,
    api_key: Optional[str] = opt_api_key,
    azure_endpoint: Optional[str] = opt_azure_endpoint,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[bool] = opt_verbose,
    # advanced options for this command
    destination: Optional[DestinationType] = opt_destination,
    slack_token: Optional[str] = opt_slack_token,
    slack_channel: Optional[str] = opt_slack_channel,
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
):
    """
    Investigate a Prometheus/Alertmanager alert
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        llm=llm,
        azure_endpoint=azure_endpoint,
        model=model,
        max_steps=max_steps,
        alertmanager_url=alertmanager_url,
        alertmanager_username=alertmanager_username,
        alertmanager_password=alertmanager_password,
        slack_token=slack_token,
        slack_channel=slack_channel,
        custom_toolsets=custom_toolsets,
        custom_runbooks=custom_runbooks
    )
    
    if alertname:
        alertname = re.compile(alertname)

    system_prompt = load_prompt(system_prompt)
    ai = config.create_issue_investigator(console, allowed_toolsets)

    source = config.create_alertmanager_source()

    if destination == DestinationType.SLACK:
        slack = config.create_slack_destination()

    try:
        issues = source.fetch_issues(alertname)
    except Exception as e:
        logging.error(f"Failed to fetch issues from alertmanager: {e}")
        return

    if alertname is not None:
        console.print(
            f"[bold yellow]Analyzing {len(issues)} issues matching filter.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
        )
    else:
        console.print(
            f"[bold yellow]Analyzing all {len(issues)} issues. (Use --alertname to filter.)[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
        )
    for i, issue in enumerate(issues):
        console.print(
            f"[bold yellow]Analyzing issue {i+1}/{len(issues)}: {issue.name}...[/bold yellow]"
        )
        result = ai.investigate(issue, system_prompt, console)

        if destination == DestinationType.CLI:
            console.print(Rule())
            console.print("[bold green]AI:[/bold green]", end=" ")
            console.print(
                Markdown(result.result.replace("\n", "\n\n")), style="bold green"
            )
            console.print(Rule())
        elif destination == DestinationType.SLACK:
            slack.send_issue(issue, result)


@investigate_app.command()
def jira(
    jira_url: Optional[str] = typer.Option(
        None, help="Jira url - e.g. https://your-company.atlassian.net"
    ),
    jira_username: Optional[str] = typer.Option(
        None, help="The email address with which you log into Jira"
    ),
    jira_api_key: str = typer.Option(
        None,
    ),
    jira_query: Optional[str] = typer.Option(
        None,
        help="Investigate tickets matching a JQL query (e.g. 'project=DEFAULT_PROJECT')",
    ),
    update_ticket: Optional[bool] = typer.Option(
        False, help="Update tickets with AI results"
    ),
    # common options
    llm: Optional[LLMType] = opt_llm,
    api_key: Optional[str] = opt_api_key,
    azure_endpoint: Optional[str] = opt_azure_endpoint,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[bool] = opt_verbose,
    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
):
    """
    Investigate a Jira ticket
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        llm=llm,
        azure_endpoint=azure_endpoint,
        model=model,
        max_steps=max_steps,
        jira_url=jira_url,
        jira_username=jira_username,
        jira_api_key=jira_api_key,
        jira_query=jira_query,
        custom_toolsets=custom_toolsets,
        custom_runbooks=custom_runbooks
    )

    system_prompt = load_prompt(system_prompt)
    ai = config.create_issue_investigator(console, allowed_toolsets)
    source = config.create_jira_source()
    try:
        # TODO: allow passing issue ID
        issues = source.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from Jira: {e}")
        return

    console.print(
        f"[bold yellow]Analyzing {len(issues)} Jira tickets.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
    )
    for i, issue in enumerate(issues):
        console.print(
            f"[bold yellow]Analyzing Jira ticket {i+1}/{len(issues)}: {issue.name}...[/bold yellow]"
        )
        result = ai.investigate(issue, system_prompt, console)

        console.print(Rule())
        console.print(f"[bold green]AI analysis of {issue.url}[/bold green]")
        console.print(Markdown(result.result.replace("\n", "\n\n")), style="bold green")
        console.print(Rule())
        if update_ticket:
            source.write_back_result(issue.id, result)
            console.print(f"[bold]Updated ticket {issue.url}.[/bold]")
        else:
            console.print(
                f"[bold]Not updating ticket {issue.url}. Use the --update-ticket option to do so.[/bold]"
            )


@investigate_app.command()
def github(
    github_url: str = typer.Option(
        "https://api.github.com", help="The GitHub api base url (e.g: https://api.github.com)"
    ),
    github_owner: Optional[str] = typer.Option(
        None, help="The GitHub repository Owner, eg: if the repository url is https://github.com/robusta-dev/holmesgpt, the owner is robusta-dev"
    ),
    github_pat: str = typer.Option(
        None,
    ),
    github_repository: Optional[str] = typer.Option(
        None,
        help="The GitHub repository name, eg: if the repository url is https://github.com/robusta-dev/holmesgpt, the repository name is holmesgpt",
    ),
    update_issue: Optional[bool] = typer.Option(
        False, help="Update issues with AI results"
    ),
    github_query: Optional[str] = typer.Option(
        "is:issue is:open",
        help="Investigate tickets matching a GitHub query (e.g. 'is:issue is:open')",
    ),
    # common options
    llm: Optional[LLMType] = opt_llm,
    api_key: Optional[str] = opt_api_key,
    azure_endpoint: Optional[str] = opt_azure_endpoint,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[bool] = opt_verbose,
    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
):
    """
    Investigate a GitHub issue
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        llm=llm,
        azure_endpoint=azure_endpoint,
        model=model,
        max_steps=max_steps,
        github_url=github_url,
        github_owner=github_owner,
        github_pat=github_pat,
        github_repository=github_repository,
        github_query=github_query,
        custom_toolsets=custom_toolsets,
        custom_runbooks=custom_runbooks
    )

    system_prompt = load_prompt(system_prompt)
    ai = config.create_issue_investigator(console, allowed_toolsets)
    source = config.create_github_source()
    try:
        issues = source.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from GitHub: {e}")
        return

    console.print(
        f"[bold yellow]Analyzing {len(issues)} GitHub Issues.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
    )
    for i, issue in enumerate(issues):
        console.print(f"[bold yellow]Analyzing GitHub issue {i+1}/{len(issues)}: {issue.name}...[/bold yellow]")
        result = ai.investigate(issue, system_prompt, console)

        console.print(Rule())
        console.print(f"[bold green]AI analysis of {issue.url}[/bold green]")
        console.print(Markdown(result.result.replace(
            "\n", "\n\n")), style="bold green")
        console.print(Rule())
        if update_issue:
            source.write_back_result(issue.id, result)
            console.print(f"[bold]Updated ticket {issue.url}.[/bold]")
        else:
            console.print(
                f"[bold]Not updating issue {issue.url}. Use the --update-issue option to do so.[/bold]"
            )

@app.command()
def version() -> None:
    typer.echo(get_version())

if __name__ == "__main__":
    app()
