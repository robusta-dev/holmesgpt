import datetime
import json
import logging
import textwrap
import os
from typing import Dict, Generator, List, Optional, Iterator

import litellm
import jinja2
from openai import BadRequestError, OpenAI
from openai._types import NOT_GIVEN
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from pydantic import BaseModel
from rich.console import Console

from holmes.core.issue import Issue
from holmes.core.runbooks import RunbookManager
from holmes.core.tools import YAMLToolExecutor, ToolCallResult


class LLMResult(BaseModel):
    tool_calls: Optional[List[ToolCallResult]] = None
    result: Optional[str] = None

    # TODO: clean up these two - prompt is really messages and messages is never set
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

        self.check_llm(self.model, self.api_key)

    def check_llm(self, model, api_key):
        # TODO: this is a hack to get around the fact that we can't pass in an api key to litellm.validate_environment 
        # so without this hack it always complains that the environment variable for the api key is missing
        # to fix that, we always set an api key in the standard format that litellm expects (which is ${PROVIDER}_API_KEY)
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

        # this unfortunately does not seem to work for azure if the deployment name is not a well-known model name 
        #if not litellm.supports_function_calling(model=model):
        #    raise Exception(f"model {model} does not support function calling. You must use HolmesGPT with a model that supports function calling.")
    
    def call(self, system_prompt, user_prompt) -> LLMResult:
        messages = self._get_initial_messages(system_prompt, user_prompt)
        tool_calls = []
        tools = self.tool_executor.get_all_tools_openai_format()
        for i in range(self.max_steps):
            logging.debug(f"running iteration {i}")
            # on the last step we don't allow tools - we want to force a reply, not a request to run another tool
            tools = NOT_GIVEN if i == self.max_steps - 1 else tools
            tool_choice = NOT_GIVEN if tools == NOT_GIVEN else "auto"
            logging.debug(f"sending messages {messages}")
            full_response = litellm.completion(
                model=self.model,
                api_key=self.api_key,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=0.00000001,
            )
            response = full_response.choices[0]
            response_message = response.message
            messages.append(
                response_message.model_dump(
                    exclude_defaults=True, exclude_unset=True, exclude_none=True
                )
            )

            tools_to_call: Optional[List[ChatCompletionMessageToolCall]]  = getattr(response_message, "tool_calls", None)
            if not tools_to_call:
                return LLMResult(
                    result=response_message.content,
                    tool_calls=tool_calls,
                    prompt=json.dumps(messages, indent=2),
                )

            # Some models return text responses alongside tool calls
            if response_message.content:
                logging.info(f"AI: {response_message.content}")

            tool_results = self.tool_executor.invoke_tools_openai_format(tools_to_call)
            tool_calls.extend(tool_results)
            messages.extend([tool_result.to_openai_format() for tool_result in tool_results])

        
    def _get_initial_messages(self, system_prompt, user_prompt):
        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
    

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
        self, issue: Issue, prompt: str, console: Console
    ) -> LLMResult:
        environment = jinja2.Environment()
        system_prompt_template = environment.from_string(prompt)
        runbooks = self.runbook_manager.get_instructions_for_issue(issue)
        if runbooks:
            console.print(
                f"[bold]Analyzing with {len(runbooks)} runbooks: {runbooks}[/bold]"
            )
        else:
            console.print(
                f"[bold]No runbooks found for this issue. Using default behaviour. (Add runbooks to guide the investigation.)[/bold]"
            )
        system_prompt = system_prompt_template.render(issue=issue, runbooks=runbooks)
        user_prompt = f"{issue.raw}"
        logging.debug(
            "Rendered system prompt:\n%s", textwrap.indent(system_prompt, "    ")
        )
        logging.debug(
            "Rendered user prompt:\n%s", textwrap.indent(user_prompt, "    ")
        )
        return self.call(system_prompt, user_prompt)
