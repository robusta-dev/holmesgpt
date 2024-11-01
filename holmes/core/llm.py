
import logging
from abc import abstractmethod
from typing import Dict, List, Optional, Union
from holmes.core.tools import Tool
from pydantic import BaseModel
from litellm import get_supported_openai_params
import litellm
import os
from openai._types import NOT_GIVEN

from holmes.core.tool_calling_llm import LLMResult
from holmes.common.env_vars import ROBUSTA_AI, ROBUSTA_API_ENDPOINT

class LLMCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMCompletionChoice(BaseModel):
    finish_reason: str
    index: int
    message: Dict[str, str]
    role: str
    content: str

class LLMCompletionResult(BaseModel):
    choices: List[LLMCompletionChoice]
    created: str
    model: str
    usage: LLMCompletionUsage

class LLMMessage(BaseModel):
    role: str
    content: str

class LLMToolMessage(LLMMessage, BaseModel):
    tool_call_id: str
    name: str

type ToolChoice = Union[NOT_GIVEN, "auto"]

class LLM:
    model: Optional[str]
    api_key: Optional[str]

    def __init__(
        self,
        model: Optional[str],
        api_key: Optional[str]
    ):
        self.model = model
        self.api_key = api_key

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
    def completion(self, messages: List[Union[LLMMessage, LLMToolMessage]], tools: List[Tool], tool_choice: ToolChoice, response_format) -> LLMCompletionResult:
        pass


class DefaultLLM(LLM):

    base_url: Optional[str]

    def __init__(
        self,
        model: Optional[str],
        api_key: Optional[str]
    ):
        super().__init__(model, api_key)
        self.base_url = None

        if ROBUSTA_AI:
            self.base_url = ROBUSTA_API_ENDPOINT

        self.check_llm(self.model, self.api_key)

    def check_llm(self, model, api_key):
        logging.debug(f"Checking LiteLLM model {model}")
        # TODO: this WAS a hack to get around the fact that we can't pass in an api key to litellm.validate_environment
        # so without this hack it always complains that the environment variable for the api key is missing
        # to fix that, we always set an api key in the standard format that litellm expects (which is ${PROVIDER}_API_KEY)
        # TODO: we can now handle this better - see https://github.com/BerriAI/litellm/issues/4375#issuecomment-2223684750
        lookup = litellm.get_llm_provider(self.model)
        if not lookup:
            raise Exception(f"Unknown provider for model {model}")
        provider = lookup[1]
        api_key_env_var = f"{provider.upper()}_API_KEY"
        if api_key:
            os.environ[api_key_env_var] = api_key
        model_requirements = litellm.validate_environment(model=model)
        if not model_requirements["keys_in_environment"]:
            raise Exception(f"model {model} requires the following environment variables: {model_requirements['missing_keys']}")

    def _strip_model_prefix(self) -> str:
        """
        Helper function to strip 'openai/' prefix from model name if it exists.
        model cost is taken from here which does not have the openai prefix
        https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
        """
        model_name = self.model
        if model_name.startswith('openai/'):
            model_name = model_name[len('openai/'):]  # Strip the 'openai/' prefix
        return model_name


        # this unfortunately does not seem to work for azure if the deployment name is not a well-known model name
        #if not litellm.supports_function_calling(model=model):
        #    raise Exception(f"model {model} does not support function calling. You must use HolmesGPT with a model that supports function calling.")
    def get_context_window_size(self) -> int:
        model_name = self._strip_model_prefix()
        try:
            return litellm.model_cost[model_name]['max_input_tokens']
        except Exception as e:
            logging.warning(f"Couldn't find model's name {model_name} in litellm's model list, fallback to 128k tokens for max_input_tokens")
            return 128000

    def count_tokens_for_message(self, messages: list[dict]) -> int:
        return litellm.token_counter(model=self.model,
                                        messages=messages)

    def get_maximum_output_token(self) -> int:
        model_name = self._strip_model_prefix()
        try:
            return litellm.model_cost[model_name]['max_output_tokens']
        except Exception as e:
            logging.warning(f"Couldn't find model's name {model_name} in litellm's model list, fallback to 4096 tokens for max_output_tokens")
            return 4096
