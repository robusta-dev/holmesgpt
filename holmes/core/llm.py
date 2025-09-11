import json
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type, Union, TYPE_CHECKING

from litellm.types.utils import ModelResponse
import sentry_sdk

from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from pydantic import BaseModel
import litellm
import os
from holmes.clients.robusta_client import RobustaModelsResponse, fetch_robusta_models
from holmes.common.env_vars import (
    LOAD_ALL_ROBUSTA_MODELS,
    REASONING_EFFORT,
    ROBUSTA_AI,
    ROBUSTA_API_ENDPOINT,
    THINKING,
)
from holmes.core.supabase_dal import SupabaseDal
from holmes.utils.env import environ_get_safe_int, replace_env_vars_values
from holmes.utils.file_utils import load_yaml_file

if TYPE_CHECKING:
    from holmes.config import Config

MODEL_LIST_FILE_LOCATION = os.environ.get(
    "MODEL_LIST_FILE_LOCATION", "/etc/holmes/config/model_list.yaml"
)


OVERRIDE_MAX_OUTPUT_TOKEN = environ_get_safe_int("OVERRIDE_MAX_OUTPUT_TOKEN")
OVERRIDE_MAX_CONTENT_SIZE = environ_get_safe_int("OVERRIDE_MAX_CONTENT_SIZE")
ROBUSTA_AI_MODEL_NAME = "Robusta"


class LLM:
    @abstractmethod
    def __init__(self):
        self.model: str  # type: ignore

    @abstractmethod
    def get_context_window_size(self) -> int:
        pass

    @abstractmethod
    def get_maximum_output_token(self) -> int:
        pass

    @abstractmethod
    def count_tokens_for_message(self, messages: list[dict]) -> int:
        pass

    @abstractmethod
    def completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = [],
        tool_choice: Optional[Union[str, dict]] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        temperature: Optional[float] = None,
        drop_params: Optional[bool] = None,
        stream: Optional[bool] = None,
    ) -> Union[ModelResponse, CustomStreamWrapper]:
        pass


class DefaultLLM(LLM):
    model: str
    api_key: Optional[str]
    api_base: Optional[str]
    api_version: Optional[str]
    args: Dict

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        args: Optional[Dict] = None,
        tracer: Optional[Any] = None,
        name: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.args = args or {}
        self.tracer = tracer
        self.name = name

        self.check_llm(self.model, self.api_key, self.api_base, self.api_version)

    def check_llm(
        self,
        model: str,
        api_key: Optional[str],
        api_base: Optional[str],
        api_version: Optional[str],
    ):
        logging.debug(f"Checking LiteLLM model {model}")
        lookup = litellm.get_llm_provider(model)
        if not lookup:
            raise Exception(f"Unknown provider for model {model}")
        provider = lookup[1]
        if provider == "watsonx":
            # NOTE: LiteLLM's validate_environment does not currently include checks for IBM WatsonX.
            # The following WatsonX-specific variables are set based on documentation from:
            # https://docs.litellm.ai/docs/providers/watsonx
            # Required variables for WatsonX:
            # - WATSONX_URL: Base URL of your WatsonX instance (required)
            # - WATSONX_APIKEY or WATSONX_TOKEN: IBM Cloud API key or IAM auth token (one is required)
            model_requirements = {"missing_keys": [], "keys_in_environment": True}
            if api_key:
                os.environ["WATSONX_APIKEY"] = api_key
            if "WATSONX_URL" not in os.environ:
                model_requirements["missing_keys"].append("WATSONX_URL")  # type: ignore
                model_requirements["keys_in_environment"] = False
            if "WATSONX_APIKEY" not in os.environ and "WATSONX_TOKEN" not in os.environ:
                model_requirements["missing_keys"].extend(  # type: ignore
                    ["WATSONX_APIKEY", "WATSONX_TOKEN"]
                )
                model_requirements["keys_in_environment"] = False
            # WATSONX_PROJECT_ID is required because we don't let user pass it to completion call directly
            if "WATSONX_PROJECT_ID" not in os.environ:
                model_requirements["missing_keys"].append("WATSONX_PROJECT_ID")  # type: ignore
                model_requirements["keys_in_environment"] = False
            # https://docs.litellm.ai/docs/providers/watsonx#usage---models-in-deployment-spaces
            # using custom watsonx deployments might require to set WATSONX_DEPLOYMENT_SPACE_ID env
            if "watsonx/deployment/" in self.model:
                logging.warning(
                    "Custom WatsonX deployment detected. You may need to set the WATSONX_DEPLOYMENT_SPACE_ID "
                    "environment variable for proper functionality. For more information, refer to the documentation: "
                    "https://docs.litellm.ai/docs/providers/watsonx#usage---models-in-deployment-spaces"
                )
        elif provider == "bedrock" and (
            os.environ.get("AWS_PROFILE") or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
        ):
            model_requirements = {"keys_in_environment": True, "missing_keys": []}
        else:
            model_requirements = litellm.validate_environment(
                model=model, api_key=api_key, api_base=api_base
            )
            # validate_environment does not accept api_version, and as a special case for Azure OpenAI Service,
            # when all the other AZURE environments are set expect AZURE_API_VERSION, validate_environment complains
            # the missing of it even after the api_version is set.
            # TODO: There's an open PR in litellm to accept api_version in validate_environment, we can leverage this
            # change if accepted to ignore the following check.
            # https://github.com/BerriAI/litellm/pull/13808
            if (
                provider == "azure"
                and ["AZURE_API_VERSION"] == model_requirements["missing_keys"]
                and api_version is not None
            ):
                model_requirements["missing_keys"] = []
                model_requirements["keys_in_environment"] = True

        if not model_requirements["keys_in_environment"]:
            raise Exception(
                f"model {model} requires the following environment variables: {model_requirements['missing_keys']}"
            )

    def _get_model_name_variants_for_lookup(self) -> list[str]:
        """
        Generate model name variants to try when looking up in litellm.model_cost.
        Returns a list of names to try in order: exact, lowercase, without prefix, etc.
        """
        names_to_try = [self.model, self.model.lower()]

        # If there's a prefix, also try without it
        if "/" in self.model:
            base_model = self.model.split("/", 1)[1]
            names_to_try.extend([base_model, base_model.lower()])

        # Remove duplicates while preserving order (dict.fromkeys maintains insertion order in Python 3.7+)
        return list(dict.fromkeys(names_to_try))

    def get_context_window_size(self) -> int:
        if OVERRIDE_MAX_CONTENT_SIZE:
            logging.debug(
                f"Using override OVERRIDE_MAX_CONTENT_SIZE {OVERRIDE_MAX_CONTENT_SIZE}"
            )
            return OVERRIDE_MAX_CONTENT_SIZE

        # Try each name variant
        for name in self._get_model_name_variants_for_lookup():
            try:
                return litellm.model_cost[name]["max_input_tokens"]
            except Exception:
                continue

        # Log which lookups we tried
        logging.warning(
            f"Couldn't find model {self.model} in litellm's model list (tried: {', '.join(self._get_model_name_variants_for_lookup())}), "
            f"using default 128k tokens for max_input_tokens. "
            f"To override, set OVERRIDE_MAX_CONTENT_SIZE environment variable to the correct value for your model."
        )
        return 128000

    @sentry_sdk.trace
    def count_tokens_for_message(self, messages: list[dict]) -> int:
        total_token_count = 0
        for message in messages:
            if "token_count" in message and message["token_count"]:
                total_token_count += message["token_count"]
            else:
                # message can be counted by this method only if message contains a "content" key
                if "content" in message:
                    if isinstance(message["content"], str):
                        message_to_count = [
                            {"type": "text", "text": message["content"]}
                        ]
                    elif isinstance(message["content"], list):
                        message_to_count = [
                            {"type": "text", "text": json.dumps(message["content"])}
                        ]
                    elif isinstance(message["content"], dict):
                        if "type" not in message["content"]:
                            message_to_count = [
                                {"type": "text", "text": json.dumps(message["content"])}
                            ]
                    token_count = litellm.token_counter(
                        model=self.model, messages=message_to_count
                    )
                    message["token_count"] = token_count
                    total_token_count += token_count
        return total_token_count

    def completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, dict]] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        temperature: Optional[float] = None,
        drop_params: Optional[bool] = None,
        stream: Optional[bool] = None,
    ) -> Union[ModelResponse, CustomStreamWrapper]:
        tools_args = {}
        allowed_openai_params = None

        if tools and len(tools) > 0 and tool_choice == "auto":
            tools_args["tools"] = tools
            tools_args["tool_choice"] = tool_choice  # type: ignore

        if THINKING:
            self.args.setdefault("thinking", json.loads(THINKING))

        if self.args.get("thinking", None):
            litellm.modify_params = True

        if REASONING_EFFORT:
            self.args.setdefault("reasoning_effort", REASONING_EFFORT)
            allowed_openai_params = [
                "reasoning_effort"
            ]  # can be removed after next litelm version

        self.args.setdefault("temperature", temperature)

        self._add_cache_control_to_last_message(messages)

        # Get the litellm module to use (wrapped or unwrapped)
        litellm_to_use = self.tracer.wrap_llm(litellm) if self.tracer else litellm
        result = litellm_to_use.completion(
            model=self.model,
            api_key=self.api_key,
            base_url=self.api_base,
            api_version=self.api_version,
            messages=messages,
            response_format=response_format,
            drop_params=drop_params,
            allowed_openai_params=allowed_openai_params,
            stream=stream,
            **tools_args,
            **self.args,
        )

        if isinstance(result, ModelResponse):
            return result
        elif isinstance(result, CustomStreamWrapper):
            return result
        else:
            raise Exception(f"Unexpected type returned by the LLM {type(result)}")

    def get_maximum_output_token(self) -> int:
        if OVERRIDE_MAX_OUTPUT_TOKEN:
            logging.debug(
                f"Using OVERRIDE_MAX_OUTPUT_TOKEN {OVERRIDE_MAX_OUTPUT_TOKEN}"
            )
            return OVERRIDE_MAX_OUTPUT_TOKEN

        # Try each name variant
        for name in self._get_model_name_variants_for_lookup():
            try:
                return litellm.model_cost[name]["max_output_tokens"]
            except Exception:
                continue

        # Log which lookups we tried
        logging.warning(
            f"Couldn't find model {self.model} in litellm's model list (tried: {', '.join(self._get_model_name_variants_for_lookup())}), "
            f"using default 4096 tokens for max_output_tokens. "
            f"To override, set OVERRIDE_MAX_OUTPUT_TOKEN environment variable to the correct value for your model."
        )
        return 4096

    def _add_cache_control_to_last_message(
        self, messages: List[Dict[str, Any]]
    ) -> None:
        """
        Add cache_control to the last non-user message for Anthropic prompt caching.
        Removes any existing cache_control from previous messages to avoid accumulation.
        """
        # First, remove any existing cache_control from all messages
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "cache_control" in block:
                        del block["cache_control"]
                        logging.debug(
                            f"Removed existing cache_control from {msg.get('role')} message"
                        )

        # Find the last non-user message to add cache_control to.
        # Adding cache_control to user message requires changing its structure, so we avoid it
        # This avoids breaking parse_messages_tags which only processes user messages
        target_msg = None
        for msg in reversed(messages):
            if msg.get("role") != "user":
                target_msg = msg
                break

        if not target_msg:
            logging.debug("No non-user message found for cache_control")
            return

        content = target_msg.get("content")

        if content is None:
            return

        if isinstance(content, str):
            # Convert string to structured format with cache_control
            target_msg["content"] = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            logging.debug(
                f"Added cache_control to {target_msg.get('role')} message (converted from string)"
            )
        elif isinstance(content, list) and content:
            # Add cache_control to the last content block
            last_block = content[-1]
            if isinstance(last_block, dict) and "type" in last_block:
                last_block["cache_control"] = {"type": "ephemeral"}
                logging.debug(
                    f"Added cache_control to {target_msg.get('role')} message (structured content)"
                )


class LLMModelRegistry:
    def __init__(self, config: "Config", dal: SupabaseDal) -> None:
        self.config = config
        self._llms: dict[str, dict[str, Any]] = {}
        self._default_robusta_model = None
        self.dal = dal

        self._init_models()

    @property
    def default_robusta_model(self) -> Optional[str]:
        return self._default_robusta_model

    def _init_models(self):
        self._llms = self._parse_models_file(MODEL_LIST_FILE_LOCATION)

        if self._should_load_robusta_ai():
            self.configure_robusta_ai_model()

        if self._should_load_config_model():
            self._llms[self.config.model] = self._create_model_entry(
                model=self.config.model,
                model_name=self.config.model,
                base_url=self.config.api_base,
                is_robusta_model=False,
            )

    def _should_load_config_model(self) -> bool:
        if self.config.model is not None:
            return True

        # backward compatibility - in the past config.model was set by default to gpt-4o.
        # so we need to check if the user has set an OPENAI_API_KEY to load the config model.
        has_openai_key = os.environ.get("OPENAI_API_KEY")
        if has_openai_key:
            self.config.model = "gpt-4o"
            return True

        return False

    def configure_robusta_ai_model(self) -> None:
        try:
            if not self.config.cluster_name or not LOAD_ALL_ROBUSTA_MODELS:
                self._load_default_robusta_config()
                return

            if not self.dal.account_id or not self.dal.enabled:
                self._load_default_robusta_config()
                return

            account_id, token = self.dal.get_ai_credentials()
            robusta_models: RobustaModelsResponse | None = fetch_robusta_models(
                account_id, token
            )
            if not robusta_models or not robusta_models.models:
                self._load_default_robusta_config()
                return

            for model in robusta_models.models:
                logging.info(f"Loading Robusta AI model: {model}")
                self._llms[model] = self._create_robusta_model_entry(model)

            if robusta_models.default_model:
                logging.info(
                    f"Setting default Robusta AI model to: {robusta_models.default_model}"
                )
                self._default_robusta_model: str = robusta_models.default_model  # type: ignore

        except Exception:
            logging.exception("Failed to get all robusta models")
            # fallback to default behavior
            self._load_default_robusta_config()

    def _load_default_robusta_config(self):
        if self._should_load_robusta_ai():
            logging.info("Loading default Robusta AI model")
            self._llms[ROBUSTA_AI_MODEL_NAME] = {
                "name": ROBUSTA_AI_MODEL_NAME,
                "base_url": ROBUSTA_API_ENDPOINT,
                "is_robusta_model": True,
                "model": "gpt-4o",
            }
            self._default_robusta_model = ROBUSTA_AI_MODEL_NAME

    def _should_load_robusta_ai(self) -> bool:
        if not self.config.should_try_robusta_ai:
            return False

        # ROBUSTA_AI were set in the env vars, so we can use it directly
        if ROBUSTA_AI is not None:
            return ROBUSTA_AI

        # MODEL is set in the env vars, e.g. the user is using a custom model
        # so we don't need to load the robusta AI model and keep the behavior backward compatible
        if "MODEL" in os.environ:
            return False

        # if the user has provided a model list, we don't need to load the robusta AI model
        if self._llms:
            return False

        return True

    def get_model_params(self, model_key: Optional[str] = None) -> dict:
        if not self._llms:
            raise Exception("No llm models were loaded")

        if model_key:
            model_params = self._llms.get(model_key)
            if model_params is not None:
                logging.info(f"Using selected model: {model_key}")
                return model_params.copy()

            logging.error(f"Couldn't find model: {model_key} in model list")

        if self._default_robusta_model:
            model_params = self._llms.get(self._default_robusta_model)
            if model_params is not None:
                logging.info(
                    f"Using default Robusta AI model: {self._default_robusta_model}"
                )
                return model_params.copy()

            logging.error(
                f"Couldn't find default Robusta AI model: {self._default_robusta_model} in model list"
            )

        model_key, first_model_params = next(iter(self._llms.items()))
        logging.info(f"Using first available model: {model_key}")
        return first_model_params.copy()

    def get_llm(self, name: str) -> LLM:  # TODO: fix logic
        return self._llms[name]  # type: ignore

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self._llms

    def _parse_models_file(self, path: str):
        models = load_yaml_file(path, raise_error=False, warn_not_found=False)
        for _, params in models.items():
            params = replace_env_vars_values(params)

        return models

    def _create_robusta_model_entry(self, model_name: str) -> dict[str, Any]:
        return self._create_model_entry(
            model="gpt-4o",  # Robusta AI model is using openai like API.
            model_name=model_name,
            base_url=f"{ROBUSTA_API_ENDPOINT}/llm/{model_name}",
            is_robusta_model=True,
        )

    def _create_model_entry(
        self,
        model: str,
        model_name: str,
        base_url: Optional[str] = None,
        is_robusta_model: Optional[bool] = None,
    ) -> dict[str, Any]:
        return {
            "name": model_name,
            "base_url": base_url,
            "is_robusta_model": is_robusta_model,
            "model": model,
        }
