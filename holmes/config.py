import logging
import os
import yaml  # type: ignore
import os.path
from typing import Any, Dict, List, Optional, Union

from holmes.config_utils import replace_env_vars_values
from holmes.utils.file_utils import load_yaml_file
from holmes import get_version  # type: ignore
from holmes.clients.robusta_client import HolmesInfo, fetch_holmes_info
from holmes.core.llm import LLM, DefaultLLM
from pydantic import FilePath, SecretStr, BaseModel, ConfigDict
from pydash.arrays import concat
import json
from holmes.core.runbooks import RunbookManager
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tool_calling_llm import IssueInvestigator, ToolCallingLLM, ToolExecutor
from holmes.core.tools import (
    Toolset,
    ToolsetPattern,
    ToolsetYamlFromConfig,
    get_matching_toolsets,
    ToolsetStatusEnum,
    ToolsetTag,
    ToolsetType,
)
from holmes.plugins.destinations.slack import SlackDestination
from holmes.plugins.runbooks import load_builtin_runbooks, load_runbooks_from_file
from holmes.plugins.sources.github import GitHubSource
from holmes.plugins.sources.jira import JiraSource, JiraServiceManagementSource
from holmes.plugins.sources.opsgenie import OpsGenieSource
from holmes.plugins.sources.pagerduty import PagerDutySource
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource

from holmes.plugins.toolsets import load_builtin_toolsets
from holmes.plugins.toolsets.mcp.toolset_mcp import RemoteMCPToolset
from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file
from holmes.utils.definitions import CUSTOM_TOOLSET_LOCATION
from pydantic import ValidationError

from holmes.core.tools import YAMLToolset
from holmes.common.env_vars import ROBUSTA_CONFIG_PATH, ROBUSTA_AI, ROBUSTA_API_ENDPOINT
from holmes.utils.definitions import RobustaConfig
from enum import Enum

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


def load_toolsets_definitions(
    toolsets: dict[str, dict[str, Any]], path: str
) -> List[ToolsetYamlFromConfig]:
    loaded_toolsets: list[ToolsetYamlFromConfig] = []
    if is_old_toolset_config(toolsets):
        message = "Old toolset config format detected, please update to the new format: https://docs.robusta.dev/master/configuration/holmesgpt/custom_toolsets.html"
        logging.warning(message)
        raise ValueError(message)

    for name, config in toolsets.items():
        try:
            validated_config: ToolsetYamlFromConfig = ToolsetYamlFromConfig(
                **config, name=name
            )
            validated_config.set_path(path)
            if validated_config.config:
                validated_config.config = replace_env_vars_values(
                    validated_config.config
                )
            loaded_toolsets.append(validated_config)
        except ValidationError as e:
            logging.warning(f"Toolset '{name}' is invalid: {e}")

        except Exception:
            logging.warning("Failed to load toolset: %s", name, exc_info=True)

    return loaded_toolsets


def parse_toolsets_file(
    path: str, raise_error: bool = True
) -> Optional[List[ToolsetYamlFromConfig]]:
    parsed_yaml = load_yaml_file(path, raise_error)

    toolsets_definitions: dict = parsed_yaml.get("toolsets", {})
    mcp_definitions: dict[str, dict[str, Any]] = parsed_yaml.get("mcp_servers", {})

    for server_config in mcp_definitions.values():
        server_config["type"] = ToolsetType.MCP

    toolsets_definitions.update(mcp_definitions)

    if not toolsets_definitions:
        message = f"No 'toolsets' key found in: {path}"
        logging.warning(message)
        if raise_error:
            raise ValueError(message)
        return None

    try:
        toolset_config = load_toolsets_definitions(toolsets_definitions, path)
    except Exception as err:
        logging.warning(f"Error loading toolset configuration from {path}: {err}")
        if raise_error:
            raise err
        return None

    return toolset_config


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
    custom_toolsets: List[FilePath] = []

    toolsets: Optional[dict[str, dict[str, Any]]] = None

    _server_tool_executor: Optional[ToolExecutor] = None

    _version: Optional[str] = None
    _holmes_info: Optional[HolmesInfo] = None

    @property
    def is_latest_version(self) -> bool:
        if self._holmes_info and self._holmes_info.latest_version and self._version:
            return self._version.startswith(self._holmes_info.latest_version)

        # We couldn't resolve version, assume we are running the latest version
        return True

    def model_post_init(self, __context: Any) -> None:
        self._version = get_version()
        self._holmes_info = fetch_holmes_info()
        self._model_list = parse_models_file(MODEL_LIST_FILE_LOCATION)
        if ROBUSTA_AI:
            self._model_list["Robusta"] = {
                "base_url": ROBUSTA_API_ENDPOINT,
            }
        if self._model_list:
            logging.info(f"loaded models: {list(self._model_list.keys())}")

        if not self.is_latest_version and self._holmes_info:
            logging.warning(
                "You are running version %s of holmes, but the latest version is %s. Please update to the latest version.",
                self._version,
                self._holmes_info.latest_version,
            )

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
        return cls(**kwargs)

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

    def create_console_tool_executor(
        self, allowed_toolsets: ToolsetPattern, dal: Optional[SupabaseDal]
    ) -> ToolExecutor:
        """
        Creates a ToolExecutor instance configured for CLI usage. This executor manages the available tools
        and their execution in the command-line interface.

        The method loads toolsets in this order, with later sources overriding earlier ones:
        1. Built-in toolsets (tagged as CORE or CLI)
        2. Custom toolsets from config files which can override built-in toolsets
        3. Toolsets defined in self.toolsets which can override both built-in and custom toolsets config
        """
        default_toolsets = [
            toolset
            for toolset in load_builtin_toolsets(dal)
            if any(tag in (ToolsetTag.CORE, ToolsetTag.CLI) for tag in toolset.tags)
        ]
        # All built-in toolsets are enabled by default, users can override this in their config
        for toolset in default_toolsets:
            toolset.enabled = True

        if allowed_toolsets == "*":
            matching_toolsets = default_toolsets
        else:
            matching_toolsets = get_matching_toolsets(
                default_toolsets,
                allowed_toolsets.split(","),  # type: ignore
            )

        toolsets_by_name = {toolset.name: toolset for toolset in matching_toolsets}

        toolsets_loaded_from_config = self.load_custom_toolsets_config()

        if toolsets_loaded_from_config:
            toolsets_by_name = (
                self.merge_and_override_bultin_toolsets_with_toolsets_config(
                    toolsets_loaded_from_config,
                    toolsets_by_name,
                )
            )
        if self.toolsets:
            loaded_toolsets_from_env = load_toolsets_definitions(self.toolsets, "env")
            if loaded_toolsets_from_env:
                toolsets_by_name = (
                    self.merge_and_override_bultin_toolsets_with_toolsets_config(
                        loaded_toolsets_from_env,
                        toolsets_by_name,
                    )
                )

        for toolset in toolsets_by_name.values():
            if toolset.enabled:
                toolset.check_prerequisites()

        toolsets = []
        for ts in toolsets_by_name.values():
            toolsets.append(ts)

        for ts in default_toolsets:
            if ts.name not in toolsets_by_name.keys():
                logging.debug(
                    f"Toolset {ts.name} from {ts.get_path()} was filtered out due to allowed_toolsets value"
                )

        enabled_tools = concat(
            *[
                ts.tools
                for ts in toolsets
                if ts.get_status() == ToolsetStatusEnum.ENABLED
            ]
        )
        logging.debug(
            f"Starting AI session with tools: {[t.name for t in enabled_tools]}"
        )
        return ToolExecutor(toolsets)

    def create_tool_executor(self, dal: Optional[SupabaseDal]) -> ToolExecutor:
        """
        Creates ToolExecutor for the server endpoints
        """

        if self._server_tool_executor:
            return self._server_tool_executor

        logging.info("Creating server tool executor")
        all_toolsets = load_builtin_toolsets(dal=dal)

        toolsets_by_name: dict[str, Toolset] = {
            toolset.name: toolset
            for toolset in all_toolsets
            if any(tag in (ToolsetTag.CORE, ToolsetTag.CLUSTER) for tag in toolset.tags)
        }

        toolsets_loaded_from_config = self.load_custom_toolsets_config()
        if toolsets_loaded_from_config:
            toolsets_by_name = (
                self.merge_and_override_bultin_toolsets_with_toolsets_config(
                    toolsets_loaded_from_config,
                    toolsets_by_name,
                )
            )

        if self.toolsets:
            loaded_toolsets_from_env = load_toolsets_definitions(self.toolsets, "env")
            if loaded_toolsets_from_env:
                toolsets_by_name = (
                    self.merge_and_override_bultin_toolsets_with_toolsets_config(
                        loaded_toolsets_from_env,
                        toolsets_by_name,
                    )
                )

        toolsets: list[Toolset] = list(toolsets_by_name.values())

        for toolset in toolsets:
            if toolset.enabled:
                toolset.check_prerequisites()

        self._server_tool_executor = ToolExecutor(toolsets)

        logging.debug(
            f"Starting AI session with tools: {[tn for tn in self._server_tool_executor.tools_by_name.keys()]}"
        )

        return self._server_tool_executor

    def create_console_toolcalling_llm(
        self, allowed_toolsets: ToolsetPattern, dal: Optional[SupabaseDal] = None
    ) -> ToolCallingLLM:
        tool_executor = self.create_console_tool_executor(allowed_toolsets, dal)
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
        self, allowed_toolsets: ToolsetPattern, dal: Optional[SupabaseDal] = None
    ) -> IssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))

        runbook_manager = RunbookManager(all_runbooks)
        tool_executor = self.create_console_tool_executor(allowed_toolsets, dal)
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

    def load_custom_toolsets_config(self) -> Optional[list[ToolsetYamlFromConfig]]:
        """
        Loads toolsets config from /etc/holmes/config/custom_toolset.yaml with ToolsetYamlFromConfig class
        that doesn't have strict validations.
        Example configuration:

        kubernetes/logs:
            enabled: false

        test/configurations:
            enabled: true
            icon_url: "example.com"
            description: "test_description"
            docs_url: "https://docs.docker.com/"
            prerequisites:
                - env:
                    - API_ENDPOINT
                - command: "curl ${API_ENDPOINT}"
            additional_instructions: "jq -r '.result.results[].userData | fromjson | .text | fromjson | .log'"
            tools:
                - name: "curl_example"
                description: "Perform a curl request to example.com using variables"
                command: "curl -X GET '{{api_endpoint}}?query={{ query_param }}' "
        """
        loaded_toolsets = []
        for custom_path in self.custom_toolsets:
            if not os.path.isfile(custom_path):
                logging.warning(f"Custom toolset file {custom_path} does not exist")
                continue
            toolset_config = parse_toolsets_file(
                path=str(custom_path), raise_error=False
            )
            if toolset_config:
                loaded_toolsets.extend(toolset_config)

        # if toolsets are loaded from custom_toolsets, return them without checking the default location
        if loaded_toolsets:
            return loaded_toolsets

        if not os.path.isfile(CUSTOM_TOOLSET_LOCATION):
            logging.debug(
                f"Custom toolset file {CUSTOM_TOOLSET_LOCATION} does not exist"
            )
            return []

        return parse_toolsets_file(path=str(CUSTOM_TOOLSET_LOCATION), raise_error=True)

    def merge_and_override_bultin_toolsets_with_toolsets_config(
        self,
        toolsets_loaded_from_config: list[ToolsetYamlFromConfig],
        default_toolsets_by_name: dict[str, Toolset],
    ) -> dict[str, Toolset]:
        """
        Merges and overrides default_toolsets_by_name with custom
        config from /etc/holmes/config/custom_toolset.yaml
        """
        toolsets_with_updated_statuses: Dict[str, YAMLToolset | RemoteMCPToolset] = {
            toolset.name: toolset  # type: ignore
            for toolset in default_toolsets_by_name.values()  # type: ignore
        }

        for toolset in toolsets_loaded_from_config:
            if toolset.name in toolsets_with_updated_statuses.keys():
                toolsets_with_updated_statuses[toolset.name].override_with(toolset)
            else:
                try:
                    validated_toolset: YAMLToolset | RemoteMCPToolset
                    if toolset.type == ToolsetType.MCP:
                        validated_toolset = RemoteMCPToolset(
                            **toolset.model_dump(exclude_none=True)
                        )
                    else:
                        validated_toolset = YAMLToolset(
                            **toolset.model_dump(exclude_none=True)
                        )
                    toolsets_with_updated_statuses[toolset.name] = validated_toolset
                except Exception as error:
                    logging.error(
                        f"Toolset '{toolset.name}' is invalid: {error} ", exc_info=True
                    )

        return toolsets_with_updated_statuses  # type: ignore

    @classmethod
    def load_from_file(cls, config_file: Optional[str], **kwargs) -> "Config":
        if config_file is not None:
            logging.debug("Loading config from file %s", config_file)
            config_from_file = load_model_from_file(cls, config_file)
        elif os.path.exists(DEFAULT_CONFIG_LOCATION):
            logging.debug(
                f"Loading config from default location {DEFAULT_CONFIG_LOCATION}"
            )
            config_from_file = load_model_from_file(cls, DEFAULT_CONFIG_LOCATION)
        else:
            logging.debug(
                f"No config file found at {DEFAULT_CONFIG_LOCATION}, using cli settings only"
            )
            config_from_file = None

        cli_options = {k: v for k, v in kwargs.items() if v is not None and v != []}

        if config_from_file is None:
            return cls(**cli_options)

        merged_config = config_from_file.dict()
        merged_config.update(cli_options)
        return cls(**merged_config)

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
        config_file: Optional[str],
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
