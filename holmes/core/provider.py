import logging

from openai import AzureOpenAI, OpenAI
from pydash.arrays import concat
from rich.console import Console

from holmes.config import BaseLLMConfig, LLMProviderType
from holmes.core.robusta_ai import RobustaAIToolCallingLLM, RobustaIssueInvestigator
from holmes.core.runbooks import RunbookManager
from holmes.core.tool_calling_llm import (
    BaseIssueInvestigator,
    BaseToolCallingLLM,
    OpenAIIssueInvestigator,
    OpenAIToolCallingLLM,
    YAMLToolExecutor,
)
from holmes.core.tools import ToolsetPattern, get_matching_toolsets
from holmes.plugins.destinations.slack import SlackDestination
from holmes.plugins.runbooks import load_builtin_runbooks, load_runbooks_from_file
from holmes.plugins.sources.jira import JiraSource
from holmes.plugins.sources.github import GitHubSource
from holmes.plugins.sources.opsgenie import OpsGenieSource
from holmes.plugins.sources.pagerduty import PagerDutySource
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource
from holmes.plugins.toolsets import load_builtin_toolsets, load_toolsets_from_file
from holmes.utils.auth import SessionManager


class LLMProviderFactory:
    def __init__(self, config: BaseLLMConfig, session_manager: SessionManager = None):
        self.config = config
        self.session_manager = session_manager

    def create_llm(self) -> OpenAI:
        if self.config.llm_provider == LLMProviderType.OPENAI:
            return OpenAI(
                api_key=(self.config.api_key.get_secret_value() if self.config.api_key else None),
            )
        elif self.config.llm_provider == LLMProviderType.AZURE:
            return AzureOpenAI(
                api_key=(self.config.api_key.get_secret_value() if self.config.api_key else None),
                azure_endpoint=self.config.azure_endpoint,
                api_version=self.config.azure_api_version,
            )
        else:
            raise ValueError(f"Unknown LLM type: {self.config.llm_provider}")

    def create_toolcalling_llm(self, console: Console, allowed_toolsets: ToolsetPattern) -> BaseToolCallingLLM:
        if self.config.llm_provider in [LLMProviderType.OPENAI, LLMProviderType.AZURE]:
            tool_executor = self._create_tool_executor(console, allowed_toolsets)
            return OpenAIToolCallingLLM(
                self.create_llm(),
                self.config.model,
                tool_executor,
                self.config.max_steps,
            )
        else:
            # TODO in the future
            return RobustaAIToolCallingLLM()

    def create_issue_investigator(self, console: Console, allowed_toolsets: ToolsetPattern) -> BaseIssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.config.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))
        runbook_manager = RunbookManager(all_runbooks)

        if self.config.llm_provider == LLMProviderType.ROBUSTA:
            return RobustaIssueInvestigator(self.config.url, self.session_manager, runbook_manager)
        else:
            tool_executor = self._create_tool_executor(console, allowed_toolsets)
            return OpenAIIssueInvestigator(
                self.create_llm(),
                self.config.model,
                tool_executor,
                runbook_manager,
                self.config.max_steps,
            )

    def create_jira_source(self) -> JiraSource:
        if self.config.jira_url is None:
            raise ValueError("--jira-url must be specified")
        if not (self.config.jira_url.startswith("http://") or self.config.jira_url.startswith("https://")):
            raise ValueError("--jira-url must start with http:// or https://")
        if self.config.jira_username is None:
            raise ValueError("--jira-username must be specified")
        if self.config.jira_api_key is None:
            raise ValueError("--jira-api-key must be specified")

        return JiraSource(
            url=self.config.jira_url,
            username=self.config.jira_username,
            api_key=self.config.jira_api_key.get_secret_value(),
            jql_query=self.config.jira_query,
        )

    def create_github_source(self) -> GitHubSource:
        if not (self.config.github_url.startswith("http://") or self.config.github_url.startswith("https://")):
            raise ValueError("--github-url must start with http:// or https://")
        if self.config.github_owner is None:
            raise ValueError("--github-owner must be specified")
        if self.config.github_repository is None:
            raise ValueError("--github-repository must be specified")
        if self.config.github_pat is None:
            raise ValueError("--github-pat must be specified")

        return GitHubSource(
            url=self.config.github_url,
            owner=self.config.github_owner,
            pat=self.config.github_pat.get_secret_value(),
            repository=self.config.github_repository,
            query=self.config.github_query,
        )

    def create_pagerduty_source(self) -> PagerDutySource:
        if self.config.pagerduty_api_key is None:
            raise ValueError("--pagerduty-api-key must be specified")

        return PagerDutySource(
            api_key=self.config.pagerduty_api_key.get_secret_value(),
            user_email=self.config.pagerduty_user_email,
            incident_key=self.config.pagerduty_incident_key,
        )

    def create_opsgenie_source(self) -> OpsGenieSource:
        if self.config.opsgenie_api_key is None:
            raise ValueError("--opsgenie-api-key must be specified")

        return OpsGenieSource(
            api_key=self.config.opsgenie_api_key.get_secret_value(),
            query=self.config.opsgenie_query,
            team_integration_key=(
                self.config.opsgenie_team_integration_key.get_secret_value()
                if self.config.opsgenie_team_integration_key
                else None
            ),
        )

    def create_alertmanager_source(self) -> AlertManagerSource:
        if self.config.alertmanager_url is None:
            raise ValueError("--alertmanager-url must be specified")
        if not (
            self.config.alertmanager_url.startswith("http://") or self.config.alertmanager_url.startswith("https://")
        ):
            raise ValueError("--alertmanager-url must start with http:// or https://")

        return AlertManagerSource(
            url=self.config.alertmanager_url,
            username=self.config.alertmanager_username,
            password=self.config.alertmanager_password,
            alertname=self.config.alertmanager_alertname,
        )

    def create_slack_destination(self):
        if self.config.slack_token is None:
            raise ValueError("--slack-token must be specified")
        if self.config.slack_channel is None:
            raise ValueError("--slack-channel must be specified")
        return SlackDestination(self.config.slack_token.get_secret_value(), self.config.slack_channel)

    def _create_tool_executor(self, console: Console, allowed_toolsets: ToolsetPattern) -> YAMLToolExecutor:
        all_toolsets = load_builtin_toolsets()
        for ts_path in self.config.custom_toolsets:
            all_toolsets.extend(load_toolsets_from_file(ts_path))

        if allowed_toolsets == "*":
            matching_toolsets = all_toolsets
        else:
            matching_toolsets = get_matching_toolsets(all_toolsets, allowed_toolsets.split(","))

        enabled_toolsets = [ts for ts in matching_toolsets if ts.is_enabled()]
        for ts in all_toolsets:
            if ts not in matching_toolsets:
                console.print(f"[yellow]Disabling toolset {ts.name} [/yellow] from {ts.get_path()}")
            elif ts not in enabled_toolsets:
                console.print(f"[yellow]Not loading toolset {ts.name}[/yellow] ({ts.get_disabled_reason()})")
                # console.print(f"[red]The following tools will be disabled: {[t.name for t in ts.tools]}[/red])")
            else:
                logging.debug(f"Loaded toolset {ts.name} from {ts.get_path()}")
                # console.print(f"[green]Loaded to  olset {ts.name}[/green] from {ts.get_path()}")

        enabled_tools = concat(*[ts.tools for ts in enabled_toolsets])
        logging.debug(f"Starting AI session with tools: {[t.name for t in enabled_tools]}")
        return YAMLToolExecutor(enabled_toolsets)
