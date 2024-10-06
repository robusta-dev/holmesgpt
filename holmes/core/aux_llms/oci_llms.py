from typing import List, Optional, Dict
import oci
import os
import json
from oci.generative_ai_inference.models import CohereTool, CohereParameterDefinition, CohereToolCall, CohereSystemMessage, CohereUserMessage, CohereToolResult
from pydantic import BaseModel
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

class Message(BaseModel):
    content: str
    tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None

class Choice(BaseModel):
    message: Message

class LiteLLMResponse(BaseModel):
    choices: List[Choice]

class ModelSupportException(Exception):
    pass

class OCILLM:
    supported_models = ['oci/cohere.command-r-plus', 'oci/cohere.command-r-16k']

    def __init__(self):
        # Get values from environment variables, with defaults if not set
        self.config_profile = os.environ.get("OCI_CONFIG_PROFILE", "DEFAULT")  # Default profile if not set
        self.endpoint = os.environ.get("OCI_ENDPOINT", None)
        self.model_id = os.environ.get("OCI_MODEL_ID", None)
        self.compartment_id = os.environ.get("OCI_COMPARTMENT_ID", None)

        # Ensure required OCI environment variables are set
        self.check_llm()

        # Load OCI config
        self.config = oci.config.from_file('~/.oci/config', self.config_profile)

        # Set up the Generative AI client
        self.generative_ai_inference_client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=self.config,
            service_endpoint=self.endpoint,
            retry_strategy=oci.retry.NoneRetryStrategy(),
            timeout=(10, 240)
        )

    def _convert_parameters(self, parameters) -> Dict[str, CohereParameterDefinition]:
        parameter_definitions = {}
        for param_name, param_properties in parameters['properties'].items():
            parameter_definitions[param_name] = CohereParameterDefinition(
                description=f"Parameter {param_name} of type {param_properties['type']}",
                type=param_properties['type'],
                is_required=param_name in parameters.get('required', [])
            )
        return parameter_definitions

    def _make_jsonable(self, obj) -> str:
        try:
            return json.dumps(obj)
        except (TypeError, ValueError):
            return str(obj)

    def _process_oci_response(self, full_response: oci.response.Response) -> LiteLLMResponse:
        """
            Converts from oci.response.Response to the response format of LiteLLMResponse 
        """
        chat_response = full_response.data.chat_response
        tool_calls = []
        if chat_response.tool_calls:
            for tc in chat_response.tool_calls:
                function = Function(name=tc.name, arguments=self._make_jsonable(tc.parameters))
                tool_call = ChatCompletionMessageToolCall(
                    id=tc.name,
                    function=function,
                    type="function"
                )
                tool_calls.append(tool_call)

        message = Message(content=chat_response.text, tool_calls=tool_calls)
        choice = Choice(message=message)
        return LiteLLMResponse(choices=[choice])

    def _convert_to_chat_history(self, messages: List[Dict]) -> List[oci.generative_ai_inference.models.CohereMessage]:
        chat_history = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                system_message = CohereSystemMessage(role=CohereSystemMessage.ROLE_SYSTEM, message=message.get("content"))
                chat_history.append(system_message)
            elif role == "user":
                user_message = CohereUserMessage(role=CohereUserMessage.ROLE_USER, message=message.get("content"))
                chat_history.append(user_message)
        return chat_history

    def _convert_to_tool_results(self, messages: List[dict]) -> Optional[List[CohereToolResult]]:
        tool_results = []
        for message in messages:
            if message.get("role") == "tool":
                cohere_tool = CohereToolCall(name=message['name'], parameters={})
                tool_result = CohereToolResult(call=cohere_tool, outputs=[{"content": message.get("content")}])
                tool_results.append(tool_result)
        return tool_results if tool_results else None

    def oci_chat(self, message: str, messages: List, model: str, tools: Optional[List], temperature: float) -> LiteLLMResponse:
        chat_detail = oci.generative_ai_inference.models.ChatDetails()
        chat_request = oci.generative_ai_inference.models.CohereChatRequest()
        chat_request.message = message
        chat_request.chat_history = self._convert_to_chat_history(messages)
        chat_request.max_tokens = self.get_maximum_output_token(model)
        chat_request.tool_results = self._convert_to_tool_results(messages)
        chat_request.is_force_single_step = True
        chat_request.temperature = temperature

        cohere_tools = []
        if tools:
            for tool in tools:
                tool_function = tool["function"]
                parameter_definitions = self._convert_parameters(tool_function['parameters'])
                cohere_tool = CohereTool(
                    name=tool_function['name'],
                    description=tool_function['description'],
                    parameter_definitions=parameter_definitions
                )
                cohere_tools.append(cohere_tool)

        chat_request.tools = cohere_tools
        chat_detail.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(model_id=self.model_id)
        chat_detail.chat_request = chat_request
        chat_detail.compartment_id = self.compartment_id

        chat_response = self.generative_ai_inference_client.chat(chat_detail)
        return self._process_oci_response(chat_response)

    @staticmethod
    def supports_llm(model: str) -> bool:
        # Check if the model is supported
        if 'oci' not in model.lower():
            return False

        if model in OCILLM.supported_models:
            return True
        else:
            # Raise an exception if it is oci but model is not supported like 'oci/llama'
            raise ModelSupportException(f"Unsupported model: {model}. Supported models are: {', '.join(OCILLM.supported_models)}")

    @staticmethod
    def check_llm() -> bool:
        """
            Verifies all the env vars exist to run the LLM
        """
        required_vars = ["OCI_MODEL_ID", "OCI_COMPARTMENT_ID", "OCI_ENDPOINT"]
        missing_vars = [var for var in required_vars if var not in os.environ]
        if missing_vars:
            raise Exception(f"Missing required environment variables: {', '.join(missing_vars)}")

        return True

    @staticmethod
    def get_context_window_size(model) -> int:
        if "cohere.command-r-plus" in model:
            return 128000
        elif 'cohere.command-r-16k' in model:
            return 16000
        raise ModelSupportException(f"Unsupported model: {model}. Supported models are: {', '.join(OCILLM.supported_models)}")

    @staticmethod
    def get_maximum_output_token(model) -> int:
        if "cohere.command-r-plus" in model or 'cohere.command-r-16k' in model:
            return 4000
        raise ModelSupportException(f"Unsupported model: {model}. Supported models are: {', '.join(OCILLM.supported_models)}")