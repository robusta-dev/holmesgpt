import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type, Union

from litellm.types.utils import ModelResponse

from holmes.core.tools import Tool
from pydantic import BaseModel
import litellm
import os
from holmes.common.env_vars import ROBUSTA_AI, ROBUSTA_API_ENDPOINT


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
        self.model: str

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
        tools: Optional[List[Tool]] = [],
        tool_choice: Optional[Union[str, dict]] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        temperature: Optional[float] = None,
        drop_params: Optional[bool] = None,
    ) -> ModelResponse:
        pass


class DefaultLLM(LLM):
    model: str
    api_key: Optional[str]
    base_url: Optional[str]

    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = None

        if ROBUSTA_AI:
            self.base_url = ROBUSTA_API_ENDPOINT

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
                model_requirements["missing_keys"].append("WATSONX_URL")
                model_requirements["keys_in_environment"] = False
            if "WATSONX_APIKEY" not in os.environ and "WATSONX_TOKEN" not in os.environ:
                model_requirements["missing_keys"].extend(
                    ["WATSONX_APIKEY", "WATSONX_TOKEN"]
                )
                model_requirements["keys_in_environment"] = False
            # WATSONX_PROJECT_ID is required because we don't let user pass it to completion call directly
            if "WATSONX_PROJECT_ID" not in os.environ:
                model_requirements["missing_keys"].append("WATSONX_PROJECT_ID")
                model_requirements["keys_in_environment"] = False
            # https://docs.litellm.ai/docs/providers/watsonx#usage---models-in-deployment-spaces
            # using custom watsonx deployments might require to set WATSONX_DEPLOYMENT_SPACE_ID env
            if "watsonx/deployment/" in self.model:
                logging.warning(
                    "Custom WatsonX deployment detected. You may need to set the WATSONX_DEPLOYMENT_SPACE_ID "
                    "environment variable for proper functionality. For more information, refer to the documentation: "
                    "https://docs.litellm.ai/docs/providers/watsonx#usage---models-in-deployment-spaces"
                )
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

    def _strip_model_prefix(self) -> str:
        """
        Helper function to strip 'openai/' prefix from model name if it exists.
        model cost is taken from here which does not have the openai prefix
        https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
        """
        model_name = self.model
        if model_name.startswith("openai/"):
            model_name = model_name[len("openai/") :]  # Strip the 'openai/' prefix
        elif model_name.startswith("bedrock/"):
            model_name = model_name[len("bedrock/") :]  # Strip the 'bedrock/' prefix
        elif model_name.startswith("vertex_ai/"):
            model_name = model_name[
                len("vertex_ai/") :
            ]  # Strip the 'vertex_ai/' prefix

        return model_name

        # this unfortunately does not seem to work for azure if the deployment name is not a well-known model name
        # if not litellm.supports_function_calling(model=model):
        #    raise Exception(f"model {model} does not support function calling. You must use HolmesGPT with a model that supports function calling.")

    def get_context_window_size(self) -> int:
        if OVERRIDE_MAX_CONTENT_SIZE:
            logging.debug(
                f"Using override OVERRIDE_MAX_CONTENT_SIZE {OVERRIDE_MAX_CONTENT_SIZE}"
            )
            return OVERRIDE_MAX_CONTENT_SIZE

        model_name = os.environ.get("MODEL_TYPE", self._strip_model_prefix())
        try:
            return litellm.model_cost[model_name]["max_input_tokens"]
        except Exception:
            logging.warning(
                f"Couldn't find model's name {model_name} in litellm's model list, fallback to 128k tokens for max_input_tokens"
            )
            return 128000

    def count_tokens_for_message(self, messages: list[dict]) -> int:
        return litellm.token_counter(model=self.model, messages=messages)

    def completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Tool]] = [],
        tool_choice: Optional[Union[str, dict]] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        temperature: Optional[float] = None,
        drop_params: Optional[bool] = None,
    ) -> ModelResponse:

        logging.info("llm.completion()")
        logging.info(f"llm.completion[len(messages)] - {len(messages)}")
        logging.info(f"llm.completion[tools] - {tools}")
        logging.info(f"llm.completion[tool_choice] - {tool_choice}")
        logging.info(f"llm.completion[response_format] - {response_format}")
        logging.info(f"llm.completion[drop_params] - {drop_params}")
        result = litellm.completion(
            model=self.model,
            api_key=self.api_key,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            base_url=self.base_url,
            temperature=temperature,
            response_format=response_format,
            drop_params=drop_params,
        )

        if isinstance(result, ModelResponse):
            return result
        else:
            raise Exception(f"Unexpected type returned by the LLM {type(result)}")

    def get_maximum_output_token(self) -> int:
        if OVERRIDE_MAX_OUTPUT_TOKEN:
            logging.debug(
                f"Using OVERRIDE_MAX_OUTPUT_TOKEN {OVERRIDE_MAX_OUTPUT_TOKEN}"
            )
            return OVERRIDE_MAX_OUTPUT_TOKEN

        model_name = os.environ.get("MODEL_TYPE", self._strip_model_prefix())
        try:
            return litellm.model_cost[model_name]["max_output_tokens"]
        except Exception:
            logging.warning(
                f"Couldn't find model's name {model_name} in litellm's model list, fallback to 4096 tokens for max_output_tokens"
            )
            return 4096
