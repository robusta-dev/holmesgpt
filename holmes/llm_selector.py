import logging
from typing import Any, Dict, Optional

from holmes.core.llm import DefaultLLM, LLM
from holmes.common.env_vars import (
    ROBUSTA_AI,
    ROBUSTA_AI_MODEL_NAME_FALLBACK,
    ROBUSTA_API_ENDPOINT,
)


class LLMSelector:
    def __init__(
        self,
        initial_api_key: Optional[str],
        model_list_config: Optional[Dict[str, Dict[str, Any]]],
        default_model_from_config: Optional[str],
        holmes_info_object: Optional[Any],
    ):
        self.initial_api_key = initial_api_key
        self.model_list_config = model_list_config
        self.default_model_from_config = default_model_from_config
        self.holmes_info_object = holmes_info_object

    def select_llm(self, model_key: Optional[str] = None) -> LLM:
        selected_model_name: Optional[str] = None
        selected_api_key: Optional[str] = self.initial_api_key
        selected_params: Dict[str, Any] = {}

        # 1) If caller asked for a specific key and it's in model_list:
        if model_key and self.model_list_config and model_key in self.model_list_config:
            logging.debug(f"Using model '{model_key}' from model_list.")
            selected_params = self.model_list_config[model_key].copy()
            selected_api_key = selected_params.pop("api_key", selected_api_key)
            selected_model_name = selected_params.pop(
                "model", self.default_model_from_config
            )

        # 2) If Config provided a model (e.g. via CLI/ENV):
        elif self.default_model_from_config:
            logging.debug(
                f"Using model '{self.default_model_from_config}' from default_model_from_config."
            )
            selected_model_name = self.default_model_from_config
            selected_params = {}

        # 3) If there's a model_list, take the first key (ensure list is not empty):
        elif self.model_list_config and len(self.model_list_config) > 0:
            first_key = next(iter(self.model_list_config.keys()))
            logging.debug(
                f"No explicit model; defaulting to first in model_list: '{first_key}'"
            )
            selected_params = self.model_list_config[first_key].copy()
            selected_api_key = selected_params.pop("api_key", selected_api_key)
            selected_model_name = selected_params.pop(
                "model", self.default_model_from_config
            )

        # 4) Finally, if ROBUSTA_AI is on, fallback:
        elif ROBUSTA_AI:
            logging.debug("No model or model_list; falling back to Robusta AI.")

            if not selected_api_key:
                raise ValueError(
                    "ROBUSTA_AI is enabled but no API key is configured. "
                    "Ensure an API key is provided to LLMSelector or via Robusta configuration."
                )

            if not self.holmes_info_object:
                logging.warning(
                    "Robusta AI fallback attempted but holmes_info_object is not available."
                )
                raise ValueError(
                    "Cannot determine Robusta AI model name: holmes_info_object not available."
                )

            selected_model_name = getattr(
                self.holmes_info_object,
                "robusta_ai_model_name",
                ROBUSTA_AI_MODEL_NAME_FALLBACK,
            )
            selected_params = {"base_url": ROBUSTA_API_ENDPOINT}

        else:
            raise ValueError(
                "No LLM model configuration provided to LLMSelector. "
                "Please ensure model parameters are passed correctly or ROBUSTA_AI is enabled and configured."
            )

        if not selected_model_name:
            raise ValueError("Could not determine an LLM model name to use.")

        return DefaultLLM(selected_model_name, selected_api_key, selected_params)
