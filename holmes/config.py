import logging
import os
import os.path
from strenum import StrEnum
from typing import Annotated, Any, Dict, List, Optional, get_args, get_origin, get_type_hints

from pydantic import SecretStr, FilePath
from holmes.utils.pydantic_utils import BaseConfig, EnvVarName, load_model_from_file


class LLMProviderType(StrEnum):
    OPENAI = "openai"
    AZURE = "azure"
    ROBUSTA = "robusta_ai"


class BaseLLMConfig(BaseConfig):
    llm_provider: LLMProviderType = LLMProviderType.OPENAI

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
            if field_name == "llm_provider":
                # Handled in load_from_env
                continue
            tp_obj = hints[field_name]
            if get_origin(tp_obj) is Annotated:
                tp_args = get_args(tp_obj)
                base_type = tp_args[0]
                for arg in tp_args[1:]:
                    if isinstance(arg, EnvVarName):
                        env_var_name = arg
                        break
                else:  # no EnvVarName(...) in annotations
                    env_var_name = field_name.upper()
            else:
                base_type = tp_obj
                env_var_name = field_name.upper()
            if env_var_name in os.environ:
                env_value = os.environ[env_var_name]
                if get_origin(base_type) == list:
                    value = [value.strip() for value in env_value.split(",")]
                else:
                    value = env_value
                vars_dict[field_name] = value
        return vars_dict

    @classmethod
    def load_from_env(cls) -> "BaseLLMConfig":
        llm_name = os.environ.get("LLM_PROVIDER", "OPENAI").lower()
        llm_provider = LLMProviderType(llm_name)
        if llm_provider == LLMProviderType.AZURE:
            final_class = AzureLLMConfig
        elif llm_provider == LLMProviderType.OPENAI:
            final_class = OpenAILLMConfig
        elif llm_provider == LLMProviderType.ROBUSTA:
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

    @classmethod
    def load_from_file(cls, config_file: Optional[str], **kwargs) -> "BaseLLMConfig":
        # FIXME!
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
            k: v for k, v in config_from_cli.model_dump().items() if v is not None and v != []
        }
        merged_config.update(cli_overrides)
        return cls(**merged_config)


class BaseOpenAIConfig(BaseLLMConfig):
    model: Annotated[Optional[str], EnvVarName("AI_MODEL")] = "gpt-4o"
    max_steps: Optional[int] = 10


class OpenAILLMConfig(BaseOpenAIConfig):
    api_key: Annotated[Optional[SecretStr], EnvVarName("OPENAI_API_KEY")]


class AzureLLMConfig(BaseOpenAIConfig):
    api_key: Annotated[Optional[SecretStr], EnvVarName("AZURE_API_KEY")]
    endpoint: Annotated[Optional[str], EnvVarName("AZURE_ENDPOINT")]
    azure_api_version: Optional[str] = "2024-02-01"


class RobustaLLMConfig(BaseOpenAIConfig):
    url: Annotated[str, EnvVarName("ROBUSTA_AI_URL")]
