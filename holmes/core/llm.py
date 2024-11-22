
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type, Union
from azure.identity import get_bearer_token_provider, DefaultAzureCredential

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
    def get_context_window_size(self) -> int:
        pass

    @abstractmethod
    def get_maximum_output_token(self) -> int:
        pass

    @abstractmethod
    def count_tokens_for_message(self, messages: list[dict]) -> int:
        pass

    @abstractmethod
    def completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Tool]] = [], tool_choice: Optional[Union[str, dict]] = None, response_format: Optional[Union[dict, Type[BaseModel]]] = None, temperature:Optional[float] = None, drop_params: Optional[bool] = None) -> ModelResponse:
        pass


def get_lite_llm_config(api_key:Optional[str], base_url:Optional[str]) -> Dict[str, Any]:

    if os.environ.get("HOLMES_FORCE_AZURE_LITELLM_VARS"):
        litellm_config:Dict[str, Any] = {
            "api_version": os.environ.get("AZURE_API_VERSION"),
            "api_base": os.environ.get("AZURE_API_BASE"),
            "tenant_id": os.environ.get("AZURE_TENANT_ID"),
            "client_id": os.environ.get("AZURE_CLIENT_ID"),
            "client_secret": os.environ.get("AZURE_CLIENT_SECRET"),
        }
        azure_ad_token = os.environ.get("AZURE_AD_TOKEN")
        if azure_ad_token:
            litellm_config["azure_ad_token"] = azure_ad_token

        azure_ad_token_provider_url = os.environ.get("AZURE_OID_PROVIDER") # AZURE_OID_PROVIDER="https://cognitiveservices.azure.com/.default"
        if azure_ad_token_provider_url:
            litellm_config["azure_ad_token_provider"] = get_bearer_token_provider(DefaultAzureCredential(), azure_ad_token_provider_url)
        return litellm_config
    if os.environ.get("AZURE_API_BASE"):
        # Let litellm read environment variables
        return {}

    return {
        "api_key": api_key,
        "base_url": base_url
    }


class DefaultLLM(LLM):

    model: str
    api_key: Optional[str]
    base_url: Optional[str]

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = None

        if ROBUSTA_AI:
            self.base_url = ROBUSTA_API_ENDPOINT

        self.check_llm(self.model, self.api_key)

    def check_llm(self, model:str, api_key:Optional[str]):
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
            logging.warning(f"model {model} requires the following environment variables: {model_requirements['missing_keys']}")

    def _strip_model_prefix(self) -> str:
        """
        Helper function to strip 'openai/' prefix from model name if it exists.
        model cost is taken from here which does not have the openai prefix
        https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
        """
        model_name = self.model
        if model_name.startswith('openai/'):
            model_name = model_name[len('openai/'):]  # Strip the 'openai/' prefix
        elif model_name.startswith('bedrock/'):
            model_name = model_name[len('bedrock/'):]  # Strip the 'bedrock/' prefix

        return model_name


        result = litellm.completion(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            response_format=response_format,
            drop_params=drop_params,
            **get_lite_llm_config(api_key=self.api_key, base_url=self.base_url)
        )# this unfortunately does not seem to work for azure if the deployment name is not a well-known model name
        #if not litellm.supports_function_calling(model=model):
        #    raise Exception(f"model {model} does not support function calling. You must use HolmesGPT with a model that supports function calling.")
    def get_context_window_size(self) -> int:
        if OVERRIDE_MAX_CONTENT_SIZE:
            logging.debug(f"Using override OVERRIDE_MAX_CONTENT_SIZE {OVERRIDE_MAX_CONTENT_SIZE}")
            return OVERRIDE_MAX_CONTENT_SIZE

        model_name = os.environ.get("MODEL_TYPE", self._strip_model_prefix())
        try:
            return litellm.model_cost[model_name]['max_input_tokens']
        except Exception:
            logging.warning(f"Couldn't find model's name {model_name} in litellm's model list, fallback to 128k tokens for max_input_tokens")
            return 128000

    def count_tokens_for_message(self, messages: list[dict]) -> int:
        return litellm.token_counter(model=self.model,
                                        messages=messages)

    def completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Tool]] = [], tool_choice: Optional[Union[str, dict]] = None, response_format: Optional[Union[dict, Type[BaseModel]]] = None, temperature:Optional[float] = None, drop_params: Optional[bool] = None) -> ModelResponse:
        result = litellm.completion(
            # model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            response_format=response_format,
            drop_params=drop_params,

            model="azure/prod-robusta-ai",
            api_version= "2024-06-01",
            api_base= "https://robustagpttest.openai.azure.com",
            tenant_id="00831b2d-a453-47eb-b06d-317841d875e5",
            client_secret="5bdab1c1-1360-4c69-ad7e-8741aca365f6",
            client_id="e6b88819-3883-4183-b7fa-cb9965bc6925",
            # azure_ad_token_provider=get_azure_ad_token_provider(),
            azure_ad_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6Inp4ZWcyV09OcFRrd041R21lWWN1VGR0QzZKMCIsImtpZCI6Inp4ZWcyV09OcFRrd041R21lWWN1VGR0QzZKMCJ9.eyJhdWQiOiJodHRwczovL2NvZ25pdGl2ZXNlcnZpY2VzLmF6dXJlLmNvbSIsImlzcyI6Imh0dHBzOi8vc3RzLndpbmRvd3MubmV0LzAwODMxYjJkLWE0NTMtNDdlYi1iMDZkLTMxNzg0MWQ4NzVlNS8iLCJpYXQiOjE3MzIyNzIwMTQsIm5iZiI6MTczMjI3MjAxNCwiZXhwIjoxNzMyMjc2NTgyLCJhY3IiOiIxIiwiYWlvIjoiQVZRQXEvOFlBQUFBc1E2K0pMRjNaUlYxNHdGZ0RnVlVTY2o4SndnZlVucGN1dzZjWUsxdFFadXpBV3ljK3dmbmgzbVhRVHBDMlBqMUhmMWM3Z3pOQ3FubHVxcVE3a2F0WWg1V2ZNYnRiZUhVUXFQMXFpcVhkeDg9IiwiYW1yIjpbInB3ZCIsIm1mYSJdLCJhcHBpZCI6IjA0YjA3Nzk1LThkZGItNDYxYS1iYmVlLTAyZjllMWJmN2I0NiIsImFwcGlkYWNyIjoiMCIsImdyb3VwcyI6WyJlYjdlN2FhYS0yNTlhLTQ2NTQtYTAzZC0yODI3YzI0MmM1Y2EiXSwiaWR0eXAiOiJ1c2VyIiwiaXBhZGRyIjoiMTg4LjE1MS4xNjAuNDMiLCJuYW1lIjoibmljb2xhcyIsIm9pZCI6ImJlY2QyYzEzLTA4MWMtNDY5OS05NDdiLTUxYTdhOGVhOGJiZiIsInB1aWQiOiIxMDAzMjAwM0Y1NzQyNDY3IiwicmgiOiIxLkFYa0FMUnVEQUZPazYwZXdiVEY0UWRoMTVaQWlNWDNJS0R4SG9PMk9VM1NiYlcwTUFVMTVBQS4iLCJzY3AiOiJ1c2VyX2ltcGVyc29uYXRpb24iLCJzdWIiOiIwSlF1NlRyOGRBOFh5d2didHRZWmpGamo5QTZOM09vX3g4MEZsdFV3YmcwIiwidGlkIjoiMDA4MzFiMmQtYTQ1My00N2ViLWIwNmQtMzE3ODQxZDg3NWU1IiwidW5pcXVlX25hbWUiOiJuaWNvbGFzQHJvYnVzdGEuZGV2IiwidXBuIjoibmljb2xhc0Byb2J1c3RhLmRldiIsInV0aSI6IlROaVg1X09VQjBTUzgwQTk4TnBRQUEiLCJ2ZXIiOiIxLjAiLCJ3aWRzIjpbIjYyZTkwMzk0LTY5ZjUtNDIzNy05MTkwLTAxMjE3NzE0NWUxMCIsImI3OWZiZjRkLTNlZjktNDY4OS04MTQzLTc2YjE5NGU4NTUwOSJdLCJ4bXNfaWRyZWwiOiIxIDIwIn0.eQo1nYNt9jZwi_lR6bPfn0XT6RBp4gAQ7AE5mD1EzusSSzSIlXpMVAGGSZGpd07spvs5CO8AYhIcVKiErb2fuKn9B1WyNvmMVkQbkFd3PdtCXgcrY3h9h-_UPF2umMiqtMKLQfSVDPgTKw-Igd4fFaBhckJiXFLmX8yAOdRGEte_GrwUU670s8_8my5QI82Zm8diiiJ-twecpnQXCeyDk4S7XNpVv3BK0yqN00-haO87DcFm9250WvFOHa8MDVxf8iunQTPNqequFmHVycqP22UuC-8d5BUa4TfzEw5Lz8oTXheSvpoX5mpE1rjT8O-pg-keJfHMZDUbBtBHBFLr0g"


        )



        if isinstance(result, ModelResponse):
            response = result.choices[0]
            response_message = response.message
            # when asked to run tools, we expect no response other than the request to run tools unless bedrock
            if response_message.content and ('bedrock' not in self.model and logging.DEBUG != logging.root.level):
                logging.warning(f"got unexpected response when tools were given: {response_message.content}")
            return result
        else:
            raise Exception(f"Unexpected type returned by the LLM {type(result)}")

    def get_maximum_output_token(self) -> int:
        if OVERRIDE_MAX_OUTPUT_TOKEN:
            logging.debug(f"Using OVERRIDE_MAX_OUTPUT_TOKEN {OVERRIDE_MAX_OUTPUT_TOKEN}")
            return OVERRIDE_MAX_OUTPUT_TOKEN

        model_name = os.environ.get("MODEL_TYPE", self._strip_model_prefix())
        try:
            return litellm.model_cost[model_name]['max_output_tokens']
        except Exception:
            logging.warning(f"Couldn't find model's name {model_name} in litellm's model list, fallback to 4096 tokens for max_output_tokens")
            return 4096
