import logging
import os
import os.path
from strenum import StrEnum
from typing import Annotated, Any, Dict, List, Optional, get_args, get_type_hints

from openai import AzureOpenAI, OpenAI
from pydantic import FilePath, SecretStr
from pydash.arrays import concat
from rich.console import Console

from holmes.core.runbooks import RunbookManager
from holmes.core.tool_calling_llm import (IssueInvestigator, ToolCallingLLM,
                                          YAMLToolExecutor)
from holmes.core.tools import ToolsetPattern, get_matching_toolsets
from holmes.plugins.destinations.slack import SlackDestination
from holmes.plugins.runbooks import (load_builtin_runbooks,
                                     load_runbooks_from_file)
from holmes.plugins.sources.github import GitHubSource
from holmes.plugins.sources.jira import JiraSource
from holmes.plugins.sources.opsgenie import OpsGenieSource
from holmes.plugins.sources.pagerduty import PagerDutySource
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource
from holmes.plugins.toolsets import load_builtin_toolsets, load_toolsets_from_file
from holmes.utils.pydantic_utils import BaseConfig, EnvVarName, load_model_from_file


class LLMProviderType(StrEnum):
    OPENAI = "openai"
    AZURE = "azure"
    ROBUSTA = "robusta_ai"


class BaseLLMConfig(BaseConfig):
    llm: LLMProviderType = LLMProviderType.OPENAI

    # FIXME: the following settings do not belong here. They define the
    # configuration of specific actions, and not of the LLM provider.
    alertmanager_url: Optional[str] = None
    alertmanager_username: Optional[str] = None
    alertmanager_password: Optional[str] = None
    alertmanager_alertname: Optional[str] = None

    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_api_key: Optional[SecretStr] = None
    jira_query: Optional[str] = ""

    github_url: Optional[str] = None
    github_owner: Optional[str] = None
    github_pat: Optional[SecretStr] = None
    github_repository: Optional[str] = None
    github_query: Optional[str] = ""

    slack_token: Optional[SecretStr] = None
    slack_channel: Optional[str] = None

    pagerduty_api_key: Optional[SecretStr] = None
    pagerduty_user_email: Optional[str] = None
    pagerduty_incident_key: Optional[str] = None

    opsgenie_api_key: Optional[SecretStr] = None
    opsgenie_team_integration_key: Optional[SecretStr] = None
    opsgenie_query: Optional[str] = None
    
    custom_runbooks: List[FilePath] = []
    custom_toolsets: List[FilePath] = []

    @classmethod
    def _collect_env_vars(cls) -> Dict[str, Any]:
        """Collect the environment variables that this class might require for setup.

        Environment variable names are determined from model fields as follows:
        - if the model field is not annotated with an EnvVarName, the env var name is
          just the model field name in upper case
        - if the model field is annotated with an EnvVarName, the env var name is
          taken from the annotation.
        """
        vars_dict = {}
        hints = get_type_hints(cls, include_extras=True)
        for field_name in cls.model_fields:
            if field_name == "llm":
                # Handled in load_from_env
                continue
            tp_obj = hints[field_name]
            for arg in get_args(tp_obj):
                if isinstance(arg, EnvVarName):
                    env_var_name = arg
                    break
            else:
                env_var_name = field_name.upper()
            if env_var_name in os.environ:
                vars_dict[field_name] = os.environ[env_var_name]
        return vars_dict

    @classmethod
    def load_from_env(cls) -> "BaseLLMConfig":
        llm_name = os.getenv("LLM_PROVIDER", "OPENAI").lower()
        llm_provider_type = LLMProviderType(llm_name)
        if llm_provider_type == LLMProviderType.AZURE:
            final_class = AzureLLMConfig
        elif llm_provider_type == LLMProviderType.OPENAI:
            final_class = OpenAILLMConfig
        elif llm_provider_type == LLMProviderType.ROBUSTA:
            final_class = RobustaLLMConfig
        else:
            raise NotImplementedError(f"Unknown LLM {llm_name}")
        kwargs = final_class._collect_env_vars()
        ret = final_class(**kwargs)
        return ret


class BaseOpenAIConfig(BaseLLMConfig):
    model: Optional[str] = "gpt-4o"
    max_steps: Optional[int] = 10


class OpenAILLMConfig(BaseOpenAIConfig):
    api_key: Optional[SecretStr]


class AzureLLMConfig(BaseOpenAIConfig):
    api_key: Optional[SecretStr]
    endpoint: Optional[str]
    azure_api_version: Optional[str] = "2024-02-01"


class RobustaLLMConfig(BaseLLMConfig):
    url: Annotated[str, EnvVarName("ROBUSTA_AI_URL")]


# TODO refactor everything below


class LLMConfig(BaseLLMConfig):

    def create_llm(self) -> OpenAI:
        if self.llm == LLMProviderType.OPENAI:
            return OpenAI(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
            )
        elif self.llm == LLMProviderType.AZURE:
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
                console.print(
                    f"[yellow]Disabling toolset {ts.name} [/yellow] from {ts.get_path()}"
                )
            elif ts not in enabled_toolsets:
                console.print(
                    f"[yellow]Not loading toolset {ts.name}[/yellow] ({ts.get_disabled_reason()})"
                )
                #console.print(f"[red]The following tools will be disabled: {[t.name for t in ts.tools]}[/red])")
            else:
                logging.debug(f"Loaded toolset {ts.name} from {ts.get_path()}")
                # console.print(f"[green]Loaded toolset {ts.name}[/green] from {ts.get_path()}")

        enabled_tools = concat(*[ts.tools for ts in enabled_toolsets])
        logging.debug(
            f"Starting AI session with tools: {[t.name for t in enabled_tools]}"
        )
        return YAMLToolExecutor(enabled_toolsets)

    def create_toolcalling_llm(
        self, console: Console, allowed_toolsets: ToolsetPattern
    ) -> ToolCallingLLM:
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

    def create_github_source(self) -> GitHubSource:
        if not (
            self.github_url.startswith(
                "http://") or self.github_url.startswith("https://")
        ):
            raise ValueError("--github-url must start with http:// or https://")
        if self.github_owner is None:
            raise ValueError("--github-owner must be specified")
        if self.github_repository is None:
            raise ValueError("--github-repository must be specified")
        if self.github_pat is None:
            raise ValueError("--github-pat must be specified")

        return GitHubSource(
            url=self.github_url,
            owner=self.github_owner,
            pat=self.github_pat.get_secret_value(),
            repository=self.github_repository,
            query=self.github_query,
        )
    
    def create_pagerduty_source(self) -> OpsGenieSource:
        if self.pagerduty_api_key is None:
            raise ValueError("--pagerduty-api-key must be specified")
        
        return PagerDutySource(
            api_key=self.pagerduty_api_key.get_secret_value(),
            user_email=self.pagerduty_user_email,
            incident_key=self.pagerduty_incident_key,
        )
    
    def create_opsgenie_source(self) -> OpsGenieSource:
        if self.opsgenie_api_key is None:
            raise ValueError("--opsgenie-api-key must be specified")
        
        return OpsGenieSource(
            api_key=self.opsgenie_api_key.get_secret_value(),
            query=self.opsgenie_query,
            team_integration_key=self.opsgenie_team_integration_key.get_secret_value() if self.opsgenie_team_integration_key else None,
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
            alertname=self.alertmanager_alertname,
        )

    def create_slack_destination(self):
        if self.slack_token is None:
            raise ValueError("--slack-token must be specified")
        if self.slack_channel is None:
            raise ValueError("--slack-channel must be specified")
        return SlackDestination(self.slack_token.get_secret_value(), self.slack_channel)

    @classmethod
    def load_from_file(cls, config_file: Optional[str], **kwargs) -> "Config":
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
