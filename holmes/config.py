import logging
import os
import yaml
import os.path

from pydantic.main import BaseModel
from holmes.core.llm import LLM, DefaultLLM
from strenum import StrEnum
from typing import Any, Dict, List, Optional
from typing import List, Optional


from pydantic import FilePath, SecretStr, Field
from pydash.arrays import concat
from rich.console import Console


from holmes.core.runbooks import RunbookManager
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tool_calling_llm import (IssueInvestigator, 
                                          ToolCallingLLM,
                                          ToolExecutor)
from holmes.core.tools import ToolsetPattern, get_matching_toolsets, ToolsetStatusEnum, ToolsetTag
from holmes.plugins.destinations.slack import SlackDestination
from holmes.plugins.runbooks import (load_builtin_runbooks,
                                     load_runbooks_from_file)
from holmes.plugins.sources.github import GitHubSource
from holmes.plugins.sources.jira import JiraSource
from holmes.plugins.sources.opsgenie import OpsGenieSource
from holmes.plugins.sources.pagerduty import PagerDutySource
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource
from holmes.plugins.toolsets import (load_builtin_toolsets,
                                     load_toolsets_from_file)
from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file
from holmes.utils.definitions import CUSTOM_TOOLSET_LOCATION
from pydantic import ValidationError
from holmes.utils.holmes_sync_toolsets import load_custom_toolsets_config, merge_and_override_bultin_toolsets_with_toolsets_config, extract_config_from_custom_toolsets_config
from holmes.core.tools import YAMLToolset
from holmes.common.env_vars import ROBUSTA_CONFIG_PATH
from holmes.utils.definitions import RobustaConfig
import re

DEFAULT_CONFIG_LOCATION = os.path.expanduser("/Users/avirobusta/git/holmesgpt/config.yaml")

def get_env_replacement(value: str) -> Optional[str]:
    env_values = re.findall(r"{{\s*env\.([^\s]*)\s*}}", value)
    if not env_values:
        return None
    env_var_key = env_values[0].strip()
    if env_var_key not in os.environ:
        msg = f"ENV var replacement {env_var_key} does not exist for param: {value}"
        logging.error(msg)
        raise Exception(msg)
    
    return os.environ.get(env_var_key)




def replace_env_vars_values(values: Dict) -> Dict:
    for key, value in values.items():
        if isinstance(value, str):
            env_var_value = get_env_replacement(value)
            if env_var_value:
                values[key] = env_var_value
        elif isinstance(value, SecretStr):
            env_var_value = get_env_replacement(value.get_secret_value())
            if env_var_value:
                values[key] = SecretStr(env_var_value)
        elif isinstance(value, dict):
            replace_env_vars_values(value)
        elif isinstance(value, list):
            values[key] = [replace_env_vars_values(iter) for iter in value]
    return values

class Config(RobustaBaseConfig):
    api_key: Optional[SecretStr] = (
        None  # if None, read from OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT env var
    )
    model: Optional[str] = "gpt-4o"
    max_steps: Optional[int] = 10
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
    
    enabled_toolsets_names: List[str] = Field(default_factory=list)

    opensearch_clusters: Optional[List[Dict]] = None # Passed through to opensearchpy.OpenSearch constructor

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
        configs = extract_config_from_custom_toolsets_config()
        combined = {}
        for item in configs:
            if isinstance(item, dict):
                for key, value in item.items():
                    combined[key] = value
        combined.update(kwargs)
        return cls(**combined)
    
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
        self, console: Console, allowed_toolsets: ToolsetPattern, dal:Optional[SupabaseDal]
    ) -> ToolExecutor:
        """
        Creates ToolExecutor for the cli 
        """
        default_toolsets = [toolset for toolset in load_builtin_toolsets(dal, opensearch_clusters=self.opensearch_clusters) if any(tag in (ToolsetTag.CORE, ToolsetTag.CLI) for tag in toolset.tags)]
        
        if allowed_toolsets == "*":
            matching_toolsets = default_toolsets
        else:
            matching_toolsets = get_matching_toolsets(
                default_toolsets, allowed_toolsets.split(",")
            )        
        
        # Enable all matching toolsets that have CORE or CLI tag
        for toolset in matching_toolsets:
            toolset.enabled = True

        matched_default_toolsets_by_name = {toolset.name: toolset for toolset in matching_toolsets}
        toolsets_loaded_from_config = load_custom_toolsets_config()

        filtered_toolsets_by_name = merge_and_override_bultin_toolsets_with_toolsets_config(
            toolsets_loaded_from_config,
            matched_default_toolsets_by_name,
        )
        
        for toolset in filtered_toolsets_by_name.values():
            if toolset.enabled:
                toolset.check_prerequisites()

        enabled_toolsets = []
        for ts in filtered_toolsets_by_name.values():
            if ts.get_status() == ToolsetStatusEnum.ENABLED:
                enabled_toolsets.append(ts)
                logging.info(f"Loaded toolset {ts.name} from {ts.get_path()}")
            elif ts.get_status() == ToolsetStatusEnum.DISABLED:
                logging.info(f"Disabled toolset: {ts.name} from {ts.get_path()})")
            elif ts.get_status() == ToolsetStatusEnum.FAILED:
                logging.info(f"Failed loading toolset {ts.name} from {ts.get_path()}: ({ts.get_error()})")
        
        for ts in default_toolsets:
            if ts.name not in filtered_toolsets_by_name.keys():
                 logging.debug(f"Toolset {ts.name} from {ts.get_path()} was filtered out due to allowed_toolsets value")
        
        enabled_tools = concat(*[ts.tools for ts in enabled_toolsets])
        logging.debug(
            f"Starting AI session with tools: {[t.name for t in enabled_tools]}"
        )
        return ToolExecutor(enabled_toolsets)

    def create_tool_executor(
        self, console: Console, dal:Optional[SupabaseDal]
    ) -> ToolExecutor:
        """
        Creates ToolExecutor for the server endpoints 
        """

        all_toolsets = load_builtin_toolsets(dal=dal, opensearch_clusters=self.opensearch_clusters)

        if os.path.isfile(CUSTOM_TOOLSET_LOCATION):
            try:
                all_toolsets.extend(load_toolsets_from_file(CUSTOM_TOOLSET_LOCATION, silent_fail=True))
            except Exception as error:
                logging.error(f"An error happened while trying to use custom toolset: {error}")

        enabled_toolsets = [ts for ts in all_toolsets if ts.name in self.enabled_toolsets_names]
        enabled_tools = concat(*[ts.tools for ts in enabled_toolsets])
        logging.debug(
            f"Starting AI session with tools: {[t.name for t in enabled_tools]}"
        )
        return ToolExecutor(enabled_toolsets)
    
    def create_console_toolcalling_llm(
        self, console: Console, allowed_toolsets: ToolsetPattern, dal:Optional[SupabaseDal] = None
    ) -> ToolCallingLLM:
        tool_executor = self.create_console_tool_executor(console, allowed_toolsets, dal)
        return ToolCallingLLM(
            tool_executor,
            self.max_steps,
            self._get_llm()
        )

    def create_toolcalling_llm(
        self, console: Console,  dal:Optional[SupabaseDal] = None
    ) -> ToolCallingLLM:
        tool_executor = self.create_tool_executor(console, dal)
        return ToolCallingLLM(
            tool_executor,
            self.max_steps,
            self._get_llm()
        )

    def create_issue_investigator(
        self,
        console: Console,
        dal: Optional[SupabaseDal] = None
    ) -> IssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))

        runbook_manager = RunbookManager(all_runbooks)
        tool_executor = self.create_tool_executor(console, dal)
        return IssueInvestigator(
            tool_executor,
            runbook_manager,
            self.max_steps,
            self._get_llm()
        )
    
    def create_console_issue_investigator(
        self,
        console: Console,
        allowed_toolsets: ToolsetPattern,
        dal: Optional[SupabaseDal] = None
    ) -> IssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))

        runbook_manager = RunbookManager(all_runbooks)
        tool_executor = self.create_console_tool_executor(console, allowed_toolsets, dal)
        return IssueInvestigator(
            tool_executor,
            runbook_manager,
            self.max_steps,
            self._get_llm()
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
        return AlertManagerSource(
            url=self.alertmanager_url,
            username=self.alertmanager_username,
            password=self.alertmanager_password,
            alertname_filter=self.alertmanager_alertname,
            label_filter=self.alertmanager_label,
            filepath=self.alertmanager_file,
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
            logging.debug(f"Loading config from file %s", config_file)
            config_from_file = load_model_from_file(cls, config_file)
        elif os.path.exists(DEFAULT_CONFIG_LOCATION):
            logging.debug(f"Loading config from default location {DEFAULT_CONFIG_LOCATION}")
            config_from_file = load_model_from_file(cls, DEFAULT_CONFIG_LOCATION)
        else:
            logging.debug(f"No config file found at {DEFAULT_CONFIG_LOCATION}, using cli settings only")
            config_from_file = None

        cli_options = {
            k: v for k, v in kwargs.items() if v is not None and v != []
        }
        if config_from_file is None:
            return cls(**cli_options)

        merged_config = config_from_file.dict()
        merged_config.update(cli_options)
        return cls(**merged_config)

    def _get_llm(self) -> LLM:
        api_key = self.api_key.get_secret_value() if self.api_key else None
        return DefaultLLM(self.model, api_key)
