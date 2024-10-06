from typing import List, Optional
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

class OCIResponse(BaseModel):
    choices: List[Choice]

class OCILLM:
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

    def convert_parameters(self, parameters):
        parameter_definitions = {}
        for param_name, param_properties in parameters['properties'].items():
            parameter_definitions[param_name] = CohereParameterDefinition(
                description=f"Parameter {param_name} of type {param_properties['type']}",
                type=param_properties['type'],
                is_required=param_name in parameters.get('required', [])
            )
        return parameter_definitions

    def make_jsonable(self, obj):
        try:
            return json.dumps(obj)
        except (TypeError, ValueError):
            return str(obj)

    def process_oci_response(self, full_response):
        chat_response = full_response.data.chat_response
        tool_calls = []
        if chat_response.tool_calls:
            for tc in chat_response.tool_calls:
                function = Function(name=tc.name, arguments=self.make_jsonable(tc.parameters))
                tool_call = ChatCompletionMessageToolCall(
                    id=tc.name,
                    function=function,
                    type="function"
                )
                tool_calls.append(tool_call)

        message = Message(content=chat_response.text, tool_calls=tool_calls)
        choice = Choice(message=message)
        return OCIResponse(choices=[choice])

    def convert_to_chat_history(self, messages: List[dict]):
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

    def convert_to_tool_results(self, messages: List[dict]):
        tool_results = []
        for message in messages:
            if message.get("role") == "tool":
                cohere_tool = CohereToolCall(name=message['name'], parameters={})
                tool_result = CohereToolResult(call=cohere_tool, outputs=[{"content": message.get("content")}])
                tool_results.append(tool_result)
        return tool_results if tool_results else None

    def oci_chat(self, message, messages, tools):
        chat_detail = oci.generative_ai_inference.models.ChatDetails()
        chat_request = oci.generative_ai_inference.models.CohereChatRequest()
        chat_request.message = message
        chat_request.chat_history = self.convert_to_chat_history(messages)
        chat_request.max_tokens = 2000
        chat_request.temperature = 0.25
        chat_request.frequency_penalty = 0
        chat_request.top_p = 0.75
        chat_request.top_k = 0
        chat_request.tool_results = self.convert_to_tool_results(messages)
        chat_request.is_force_single_step = True

        cohere_tools = []
        if tools:
            for tool in tools:
                tool_function = tool["function"]
                parameter_definitions = self.convert_parameters(tool_function['parameters'])
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
        return self.process_oci_response(chat_response)
    
    @staticmethod
    def supports_llm(model: str) -> bool:
        return 'oci' in model.lower()

    @staticmethod
    def check_llm() -> bool:
        required_vars = ["OCI_MODEL_ID", "OCI_COMPARTMENT_ID", "OCI_ENDPOINT"]
        missing_vars = [var for var in required_vars if var not in os.environ]
        if missing_vars:
            raise Exception(f"Missing required environment variables: {', '.join(missing_vars)}")

        return True

    @staticmethod
    def get_context_window_size(model) -> int:
        if "cohere" in model:
            return 128000
    
    @staticmethod
    def get_maximum_output_token(model) -> int:
        if "cohere" in model:
            return 4000
