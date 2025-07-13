import json
import logging
import os
import os.path
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Union

import yaml  # type: ignore
from pydantic import BaseModel, ConfigDict, FilePath, SecretStr

from holmes import get_version  # type: ignore
from holmes.clients.robusta_client import HolmesInfo, fetch_holmes_info
from holmes.common.env_vars import ROBUSTA_AI, ROBUSTA_API_ENDPOINT, ROBUSTA_CONFIG_PATH
from holmes.core.llm import LLM, DefaultLLM
from holmes.core.runbooks import RunbookManager
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tool_calling_llm import IssueInvestigator, ToolCallingLLM
from holmes.core.tools_utils.tool_executor import ToolExecutor
from holmes.core.toolset_manager import ToolsetManager
from holmes.plugins.destinations.slack import SlackDestination
from holmes.plugins.runbooks import (
    RunbookCatalog,
    load_builtin_runbooks,
    load_runbook_catalog,
    load_runbooks_from_file,
)
from holmes.plugins.sources.github import GitHubSource
from holmes.plugins.sources.jira import JiraServiceManagementSource, JiraSource
from holmes.plugins.sources.opsgenie import OpsGenieSource
from holmes.plugins.sources.pagerduty import PagerDutySource
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource
from holmes.utils.definitions import RobustaConfig
from holmes.utils.env import replace_env_vars_values
from holmes.utils.file_utils import load_yaml_file
from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file

DEFAULT_CONFIG_LOCATION = os.path.expanduser("~/.holmes/config.yaml")
MODEL_LIST_FILE_LOCATION = os.environ.get(
    "MODEL_LIST_FILE_LOCATION", "/etc/holmes/config/model_list.yaml"
)


class SupportedTicketSources(str, Enum):
    JIRA_SERVICE_MANAGEMENT = "jira-service-management"
    PAGERDUTY = "pagerduty"


def is_old_toolset_config(
    toolsets: Union[dict[str, dict[str, Any]], List[dict[str, Any]]],
) -> bool:
    # old config is a list of toolsets
    if isinstance(toolsets, list):
        return True
    return False


def parse_models_file(path: str):
    models = load_yaml_file(path, raise_error=False, warn_not_found=False)

    for model, params in models.items():
        params = replace_env_vars_values(params)

    return models


class Config(RobustaBaseConfig):
    api_key: Optional[SecretStr] = (
        None  # if None, read from OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT env var
    )
    model: Optional[str] = "gpt-4o"
    max_steps: int = 10
    cluster_name: Optional[str] = None

    alertmanager_url: Optional[str] = None
    alertmanager_username: Optional[str] = None
    alertmanager_password: Optional[str] = None
    alertmanager_alertname: Optional[str] = None
    alertmanager_label: Optional[List[str]] = []
    alertmanager_file: Optional[FilePath] = None

    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_api_key: Optional[SecretStr] = None
    jira_query: Optional[str] = ""

    github_url: Optional[str] = None
    github_owner: Optional[str] = None
    github_pat: Optional[SecretStr] = None
    github_repository: Optional[str] = None
    github_query: str = ""

    slack_token: Optional[SecretStr] = None
    slack_channel: Optional[str] = None

    pagerduty_api_key: Optional[SecretStr] = None
    pagerduty_user_email: Optional[str] = None
    pagerduty_incident_key: Optional[str] = None

    opsgenie_api_key: Optional[SecretStr] = None
    opsgenie_team_integration_key: Optional[SecretStr] = None
    opsgenie_query: Optional[str] = None

    custom_runbooks: List[FilePath] = []

    # custom_toolsets is passed from config file, and be used to override built-in toolsets, provides 'stable' customized toolset.
    # The status of custom toolsets can be cached.
    custom_toolsets: Optional[List[FilePath]] = None
    # custom_toolsets_from_cli is passed from CLI option `--custom-toolsets` as 'experimental' custom toolsets.
    # The status of toolset here won't be cached, so the toolset from cli will always be loaded when specified in the CLI.
    custom_toolsets_from_cli: Optional[List[FilePath]] = None

    toolsets: Optional[dict[str, dict[str, Any]]] = None

    _server_tool_executor: Optional[ToolExecutor] = None

    _version: Optional[str] = None
    _holmes_info: Optional[HolmesInfo] = None

    _toolset_manager: Optional[ToolsetManager] = None

    @property
    def is_latest_version(self) -> bool:
        if (
            not self._holmes_info
            or not self._holmes_info.latest_version
            or not self._version
        ):
            # We couldn't resolve version, assume we are running the latest version
            return True
        if self._version.startswith("dev-"):
            # dev versions are considered to be the latest version
            return True

        return self._version.startswith(self._holmes_info.latest_version)

    @property
    def toolset_manager(self) -> ToolsetManager:
        if not self._toolset_manager:
            self._toolset_manager = ToolsetManager(
                toolsets=self.toolsets,
                custom_toolsets=self.custom_toolsets,
                custom_toolsets_from_cli=self.custom_toolsets_from_cli,
            )
        return self._toolset_manager

    def model_post_init(self, __context: Any) -> None:
        self._version = get_version()
        self._holmes_info = fetch_holmes_info()
        self._model_list = parse_models_file(MODEL_LIST_FILE_LOCATION)
        if ROBUSTA_AI:
            self._model_list["Robusta"] = {
                "base_url": ROBUSTA_API_ENDPOINT,
            }

    def log_useful_info(self):
        if self._model_list:
            logging.info(f"loaded models: {list(self._model_list.keys())}")

        if not self.is_latest_version and self._holmes_info:
            logging.warning(
                f"You are running version {self._version} of holmes, but the latest version is {self._holmes_info.latest_version}. Please update.",
            )

    @classmethod
    def load_from_file(cls, config_file: Optional[Path], **kwargs) -> "Config":
        """
        Load configuration from file and merge with CLI options.

        Args:
            config_file: Path to configuration file
            **kwargs: CLI options to override config file values

        Returns:
            Config instance with merged settings
        """
        config_from_file: Optional[Config] = None
        if config_file is not None and config_file.exists():
            logging.debug(f"Loading config from {config_file}")
            config_from_file = load_model_from_file(cls, config_file)

        cli_options = {k: v for k, v in kwargs.items() if v is not None and v != []}

        if config_from_file is None:
            result = cls(**cli_options)
        else:
            logging.debug(f"Overriding config from cli options {cli_options}")
            merged_config = config_from_file.dict()
            merged_config.update(cli_options)
            result = cls(**merged_config)

        result.log_useful_info()
        return result

    @classmethod
    def load_from_env(cls):
        kwargs = {}
        for field_name in [
            "model",
            "api_key",
            "max_steps",
            "alertmanager_url",
            "alertmanager_username",
            "alertmanager_password",
            "jira_url",
            "jira_username",
            "jira_api_key",
            "jira_query",
            "slack_token",
            "slack_channel",
            "github_url",
            "github_owner",
            "github_repository",
            "github_pat",
            "github_query",
            # TODO
            # custom_runbooks
        ]:
            val = os.getenv(field_name.upper(), None)
            if val is not None:
                kwargs[field_name] = val
        kwargs["cluster_name"] = Config.__get_cluster_name()
        result = cls(**kwargs)
        result.log_useful_info()
        return result

    @staticmethod
    def __get_cluster_name() -> Optional[str]:
        config_file_path = ROBUSTA_CONFIG_PATH
        env_cluster_name = os.environ.get("CLUSTER_NAME")
        if env_cluster_name:
            return env_cluster_name

        if not os.path.exists(config_file_path):
            logging.info(f"No robusta config in {config_file_path}")
            return None

        logging.info(f"loading config {config_file_path}")
        with open(config_file_path) as file:
            yaml_content = yaml.safe_load(file)
            config = RobustaConfig(**yaml_content)
            return config.global_config.get("cluster_name")

        return None

    @staticmethod
    def get_runbook_catalog() -> Optional[RunbookCatalog]:
        # TODO(mainred): besides the built-in runbooks, we need to allow the user to bring their own runbooks
        runbook_catalog = load_runbook_catalog()
        return runbook_catalog

    def create_console_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        """
        Creates a ToolExecutor instance configured for CLI usage. This executor manages the available tools
        and their execution in the command-line interface.

        The method loads toolsets in this order, with later sources overriding earlier ones:
        1. Built-in toolsets (tagged as CORE or CLI)
        2. toolsets from config file will override and be merged into built-in toolsets with the same name.
        3. Custom toolsets from config files which can not override built-in toolsets
        """
        cli_toolsets = self.toolset_manager.list_console_toolsets(dal=dal)
        return ToolExecutor(cli_toolsets)

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        """
        Creates ToolExecutor for the server endpoints
        """

        if self._server_tool_executor:
            return self._server_tool_executor

        toolsets = self.toolset_manager.list_server_toolsets(dal=dal)

        self._server_tool_executor = ToolExecutor(toolsets)

        logging.debug(
            f"Starting AI session with tools: {[tn for tn in self._server_tool_executor.tools_by_name.keys()]}"
        )

        return self._server_tool_executor

    def create_console_toolcalling_llm(
        self, dal: Optional[SupabaseDal] = None
    ) -> ToolCallingLLM:
        tool_executor = self.create_console_tool_executor(dal)
        return ToolCallingLLM(tool_executor, self.max_steps, self._get_llm())

    def create_toolcalling_llm(
        self, dal: Optional[SupabaseDal] = None, model: Optional[str] = None
    ) -> ToolCallingLLM:
        tool_executor = self.create_tool_executor(dal)
        return ToolCallingLLM(tool_executor, self.max_steps, self._get_llm(model))

    def create_issue_investigator(
        self, dal: Optional[SupabaseDal] = None, model: Optional[str] = None
    ) -> IssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))

        runbook_manager = RunbookManager(all_runbooks)
        tool_executor = self.create_tool_executor(dal)
        return IssueInvestigator(
            tool_executor, runbook_manager, self.max_steps, self._get_llm(model)
        )

    def create_console_issue_investigator(
        self, dal: Optional[SupabaseDal] = None
    ) -> IssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))

        runbook_manager = RunbookManager(all_runbooks)
        tool_executor = self.create_console_tool_executor(dal=dal)
        return IssueInvestigator(
            tool_executor, runbook_manager, self.max_steps, self._get_llm()
        )

    def validate_jira_config(self):
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

    def create_jira_source(self) -> JiraSource:
        self.validate_jira_config()

        return JiraSource(
            url=self.jira_url,  # type: ignore
            username=self.jira_username,  # type: ignore
            api_key=self.jira_api_key.get_secret_value(),  # type: ignore
            jql_query=self.jira_query,  # type: ignore
        )

    def create_jira_service_management_source(self) -> JiraServiceManagementSource:
        self.validate_jira_config()

        return JiraServiceManagementSource(
            url=self.jira_url,  # type: ignore
            username=self.jira_username,  # type: ignore
            api_key=self.jira_api_key.get_secret_value(),  # type: ignore
            jql_query=self.jira_query,  # type: ignore
        )

    def create_github_source(self) -> GitHubSource:
        if not self.github_url or not (
            self.github_url.startswith("http://")
            or self.github_url.startswith("https://")
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

    def create_pagerduty_source(self) -> PagerDutySource:
        if self.pagerduty_api_key is None:
            raise ValueError("--pagerduty-api-key must be specified")

        return PagerDutySource(
            api_key=self.pagerduty_api_key.get_secret_value(),
            user_email=self.pagerduty_user_email,  # type: ignore
            incident_key=self.pagerduty_incident_key,
        )

    def create_opsgenie_source(self) -> OpsGenieSource:
        if self.opsgenie_api_key is None:
            raise ValueError("--opsgenie-api-key must be specified")

        return OpsGenieSource(
            api_key=self.opsgenie_api_key.get_secret_value(),
            query=self.opsgenie_query,  # type: ignore
            team_integration_key=(
                self.opsgenie_team_integration_key.get_secret_value()
                if self.opsgenie_team_integration_key
                else None
            ),
        )

    def create_alertmanager_source(self) -> AlertManagerSource:
        return AlertManagerSource(
            url=self.alertmanager_url,  # type: ignore
            username=self.alertmanager_username,
            alertname_filter=self.alertmanager_alertname,  # type: ignore
            label_filter=self.alertmanager_label,  # type: ignore
            filepath=self.alertmanager_file,
        )

    def create_slack_destination(self):
        if self.slack_token is None:
            raise ValueError("--slack-token must be specified")
        if self.slack_channel is None:
            raise ValueError("--slack-channel must be specified")
        return SlackDestination(self.slack_token.get_secret_value(), self.slack_channel)

    def _get_llm(self, model_key: Optional[str] = None) -> LLM:
        api_key = self.api_key.get_secret_value() if self.api_key else None
        model = self.model
        model_params = {}
        if self._model_list:
            # get requested model or the first credentials if no model requested.
            model_params = (
                self._model_list.get(model_key, {}).copy()
                if model_key
                else next(iter(self._model_list.values())).copy()
            )
            api_key = model_params.pop("api_key", api_key)
            model = model_params.pop("model", model)

        return DefaultLLM(model, api_key, model_params)  # type: ignore

    def get_models_list(self) -> List[str]:
        if self._model_list:
            return json.dumps(list(self._model_list.keys()))  # type: ignore

        return json.dumps([self.model])  # type: ignore


class TicketSource(BaseModel):
    config: Config
    output_instructions: list[str]
    source: Union[JiraServiceManagementSource, PagerDutySource]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SourceFactory(BaseModel):
    @staticmethod
    def create_source(
        source: SupportedTicketSources,
        config_file: Optional[Path],
        ticket_url: Optional[str],
        ticket_username: Optional[str],
        ticket_api_key: Optional[str],
        ticket_id: Optional[str],
    ) -> TicketSource:
        supported_sources = [s.value for s in SupportedTicketSources]
        if source not in supported_sources:
            raise ValueError(
                f"Source '{source}' is not supported. Supported sources: {', '.join(supported_sources)}"
            )

        if source == SupportedTicketSources.JIRA_SERVICE_MANAGEMENT:
            config = Config.load_from_file(
                config_file=config_file,
                api_key=None,
                model=None,
                max_steps=None,
                jira_url=ticket_url,
                jira_username=ticket_username,
                jira_api_key=ticket_api_key,
                jira_query=None,
                custom_toolsets=None,
                custom_runbooks=None,
            )

            if not (
                config.jira_url
                and config.jira_username
                and config.jira_api_key
                and ticket_id
            ):
                raise ValueError(
                    "URL, username, API key, and ticket ID are required for jira-service-management"
                )

            output_instructions = [
                "All output links/urls must **always** be of this format : [link text here|http://your.url.here.com] and **never*** the format [link text here](http://your.url.here.com)"
            ]
            source_instance = config.create_jira_service_management_source()
            return TicketSource(
                config=config,
                output_instructions=output_instructions,
                source=source_instance,
            )

        elif source == SupportedTicketSources.PAGERDUTY:
            config = Config.load_from_file(
                config_file=config_file,
                api_key=None,
                model=None,
                max_steps=None,
                pagerduty_api_key=ticket_api_key,
                pagerduty_user_email=ticket_username,
                pagerduty_incident_key=None,
                custom_toolsets=None,
                custom_runbooks=None,
            )

            if not (
                config.pagerduty_user_email and config.pagerduty_api_key and ticket_id
            ):
                raise ValueError(
                    "username, API key, and ticket ID are required for pagerduty"
                )

            output_instructions = [
                "All output links/urls must **always** be of this format : \n link text here: http://your.url.here.com\n **never*** use the url the format [link text here](http://your.url.here.com)"
            ]
            source_instance = config.create_pagerduty_source()  # type: ignore
            return TicketSource(
                config=config,
                output_instructions=output_instructions,
                source=source_instance,
            )

        else:
            raise NotImplementedError(f"Source '{source}' is not yet implemented")
