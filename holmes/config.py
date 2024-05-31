import logging
import os.path
from enum import StrEnum
from typing import (Annotated, Any, ClassVar, List, Literal, Optional, Pattern,
                    TypeVar, Union)

from openai import AzureOpenAI, OpenAI
from pydantic import BaseModel, ConfigDict, Field, SecretStr, FilePath
from pydash.arrays import concat
from rich.console import Console

from holmes.core.runbooks import RunbookManager
from holmes.core.tool_calling_llm import (IssueInvestigator, ToolCallingLLM,
                                       YAMLToolExecutor)
from holmes.core.tools import Toolset, ToolsetPattern, get_matching_toolsets
from holmes.plugins.destinations.slack import SlackDestination
from holmes.plugins.runbooks import Runbook, load_builtin_runbooks, load_runbooks_from_file
from holmes.plugins.sources.jira.plugin import JiraSource
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource
from holmes.plugins.toolsets import Toolset, load_builtin_toolsets, load_toolsets_from_file
from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file


class LLMType(StrEnum):
    OPENAI = "openai"
    AZURE = "azure"


class ConfigFile(RobustaBaseConfig):
    llm: Optional[LLMType] = LLMType.OPENAI
    api_key: Optional[SecretStr] = (
        None  # if None, read from OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT env var
    )
    azure_endpoint: Optional[str] = (
        None  # if None, read from AZURE_OPENAI_ENDPOINT env var
    )
    azure_api_version: Optional[str] = "2024-02-01"
    model: Optional[str] = None
    max_steps: Optional[int] = 10

    alertmanager_url: Optional[str] = None
    alertmanager_username: Optional[str] = None
    alertmanager_password: Optional[str] = None

    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_api_key: Optional[SecretStr] = None
    jira_query: Optional[str] = ""

    slack_token: Optional[SecretStr] = None
    slack_channel: Optional[str] = None

    custom_runbooks: List[FilePath] = []
    custom_toolsets: List[FilePath] = []

    def create_llm(self) -> OpenAI:
        if self.llm == LLMType.OPENAI:
            return OpenAI(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
            )
        elif self.llm == LLMType.AZURE:
            return AzureOpenAI(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
                azure_endpoint=self.azure_endpoint,
                api_version=self.azure_api_version,
            )
        else:
            raise ValueError(f"Unknown LLM type: {self.llm}")

    def _create_tool_executor(
        self, console: Console, allowed_toolsets: ToolsetPattern
    ) -> YAMLToolExecutor:
        all_toolsets = load_builtin_toolsets()
        for ts_path in self.custom_toolsets:
            all_toolsets.extend(load_toolsets_from_file(ts_path))
            
        if allowed_toolsets == "*":
            matching_toolsets = all_toolsets
        else:
            matching_toolsets = get_matching_toolsets(
                all_toolsets, allowed_toolsets.split(",")
            )

        enabled_toolsets = [ts for ts in matching_toolsets if ts.is_enabled()]
        for ts in all_toolsets:
            if ts not in matching_toolsets:
                console.print(f"[yellow]Disabling toolset {ts.name} [/yellow] from {ts.get_path()}")
            elif ts not in enabled_toolsets:
                console.print(
                    f"[red]Error loading toolset {ts.name}[/red] from {ts.get_path()} ({ts.get_disabled_reason()})"
                )
                console.print(f"[red]The following tools will be disabled: {[t.name for t in ts.tools]}[/red])")
            else:
                logging.debug(f"Loaded toolset {ts.name} from {ts.get_path()}")
                #console.print(f"[green]Loaded toolset {ts.name}[/green] from {ts.get_path()}")

        enabled_tools = concat(*[ts.tools for ts in enabled_toolsets])
        logging.debug(
            f"Starting AI session with tools: {[t.name for t in enabled_tools]}"
        )
        return YAMLToolExecutor(enabled_toolsets)

    def create_toolcalling_llm(
        self, console: Console, allowed_toolsets: ToolsetPattern
    ) -> IssueInvestigator:
        tool_executor = self._create_tool_executor(console, allowed_toolsets)
        return ToolCallingLLM(
            self.create_llm(),
            self.model,
            tool_executor,
            self.max_steps,
        )

    def create_issue_investigator(
        self, console: Console, allowed_toolsets: ToolsetPattern
    ) -> IssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))
        
        runbook_manager = RunbookManager(all_runbooks)
        tool_executor = self._create_tool_executor(console, allowed_toolsets)
        return IssueInvestigator(
            self.create_llm(),
            self.model,
            tool_executor,
            runbook_manager,
            self.max_steps,
        )

    def create_jira_source(self) -> JiraSource:
        if self.jira_url is None:
            raise ValueError("--jira-url must be specified")
        if not (
            self.jira_url.startswith("http://") or self.jira_url.startswith("https://")
        ):
            raise ValueError("--jira-url must start with http:// or https://")
        if self.jira_username is None:
            raise ValueError("--jira-username must be specified")
        if self.jira_api_key is None:
            raise ValueError("--jira-api-key must be specified")

        return JiraSource(
            url=self.jira_url,
            username=self.jira_username,
            api_key=self.jira_api_key.get_secret_value(),
            jql_query=self.jira_query,
        )

    def create_alertmanager_source(self) -> AlertManagerSource:
        if self.alertmanager_url is None:
            raise ValueError("--alertmanager-url must be specified")
        if not (
            self.alertmanager_url.startswith("http://")
            or self.alertmanager_url.startswith("https://")
        ):
            raise ValueError("--alertmanager-url must start with http:// or https://")

        return AlertManagerSource(
            url=self.alertmanager_url,
            username=self.alertmanager_username,
            password=self.alertmanager_password,
        )

    def create_slack_destination(self):
        if self.slack_token is None:
            raise ValueError("--slack-token must be specified")
        if self.slack_channel is None:
            raise ValueError("--slack-channel must be specified")
        return SlackDestination(self.slack_token.get_secret_value(), self.slack_channel)

    @classmethod
    def load(cls, config_file: Optional[str], **kwargs) -> "ConfigFile":
        if config_file is not None:
            logging.debug("Loading config from file %s", config_file)
            config_from_file = load_model_from_file(cls, config_file)
        elif os.path.exists("config.yaml"):
            logging.debug("Loading config from default location config.yaml")
            config_from_file = load_model_from_file(cls, "config.yaml")
        else:
            logging.debug("No config file found, using cli settings only")
            config_from_file = None

        config_from_cli = cls(**kwargs)
        if config_from_file is None:
            return config_from_cli

        merged_config = config_from_file.dict()
        # remove Nones to avoid overriding config file with empty cli args
        cli_overrides = {
            k: v for k, v in config_from_cli.dict().items() if v is not None and v != []
        }
        merged_config.update(cli_overrides)
        return cls(**merged_config)
