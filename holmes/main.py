import os
from holmes.utils.cert_utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")
if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY IMPORTS OR CODE ABOVE THIS LINE
# IMPORTING ABOVE MIGHT INITIALIZE AN HTTPS CLIENT THAT DOESN'T TRUST THE CUSTOM CERTIFICATE


import socket
import uuid
import logging
import re
import warnings
import json
from enum import Enum
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.rule import Rule
from holmes.utils.file_utils import write_json_file
from holmes.config import Config
from holmes.plugins.destinations import DestinationType
from holmes.plugins.interfaces import Issue
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.tool_calling_llm import LLMResult, ResourceInstructionDocument
from holmes.plugins.sources.opsgenie import OPSGENIE_TEAM_INTEGRATION_KEY_HELP
from holmes import get_version


app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
investigate_app = typer.Typer(
    add_completion=False,
    name="investigate",
    no_args_is_help=True,
    help="Investigate firing alerts or tickets",
)
app.add_typer(investigate_app, name="investigate")
generate_app = typer.Typer(
    add_completion=False,
    name="generate",
    no_args_is_help=True,
    help="Generate new integrations or test data",
)
app.add_typer(generate_app, name="generate")


class Verbosity(Enum):
    NORMAL = 0
    LOG_QUERIES = 1
    VERBOSE = 2
    VERY_VERBOSE = 3

def cli_flags_to_verbosity(verbose_flags: List[bool]) -> Verbosity:
    if verbose_flags is None or len(verbose_flags) == 0:
        return Verbosity.NORMAL
    elif len(verbose_flags) == 1:
        return Verbosity.LOG_QUERIES
    elif len(verbose_flags) == 2:
        return Verbosity.VERBOSE
    else:
        return Verbosity.VERY_VERBOSE

def init_logging(verbose_flags: List[bool] = None):
    verbosity = cli_flags_to_verbosity(verbose_flags)

    if verbosity == Verbosity.VERY_VERBOSE:
        logging.basicConfig(level=logging.DEBUG, format="%(message)s", handlers=[RichHandler(show_level=False, show_time=False)])
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(show_level=False, show_time=False)])

    if verbosity.value >= Verbosity.NORMAL.value:
        logging.info(f"verbosity is {verbosity}")

    if verbosity.value >= Verbosity.LOG_QUERIES.value:
        # TODO
        pass

    if verbosity.value >= Verbosity.VERBOSE.value:
        logging.getLogger().setLevel(logging.DEBUG)

    # disable INFO logs from OpenAI
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # disable INFO logs from LiteLLM
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    # disable INFO logs from AWS (relevant when using bedrock)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    # when running in --verbose mode we don't want to see DEBUG logs from these libraries
    logging.getLogger("openai._base_client").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("markdown_it").setLevel(logging.INFO)
    # Suppress UserWarnings from the slack_sdk module
    warnings.filterwarnings("ignore", category=UserWarning, module="slack_sdk.*")
    return Console()

# Common cli options
# The defaults for options that are also in the config file MUST be None or else the cli defaults will override settings in the config file
opt_api_key: Optional[str] = typer.Option(
    None,
    help="API key to use for the LLM (if not given, uses environment variables OPENAI_API_KEY or AZURE_API_KEY)",
)
opt_model: Optional[str] = typer.Option(
    None,
    help="Model to use for the LLM"
)
opt_config_file: Optional[Path] = typer.Option(
    None,
    "--config",
    help="Path to the config file. Defaults to ~/.holmes/config.yaml when it exists. Command line arguments take precedence over config file settings",
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
opt_verbose: Optional[List[bool]] = typer.Option(
    [],
    "--verbose",
    "-v",
    help="Verbose output. You can pass multiple times to increase the verbosity. e.g. -v or -vv or -vvv or -vvvv",
)
opt_echo_request: bool = typer.Option(
    True,
    "--echo/--no-echo",
    help="Echo back the question provided to HolmesGPT in the output",
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
opt_json_output_file: Optional[str] = typer.Option(
    None,
    "--json-output-file",
    help="Save the complete output in json format in to a file",
    envvar="HOLMES_JSON_OUTPUT_FILE",
)

opt_post_processing_prompt: Optional[str] = typer.Option(
    None,
    "--post-processing-prompt",
    help="Adds a prompt for post processing. (Preferable for chatty ai models)",
    envvar="HOLMES_POST_PROCESSING_PROMPT",
)

opt_documents: Optional[str] = typer.Option(
    None,
    "--documents",
    help="Additional documents to provide the LLM (typically URLs to runbooks)",
)

# Common help texts
system_prompt_help = "Advanced. System prompt for LLM. Values starting with builtin:// are loaded from holmes/plugins/prompts, values starting with file:// are loaded from the given path, other values are interpreted as a prompt string"

def parse_documents(documents:Optional[str]) -> List[ResourceInstructionDocument]:
    resource_documents = []

    if documents is not None:
        data = json.loads(documents)
        for item in data:
            resource_document = ResourceInstructionDocument(**item)
            resource_documents.append(resource_document)

    return resource_documents

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
                console.print(f"[bold magenta]Used Tool:[/bold magenta]", end="")
                # we need to print this separately with markup=False because it contains arbitrary text and we don't want console.print to interpret it
                console.print(f"{tool_call.description}. Output=\n{tool_call.result}", markup=False)

        console.print(f"[bold green]AI:[/bold green]", end=" ")
        console.print(Markdown(result.result))
        if add_separator:
            console.print(Rule())

    elif destination == DestinationType.SLACK:
        slack = config.create_slack_destination()
        slack.send_issue(issue, result)


# TODO: add interactive interpreter mode
# TODO: add streaming output
@app.command()
def ask(
    prompt: str = typer.Argument(help="What to ask the LLM (user prompt)"),
    # common options
    api_key: Optional[str] = opt_api_key,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[List[bool]] = opt_verbose,
    # semi-common options
    destination: Optional[DestinationType] = opt_destination,
    slack_token: Optional[str] = opt_slack_token,
    slack_channel: Optional[str] = opt_slack_channel,

    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_ask.jinja2", help=system_prompt_help
    ),
    show_tool_output: bool = typer.Option(
        False,
        "--show-tool-output",
        help="Advanced. Show the output of each tool that was called",
    ),
    include_file: Optional[List[Path]] = typer.Option(
        [],
        "--file",
        "-f",
        help="File to append to prompt (can specify -f multiple times to add multiple files)",
    ),
    json_output_file: Optional[str] = opt_json_output_file,
    echo_request: bool = opt_echo_request,
    post_processing_prompt: Optional[str] = opt_post_processing_prompt
):
    """
    Ask any question and answer using available tools
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        model=model,
        max_steps=max_steps,
        custom_toolsets=custom_toolsets,
        slack_token=slack_token,
        slack_channel=slack_channel,
    )
    system_prompt = load_and_render_prompt(system_prompt)
    ai = config.create_toolcalling_llm(console, allowed_toolsets)
    if echo_request:
        console.print("[bold yellow]User:[/bold yellow] " + prompt)
    for path in include_file:
        f = path.open("r")
        prompt += f"\n\nAttached file '{path.absolute()}':\n{f.read()}"
        console.print(f"[bold yellow]Loading file {path}[/bold yellow]")

    response = ai.prompt_call(system_prompt, prompt, post_processing_prompt)

    if json_output_file:
        write_json_file(json_output_file, response.model_dump())

    issue = Issue(
        id=str(uuid.uuid4()),
        name=prompt,
        source_type="holmes-ask",
        raw={"prompt": prompt},
        source_instance_id=socket.gethostname(),
    )
    handle_result(response, console, destination, config, issue, show_tool_output, False)


@investigate_app.command()
def alertmanager(
    alertmanager_url: Optional[str] = typer.Option(None, help="AlertManager url"),
    alertmanager_alertname: Optional[str] = typer.Option(
        None,
        help="Investigate all alerts with this name (can be regex that matches multiple alerts). If not given, defaults to all firing alerts",
    ),
    alertmanager_label: Optional[List[str]] = typer.Option(
        [],
        help="For filtering alerts with a specific label. Must be of format key=value. If --alertmanager-label is passed multiple times, alerts must match ALL labels"
    ),
    alertmanager_username: Optional[str] = typer.Option(
        None, help="Username to use for basic auth"
    ),
    alertmanager_password: Optional[str] = typer.Option(
        None, help="Password to use for basic auth"
    ),
    alertmanager_file: Optional[Path] = typer.Option(
        None, help="Load alertmanager alerts from a file (used by the test framework)"
    ),
    alertmanager_limit: Optional[int] = typer.Option(
        None,
        "-n",
        help="Limit the number of alerts to process"
    ),
    # common options
    api_key: Optional[str] = opt_api_key,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[List[bool]] = opt_verbose,
    # advanced options for this command
    destination: Optional[DestinationType] = opt_destination,
    slack_token: Optional[str] = opt_slack_token,
    slack_channel: Optional[str] = opt_slack_channel,
    json_output_file: Optional[str] = opt_json_output_file,
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
    post_processing_prompt: Optional[str] = opt_post_processing_prompt
):
    """
    Investigate a Prometheus/Alertmanager alert
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        model=model,
        max_steps=max_steps,
        alertmanager_url=alertmanager_url,
        alertmanager_username=alertmanager_username,
        alertmanager_password=alertmanager_password,
        alertmanager_alertname=alertmanager_alertname,
        alertmanager_label=alertmanager_label,
        alertmanager_file=alertmanager_file,
        slack_token=slack_token,
        slack_channel=slack_channel,
        custom_toolsets=custom_toolsets,
        custom_runbooks=custom_runbooks
    )

    ai = config.create_issue_investigator(console, allowed_toolsets)

    source = config.create_alertmanager_source()

    try:
        issues = source.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from alertmanager", exc_info=e)
        return

    if alertmanager_limit is not None:
        console.print(f"[bold yellow]Limiting to {alertmanager_limit}/{len(issues)} issues.[/bold yellow]")
        issues = issues[:alertmanager_limit]

    if alertmanager_alertname is not None:
        console.print(
            f"[bold yellow]Analyzing {len(issues)} issues matching filter.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
        )
    else:
        console.print(
            f"[bold yellow]Analyzing all {len(issues)} issues. (Use --alertmanager-alertname to filter.)[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
        )
    results = []
    for i, issue in enumerate(issues):
        console.print(
            f"[bold yellow]Analyzing issue {i+1}/{len(issues)}: {issue.name}...[/bold yellow]"
        )
        result = ai.investigate(
            issue=issue,
            prompt=system_prompt,
            console=console,
            instructions=None,
            post_processing_prompt=post_processing_prompt)
        results.append({"issue": issue.model_dump(), "result": result.model_dump()})
        handle_result(result, console, destination, config, issue, False, True)

    if json_output_file:
        write_json_file(json_output_file, results)


@generate_app.command("alertmanager-tests")
def generate_alertmanager_tests(
    alertmanager_url: Optional[str] = typer.Option(None, help="AlertManager url"),
    alertmanager_username: Optional[str] = typer.Option(
        None, help="Username to use for basic auth"
    ),
    alertmanager_password: Optional[str] = typer.Option(
        None, help="Password to use for basic auth"
    ),
    output: Optional[Path] = typer.Option(
        None, help="Path to dump alertmanager alerts as json (if not given, output curl commands instead)"
    ),
    config_file: Optional[str] = opt_config_file,
    verbose: Optional[List[bool]] = opt_verbose,
):
    """
    Connect to alertmanager and dump all alerts as either a json file or curl commands to simulate the alert (depending on --output flag)
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        alertmanager_url=alertmanager_url,
        alertmanager_username=alertmanager_username,
        alertmanager_password=alertmanager_password,
    )

    source = config.create_alertmanager_source()
    if output is None:
        source.output_curl_commands(console)
    else:
        source.dump_raw_alerts_to_file(output)


@investigate_app.command()
def jira(
    jira_url: Optional[str] = typer.Option(
        None,
        help="Jira url - e.g. https://your-company.atlassian.net",
        envvar="JIRA_URL"
    ),
    jira_username: Optional[str] = typer.Option(
        None,
        help="The email address with which you log into Jira",
        envvar="JIRA_USERNAME"
    ),
    jira_api_key: str = typer.Option(
        None,
        envvar="JIRA_API_KEY",
    ),
    jira_query: Optional[str] = typer.Option(
        None,
        help="Investigate tickets matching a JQL query (e.g. 'project=DEFAULT_PROJECT')",
    ),
    update: Optional[bool] = typer.Option(
        False, help="Update Jira with AI results"
    ),
    # common options
    api_key: Optional[str] = opt_api_key,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[List[bool]] = opt_verbose,
    json_output_file: Optional[str] = opt_json_output_file,
    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
    post_processing_prompt: Optional[str] = opt_post_processing_prompt
):
    """
    Investigate a Jira ticket
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        model=model,
        max_steps=max_steps,
        jira_url=jira_url,
        jira_username=jira_username,
        jira_api_key=jira_api_key,
        jira_query=jira_query,
        custom_toolsets=custom_toolsets,
        custom_runbooks=custom_runbooks
    )
    ai = config.create_issue_investigator(console, allowed_toolsets)
    source = config.create_jira_source()
    try:
        issues = source.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from Jira", exc_info=e)
        return

    console.print(
        f"[bold yellow]Analyzing {len(issues)} Jira tickets.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
    )

    results = []
    for i, issue in enumerate(issues):
        console.print(
            f"[bold yellow]Analyzing Jira ticket {i+1}/{len(issues)}: {issue.name}...[/bold yellow]"
        )
        result = ai.investigate(
            issue=issue,
            prompt=system_prompt,
            console=console,
            instructions=None,
            post_processing_prompt=post_processing_prompt)

        console.print(Rule())
        console.print(f"[bold green]AI analysis of {issue.url}[/bold green]")
        console.print(Markdown(result.result.replace("\n", "\n\n")), style="bold green")
        console.print(Rule())
        if update:
            source.write_back_result(issue.id, result)
            console.print(f"[bold]Updated ticket {issue.url}.[/bold]")
        else:
            console.print(
                f"[bold]Not updating ticket {issue.url}. Use the --update option to do so.[/bold]"
            )

        results.append({"issue": issue.model_dump(), "result": result.model_dump()})

    if json_output_file:
        write_json_file(json_output_file, results)


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
    update: Optional[bool] = typer.Option(
        False, help="Update GitHub with AI results"
    ),
    github_query: Optional[str] = typer.Option(
        "is:issue is:open",
        help="Investigate tickets matching a GitHub query (e.g. 'is:issue is:open')",
    ),
    # common options
    api_key: Optional[str] = opt_api_key,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[List[bool]] = opt_verbose,
    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
    post_processing_prompt: Optional[str] = opt_post_processing_prompt
):
    """
    Investigate a GitHub issue
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
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
    ai = config.create_issue_investigator(console, allowed_toolsets)
    source = config.create_github_source()
    try:
        issues = source.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from GitHub", exc_info=e)
        return

    console.print(
        f"[bold yellow]Analyzing {len(issues)} GitHub Issues.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
    )
    for i, issue in enumerate(issues):
        console.print(f"[bold yellow]Analyzing GitHub issue {i+1}/{len(issues)}: {issue.name}...[/bold yellow]")

        result = ai.investigate(
            issue=issue,
            prompt=system_prompt,
            console=console,
            instructions=None,
            post_processing_prompt=post_processing_prompt)

        console.print(Rule())
        console.print(f"[bold green]AI analysis of {issue.url}[/bold green]")
        console.print(Markdown(result.result.replace(
            "\n", "\n\n")), style="bold green")
        console.print(Rule())
        if update:
            source.write_back_result(issue.id, result)
            console.print(f"[bold]Updated ticket {issue.url}.[/bold]")
        else:
            console.print(
                f"[bold]Not updating issue {issue.url}. Use the --update option to do so.[/bold]"
            )

@investigate_app.command()
def pagerduty(
    pagerduty_api_key: str = typer.Option(
        None, help="The PagerDuty API key.  This can be found in the PagerDuty UI under Integrations > API Access Keys."
    ),
    pagerduty_user_email: Optional[str] = typer.Option(
        None, help="When --update is set, which user will be listed as the user who updated the ticket. (Must be the email of a valid user in your PagerDuty account.)"
    ),
    pagerduty_incident_key: Optional[str] = typer.Option(
        None, help="If provided, only analyze a single PagerDuty incident matching this key"
    ),
    update: Optional[bool] = typer.Option(
        False, help="Update PagerDuty with AI results"
    ),
    # common options
    api_key: Optional[str] = opt_api_key,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[List[bool]] = opt_verbose,
    json_output_file: Optional[str] = opt_json_output_file,
    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
    post_processing_prompt: Optional[str] = opt_post_processing_prompt
):
    """
    Investigate a PagerDuty incident
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        model=model,
        max_steps=max_steps,
        pagerduty_api_key=pagerduty_api_key,
        pagerduty_user_email=pagerduty_user_email,
        pagerduty_incident_key=pagerduty_incident_key,
        custom_toolsets=custom_toolsets,
        custom_runbooks=custom_runbooks
    )
    ai = config.create_issue_investigator(console, allowed_toolsets)
    source = config.create_pagerduty_source()
    try:
        issues = source.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from PagerDuty", exc_info=e)
        return

    console.print(
        f"[bold yellow]Analyzing {len(issues)} PagerDuty incidents.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
    )

    results = []
    for i, issue in enumerate(issues):
        console.print(f"[bold yellow]Analyzing PagerDuty incident {i+1}/{len(issues)}: {issue.name}...[/bold yellow]")

        result = ai.investigate(
            issue=issue,
            prompt=system_prompt,
            console=console,
            instructions=None,
            post_processing_prompt=post_processing_prompt)

        console.print(Rule())
        console.print(f"[bold green]AI analysis of {issue.url}[/bold green]")
        console.print(Markdown(result.result.replace(
            "\n", "\n\n")), style="bold green")
        console.print(Rule())
        if update:
            source.write_back_result(issue.id, result)
            console.print(f"[bold]Updated alert {issue.url}.[/bold]")
        else:
            console.print(
                f"[bold]Not updating alert {issue.url}. Use the --update option to do so.[/bold]"
            )
        results.append({"issue": issue.model_dump(), "result": result.model_dump()})

    if json_output_file:
        write_json_file(json_output_file, results)

@investigate_app.command()
def opsgenie(
    opsgenie_api_key: str = typer.Option(
        None, help="The OpsGenie API key"
    ),
    opsgenie_team_integration_key: str = typer.Option(
        None, help=OPSGENIE_TEAM_INTEGRATION_KEY_HELP
    ),
    opsgenie_query: Optional[str] = typer.Option(
        None, help="E.g. 'message: Foo' (see https://support.atlassian.com/opsgenie/docs/search-queries-for-alerts/)"
    ),
    update: Optional[bool] = typer.Option(
        False, help="Update OpsGenie with AI results"
    ),
    # common options
    api_key: Optional[str] = opt_api_key,
    model: Optional[str] = opt_model,
    config_file: Optional[str] = opt_config_file,
    custom_toolsets: Optional[List[Path]] = opt_custom_toolsets,
    allowed_toolsets: Optional[str] = opt_allowed_toolsets,
    custom_runbooks: Optional[List[Path]] = opt_custom_runbooks,
    max_steps: Optional[int] = opt_max_steps,
    verbose: Optional[List[bool]] = opt_verbose,
    # advanced options for this command
    system_prompt: Optional[str] = typer.Option(
        "builtin://generic_investigation.jinja2", help=system_prompt_help
    ),
    post_processing_prompt: Optional[str] = opt_post_processing_prompt,
    documents: Optional[str] = opt_documents
):
    """
    Investigate an OpsGenie alert
    """
    console = init_logging(verbose)
    config = Config.load_from_file(
        config_file,
        api_key=api_key,
        model=model,
        max_steps=max_steps,
        opsgenie_api_key=opsgenie_api_key,
        opsgenie_team_integration_key=opsgenie_team_integration_key,
        opsgenie_query=opsgenie_query,
        custom_toolsets=custom_toolsets,
        custom_runbooks=custom_runbooks
    )
    ai = config.create_issue_investigator(console, allowed_toolsets)
    source = config.create_opsgenie_source()
    try:
        issues = source.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from OpsGenie", exc_info=e)
        return

    console.print(
        f"[bold yellow]Analyzing {len(issues)} OpsGenie alerts.[/bold yellow] [red]Press Ctrl+C to stop.[/red]"
    )
    for i, issue in enumerate(issues):
        console.print(f"[bold yellow]Analyzing OpsGenie alert {i+1}/{len(issues)}: {issue.name}...[/bold yellow]")
        result = ai.investigate(
            issue=issue,
            prompt=system_prompt,
            console=console,
            instructions=None,
            post_processing_prompt=post_processing_prompt)

        console.print(Rule())
        console.print(f"[bold green]AI analysis of {issue.url}[/bold green]")
        console.print(Markdown(result.result.replace(
            "\n", "\n\n")), style="bold green")
        console.print(Rule())
        if update:
            source.write_back_result(issue.id, result)
            console.print(f"[bold]Updated alert {issue.url}.[/bold]")
        else:
            console.print(
                f"[bold]Not updating alert {issue.url}. Use the --update option to do so.[/bold]"
            )


@app.command()
def version() -> None:
    typer.echo(get_version())


def run():
    app()


if __name__ == "__main__":
    run()
