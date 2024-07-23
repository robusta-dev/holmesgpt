import logging
import os
import os.path

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.outputs import GenerationChunk
from langchain_core.utils import get_from_dict_or_env
from pydantic.v1 import root_validator
from strenum import StrEnum
from typing import List, Optional, Dict, Any, Type, Iterator

from openai import AzureOpenAI, OpenAI
from pydantic import FilePath, SecretStr, BaseModel, create_model, Field
from pydash.arrays import concat
from rich.console import Console
from langchain_core.language_models import BaseLLM, LLM

from holmes.core.runbooks import RunbookManager
from holmes.core.tool_calling_llm import (IssueInvestigator, ToolCallingLLM,
                                          YAMLToolExecutor)

from holmes.core.tool_calling_langchain import LCToolCallingLLM, LCIssueInvestigator
from holmes.core.tools import ToolsetPattern, get_matching_toolsets
from holmes.core.tools_langchain import LCYAMLTool, LangchainYamlTool
from holmes.plugins.destinations.slack import SlackDestination
from holmes.plugins.runbooks import (load_builtin_runbooks,
                                     load_runbooks_from_file)
from holmes.plugins.sources.github import GitHubSource
from holmes.plugins.sources.jira import JiraSource
from holmes.plugins.sources.opsgenie import OpsGenieSource
from holmes.plugins.sources.pagerduty import PagerDutySource
from holmes.plugins.sources.prometheus.plugin import AlertManagerSource
from holmes.plugins.toolsets import (load_builtin_toolsets,
                                     load_toolsets_from_file,
                                     load_builtin_lctoolsets)
from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file


DEFAULT_CONFIG_LOCATION = os.path.expanduser("~/.holmes/config.yaml")


class VolcArkLLM(LLM):
    volc_engine_ak: str | None = None,
    volc_engine_sk: str | None = None,
    model: str = None

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        values["ak"] = get_from_dict_or_env(
                values,
                "volc_engine_ak",
                "VOLC_AK",
                default="",
        )
        values["sk"] = get_from_dict_or_env(
            values,
            "volc_engine_sk",
            "VOLC_SK",
            default="",
        )
        try:
            from volcenginesdkarkruntime import Ark

            values["client"] = Ark(ak=values["ak"], sk=values["sk"])
        except ImportError:
            raise ImportError(
                "qianfan package not found, please install it with "
                "`pip install qianfan`"
            )
        return values

    def _convert_prompt_msg_params(
        self,
        prompt: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict:
        model_req = {
            "model": self.model,
        }
        return {
            **model_req,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream
            # "parameters": {**self._default_params, **kwargs},
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        params = self._convert_prompt_msg_params(prompt, **kwargs)
        response = self.client.chat.completions.create(**params)

        return response.choices[0].message.content

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        params = self._convert_prompt_msg_params(prompt, stream=True, **kwargs)
        for res in self.client.chat.completions.create(**params):

            if not res.choices:
                continue
            chunk = GenerationChunk(
                text=res.choices[0].delta.content)
            if run_manager:
                run_manager.on_llm_new_token(chunk.text, chunk=chunk)
            yield chunk

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return a dictionary of identifying parameters."""
        return {
            # The model name allows users to specify custom token counting
            # rules in LLM monitoring applications (e.g., in LangSmith users
            # can provide per token pricing for their model and monitor
            # costs for the given LLM.)
            "model_name": "Ark",
        }

    @property
    def _llm_type(self) -> str:
        return "Ark"

class LLMType(StrEnum):
    OPENAI = "openai"
    AZURE = "azure"


class Config(RobustaBaseConfig):
    llm: Optional[LLMType] = LLMType.OPENAI
    api_key: Optional[SecretStr] = (
        None  # if None, read from OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT env var
    )
    azure_endpoint: Optional[str] = (
        None  # if None, read from AZURE_OPENAI_ENDPOINT env var
    )
    azure_api_version: Optional[str] = "2024-02-01"
    # model: Optional[str] = "gpt-4o"
    model: Optional[str] = "gpt-3.5-turbo"
    max_steps: Optional[int] = 10

    alertmanager_url: Optional[str] = None
    alertmanager_username: Optional[str] = None
    alertmanager_password: Optional[str] = None
    alertmanager_alertname: Optional[str] = None
    alertmanager_label: Optional[str] = None
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

    @classmethod
    def load_from_env(cls):
        kwargs = {"llm": LLMType(os.getenv("HOLMES_LLM", "OPENAI").lower())}
        for field_name in [
            "model",
            "api_key",
            "azure_endpoint",
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
            # custom_toolsets
        ]:
            val = os.getenv(field_name.upper(), None)
            if val is not None:
                kwargs[field_name] = val
        return cls(**kwargs)

    def create_llm(self) -> OpenAI:
        if self.llm == LLMType.OPENAI:
            logging.debug(f"Using OpenAI")
            client = OpenAI(
                # defaults to os.environ.get("OPENAI_API_KEY")
                api_key="sk-O0WQwcYSZjqoA52DgmjXljJq523597n71NqhmvpACizDgR1h",
                base_url="https://api.chatanywhere.tech/v1"
                # base_url="https://api.chatanywhere.cn/v1"
            )
            return client
            # return OpenAI(
            #     api_key=self.api_key.get_secret_value() if self.api_key else None,
            # )
        elif self.llm == LLMType.AZURE:
            logging.debug(f"Using Azure with endpoint {self.azure_endpoint}")
            return AzureOpenAI(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
                azure_endpoint=self.azure_endpoint,
                api_version=self.azure_api_version,
            )
        else:
            raise ValueError(f"Unknown LLM type: {self.llm}")

    def create_langchain_model(self) -> BaseLLM:
        # from langchain_community.llms.ollama import Ollama
        # llm = Ollama(base_url='http://172.30.87.8:11434', model="qwen2:7b")
        # os.environ['QIANFAN_ACCESS_KEY'] = 'ALTAKY8B6rgQajrLfGTt2cQJa3'
        # os.environ['QIANFAN_SECRET_KEY'] = '35f4259d59984682a33b682fcff1d7bd'
        # from langchain_community.llms.baidu_qianfan_endpoint import \
        #     QianfanLLMEndpoint
        # llm = QianfanLLMEndpoint(model="ERNIE-Speed-128k")
        llm = self._get_volcengine_llm()
        return llm

    def _get_volcengine_llm(self) -> BaseLLM:
        llm = VolcArkLLM(
            volc_engine_ak="AKLTZjRjOTUyMjhkNTk1NGY3NDllNGMxZDgyYjkyODg5YTc",
            volc_engine_sk="TlRrd1pUUXdOelpoWWpsa05Ea3paVGxsTWpVNU9EZzFOMlpsWkRZd1pHSQ==",
            # Doubao-pro-32k
            model="ep-20240716070955-bh4rh",
            # functioncall
            # model="ep-20240716083322-8xdnb",
            # Doubao-pro-4k
            # model="ep-20240716070955-bh4rh",
        )
        return llm

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

    def _create_lctool_executor_toolset(
        self, console: Console, allowed_toolsets: ToolsetPattern
    ) -> List[LangchainYamlTool]:
        all_toolsets = load_builtin_lctoolsets()
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
        lc_tools = []
        for t in enabled_tools:
            lyt = LangchainYamlTool()
            lyt.name = t.name
            lyt.description = t.description
            lyt.yamltool = t
            lyt.args_schema = self.create_pydantic_model(t.get_langchain_tool_args_format())
            print(f'***Tool {lyt.name}, Args: {lyt.args}')
            # lyt.args = t.get_langchain_tool_args_format()
            lc_tools.append(lyt)

        # lc_tools = [LangchainYamlTool(t) for t in enabled_tools]
        logging.debug(
            f"Starting AI session with tools: {[t.name for t in enabled_tools]}"
        )
        return lc_tools
        # return YAMLToolExecutor(enabled_toolsets)

    def create_pydantic_model(self, schema: Dict[str, Dict[str, Any]]) -> Type[BaseModel]:
        fields = {}
        for field_name, field_info in schema.items():
            field_type = str  # 默认字段类型为字符串
            if field_info.get('type') == 'string':
                field_type = str
            elif field_info.get('type') == 'integer':
                field_type = int
            elif field_info.get('type') == 'float':
                field_type = float
            elif field_info.get('type') == 'boolean':
                field_type = bool
            else:
                raise ValueError(
                    f"Unsupported field type: {field_info.get('type')}")

            title = field_info.get('title', field_name)
            fields[field_name] = (field_type, ...)
        return create_model('DynamicModel', **fields)

    def create_pydantic_model2(self, schema: Dict[str, Dict[str, Any]]) -> Type[BaseModel]:
        DynamicModel = create_model(
            "DynamicModel",
            **{field_name: (Field(type_annotation,
                                  default=default) if default is not ... else Field(
                type_annotation))
               for field_name, (type_annotation, default) in
               schema.items()}
        )
        return DynamicModel


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

    def create_issue_lc_investigator(
        self, console: Console, allowed_toolsets: ToolsetPattern
    ) -> LCIssueInvestigator:
        all_runbooks = load_builtin_runbooks()
        for runbook_path in self.custom_runbooks:
            all_runbooks.extend(load_runbooks_from_file(runbook_path))

        runbook_manager = RunbookManager(all_runbooks)
        tools = self._create_lctool_executor_toolset(console, allowed_toolsets)
        # tool_executor = self._create_tool_executor(console, allowed_toolsets)
        return LCIssueInvestigator(
            self.create_langchain_model(),
            self.model,
            tools,
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
        return AlertManagerSource(
            url=self.alertmanager_url,
            username=self.alertmanager_username,
            password=self.alertmanager_password,
            alertname=self.alertmanager_alertname,
            label=self.alertmanager_label,
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
