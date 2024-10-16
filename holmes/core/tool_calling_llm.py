import concurrent.futures
import json
import logging
import textwrap
import os
from typing import List, Optional
from holmes.plugins.prompts import load_and_render_prompt
from litellm import get_supported_openai_params
import litellm
import jinja2
from openai import BadRequestError
from openai._types import NOT_GIVEN
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
from pydantic import BaseModel
from rich.console import Console
from holmes.common.env_vars import ROBUSTA_AI, ROBUSTA_API_ENDPOINT

from holmes.core.issue import Issue
from holmes.core.runbooks import RunbookManager
from holmes.core.tools import YAMLToolExecutor


class ToolCallResult(BaseModel):
    tool_call_id: str
    tool_name: str
    description: str
    result: str


class LLMResult(BaseModel):
    tool_calls: Optional[List[ToolCallResult]] = None
    result: Optional[str] = None
    unprocessed_result: Optional[str] = None
    instructions: List[str] = []

    # TODO: clean up these two
    prompt: Optional[str] = None
    messages: Optional[List[dict]] = None

    def get_tool_usage_summary(self):
        return "AI used info from issue and " + ",".join(
            [f"`{tool_call.description}`" for tool_call in self.tool_calls]
        )

class ToolCallingLLM:

    def __init__(
        self,
        model: Optional[str],
        api_key: Optional[str],
        tool_executor: YAMLToolExecutor,
        max_steps: int,
    ):
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.model = model
        self.api_key = api_key
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
    
    def call(self, system_prompt, user_prompt, post_process_prompt: Optional[str] = None, response_format: dict = None) -> LLMResult:
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
        tool_calls = []
        tools = self.tool_executor.get_all_tools_openai_format()

        for i in range(self.max_steps):
            logging.debug(f"running iteration {i}")
            # on the last step we don't allow tools - we want to force a reply, not a request to run another tool
            tools = NOT_GIVEN if i == self.max_steps - 1 else tools
            tool_choice = NOT_GIVEN if tools == NOT_GIVEN else "auto"
            
            total_tokens = self.count_tokens_for_message(messages)
            max_context_size = self.get_context_window_size()
            maximum_output_token = self.get_maximum_output_token()

            if (total_tokens + maximum_output_token) > max_context_size:
                logging.warning("Token limit exceeded. Truncating tool responses.")
                messages = self.truncate_messages_to_fit_context(messages, max_context_size, maximum_output_token)

            logging.debug(f"sending messages {messages}")
            try:
                full_response = litellm.completion(
                    model=self.model,
                    api_key=self.api_key,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    base_url=self.base_url,
                    temperature=0.00000001,
                    response_format=response_format,
                    drop_params=True
                )
                logging.debug(f"got response {full_response}")
            # catch a known error that occurs with Azure and replace the error message with something more obvious to the user
            except BadRequestError as e:
                if "Unrecognized request arguments supplied: tool_choice, tools" in str(e):
                    raise Exception(
                        "The Azure model you chose is not supported. Model version 1106 and higher required."
                    )
                else:
                    raise
            response = full_response.choices[0]
            response_message = response.message
            messages.append(
                response_message.model_dump(
                    exclude_defaults=True, exclude_unset=True, exclude_none=True
                )
            )

            tools_to_call = getattr(response_message, "tool_calls", None)
            if not tools_to_call:
                # For chatty models post process and summarize the result
                if post_process_prompt:
                    logging.info(f"Running post processing on investigation.")
                    raw_response = response_message.content
                    post_processed_response = self._post_processing_call(
                                                    prompt=user_prompt, 
                                                    investigation=raw_response, 
                                                    user_prompt=post_process_prompt
                                                )
                    return LLMResult(
                        result=post_processed_response,
                        unprocessed_result = raw_response,
                        tool_calls=tool_calls,
                        prompt=json.dumps(messages, indent=2),
                    )
                
                return LLMResult(
                    result=response_message.content,
                    tool_calls=tool_calls,
                    prompt=json.dumps(messages, indent=2),
                )

            # when asked to run tools, we expect no response other than the request to run tools unless bedrock
            if response_message.content and ('bedrock' not in self.model and logging.DEBUG != logging.root.level):
                logging.warning(f"got unexpected response when tools were given: {response_message.content}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = []
                for t in tools_to_call:
                    futures.append(executor.submit(self._invoke_tool, t))

                for future in concurrent.futures.as_completed(futures):
                    tool_call_result: ToolCallResult = future.result()
                    tool_calls.append(tool_call_result)
                    messages.append(
                        {
                            "tool_call_id": tool_call_result.tool_call_id,
                            "role": "tool",
                            "name": tool_call_result.tool_name,
                            "content": tool_call_result.result,
                        }
                    )

    def _invoke_tool(self, tool_to_call: ChatCompletionMessageToolCall) -> ToolCallResult:
        tool_name = tool_to_call.function.name
        tool_params = json.loads(tool_to_call.function.arguments)
        tool_call_id = tool_to_call.id
        tool = self.tool_executor.get_tool_by_name(tool_name)
        tool_response = tool.invoke(tool_params)

        return ToolCallResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            description=tool.get_parameterized_one_liner(tool_params),
            result=tool_response,
        )

    @staticmethod
    def __load_post_processing_user_prompt(input_prompt, investigation, user_prompt: Optional[str] = None) -> str:
        if not user_prompt:
            user_prompt = "builtin://generic_post_processing.jinja2"
        return load_and_render_prompt(user_prompt, {"investigation": investigation, "prompt": input_prompt})

    def _post_processing_call(self, prompt, investigation, user_prompt: Optional[str] = None, 
                              system_prompt: str ="You are an AI assistant summarizing Kubernetes issues.") -> Optional[str]:
        try:
            user_prompt = ToolCallingLLM.__load_post_processing_user_prompt(prompt, investigation, user_prompt)

            logging.debug(f"Post processing prompt:\n\"\"\"\n{user_prompt}\n\"\"\"")
            messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ]
            full_response = litellm.completion(
                model=self.model,
                api_key=self.api_key,
                messages=messages,
                temperature=0
            )
            logging.debug(f"Post processing response {full_response}")
            return full_response.choices[0].message.content
        except Exception as error:
            logging.exception("Failed to run post processing", exc_info=True)
            return investigation

    def truncate_messages_to_fit_context(self, messages: list, max_context_size: int, maximum_output_token: int) -> list:
        messages_except_tools = [message for message in messages if message["role"] != "tool"]
        message_size_without_tools = self.count_tokens_for_message(messages_except_tools)

        tool_call_messages = [message for message in messages if message["role"] == "tool"]
        
        if message_size_without_tools >= (max_context_size - maximum_output_token):
            logging.error(f"The combined size of system_prompt and user_prompt ({message_size_without_tools} tokens) exceeds the model's context window for input.")
            raise Exception(f"The combined size of system_prompt and user_prompt ({message_size_without_tools} tokens) exceeds the model's context window for input.")

        tool_size = min(10000, int((max_context_size - message_size_without_tools - maximum_output_token) / len(tool_call_messages)))

        for message in messages:
            if message["role"] == "tool":
                message["content"] = message["content"][:tool_size]
        return messages
        
# TODO: consider getting rid of this entirely and moving templating into the cmds in holmes.py 
class IssueInvestigator(ToolCallingLLM):
    """
    Thin wrapper around ToolCallingLLM which:
    1) Provides a default prompt for RCA
    2) Accepts Issue objects
    3) Looks up and attaches runbooks
    """

    def __init__(
        self,
        model: Optional[str],
        api_key: Optional[str],
        tool_executor: YAMLToolExecutor,
        runbook_manager: RunbookManager,
        max_steps: int,
    ):
        super().__init__(model, api_key, tool_executor, max_steps)
        self.runbook_manager = runbook_manager

    def investigate(
        self, issue: Issue, prompt: str, console: Console, instructions: List[str] = [], post_processing_prompt: Optional[str] = None
    ) -> LLMResult:
        runbooks = self.runbook_manager.get_instructions_for_issue(issue)
        runbooks.extend(instructions)

        if runbooks:
            console.print(
                f"[bold]Analyzing with {len(runbooks)} runbooks: {runbooks}[/bold]"
            )
        else:
            console.print(
                f"[bold]No runbooks found for this issue. Using default behaviour. (Add runbooks to guide the investigation.)[/bold]"
            )
        system_prompt = load_and_render_prompt(prompt, {"issue": issue})

        user_prompt = ""
        if runbooks:
            for i in runbooks:
                user_prompt += f"* {i}\n"

            user_prompt = f'My instructions to check \n"""{user_prompt}"""'

        user_prompt = f"{user_prompt}\n This is context from the issue {issue.raw}"
        logging.debug(
            "Rendered system prompt:\n%s", textwrap.indent(system_prompt, "    ")
        )
        logging.debug(
            "Rendered user prompt:\n%s", textwrap.indent(user_prompt, "    ")
        )

        res = self.call(system_prompt, user_prompt, post_processing_prompt)
        res.instructions = runbooks
        return res
