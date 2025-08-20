import json
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type, Union

from litellm.types.utils import ModelResponse
import sentry_sdk

from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from pydantic import BaseModel
import litellm
import os
from holmes.common.env_vars import (
    REASONING_EFFORT,
    THINKING,
)


def environ_get_safe_int(env_var, default="0"):
    try:
        return max(int(os.environ.get(env_var, default)), 0)
    except ValueError:
        return int(default)


OVERRIDE_MAX_OUTPUT_TOKEN = environ_get_safe_int("OVERRIDE_MAX_OUTPUT_TOKEN")
OVERRIDE_MAX_CONTENT_SIZE = environ_get_safe_int("OVERRIDE_MAX_CONTENT_SIZE")


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
    base_url: Optional[str]
    args: Dict

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        args: Optional[Dict] = None,
        tracer=None,
    ):
        self.model = model
        self.api_key = api_key
        self.args = args or {}
        self.tracer = tracer

        if not self.args:
            self.check_llm(self.model, self.api_key)

    def check_llm(self, model: str, api_key: Optional[str]):
        logging.debug(f"Checking LiteLLM model {model}")
        # TODO: this WAS a hack to get around the fact that we can't pass in an api key to litellm.validate_environment
        # so without this hack it always complains that the environment variable for the api key is missing
        # to fix that, we always set an api key in the standard format that litellm expects (which is ${PROVIDER}_API_KEY)
        # TODO: we can now handle this better - see https://github.com/BerriAI/litellm/issues/4375#issuecomment-2223684750
        lookup = litellm.get_llm_provider(self.model)
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
        elif provider == "bedrock" and os.environ.get("AWS_PROFILE"):
            model_requirements = {"keys_in_environment": True, "missing_keys": []}
        else:
            #
            api_key_env_var = f"{provider.upper()}_API_KEY"
            if api_key:
                os.environ[api_key_env_var] = api_key
            model_requirements = litellm.validate_environment(model=model)

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
        # Get the litellm module to use (wrapped or unwrapped)
        litellm_to_use = self.tracer.wrap_llm(litellm) if self.tracer else litellm

        result = litellm_to_use.completion(
            model=self.model,
            api_key=self.api_key,
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
