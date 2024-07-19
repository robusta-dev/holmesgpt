import datetime
import json
import logging
import textwrap
from typing import Dict, Generator, List, Optional

import jinja2
from openai import BadRequestError, OpenAI
from openai._types import NOT_GIVEN
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from pydantic import BaseModel
from rich.console import Console

from holmes.core.issue import Issue
from holmes.core.runbooks import RunbookManager
from holmes.core.tools import YAMLToolExecutor


class ToolCallResult(BaseModel):
    tool_name: str
    description: str
    result: str

class LLMResult(BaseModel):
    tool_calls: Optional[List[ToolCallResult]] = None
    result: Optional[str] = None
    prompt: Optional[str] = None
    messages: Optional[List[dict]] = None

    def get_tool_usage_summary(self):
        return "AI used info from issue and " + ",".join(
            [f"`{tool_call.description}`" for tool_call in self.tool_calls]
        )

class ToolCallingLLM:

    def __init__(
        self,
        client: OpenAI,
        model: str,
        tool_executor: YAMLToolExecutor,
        max_steps: int,
    ):
        self.client = client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.model = model

    def call(self, system_prompt, user_prompt) -> LLMResult:
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
            logging.debug(f"sending messages {messages}")
            try:
                full_response = self.client.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=0.00000001
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

            tools_to_call = response_message.tool_calls
            if not tools_to_call:
                return LLMResult(
                    result=response_message.content,
                    tool_calls=tool_calls,
                    prompt=json.dumps(messages, indent=2),
                )

            # when asked to run tools, we expect no response other than the request to run tools
            if response_message.content:
                logging.warning(f"got unexpected response when tools were given: {response_message.content}")

            for t in tools_to_call:
                tool_name = t.function.name
                tool_params = json.loads(t.function.arguments)
                tool = self.tool_executor.get_tool_by_name(tool_name)
                tool_response = tool.invoke(tool_params)
                MAX_CHARS = 100_000 # an arbitrary limit - we will do something smarter in the future
                if len(tool_response) > MAX_CHARS:
                    logging.warning(f"tool {tool_name} returned a very long response ({len(tool_response)} chars) - truncating to last 10000 chars")
                    tool_response = tool_response[-MAX_CHARS:]
                messages.append(
                    {
                        "tool_call_id": t.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_response,
                    }
                )
                tool_calls.append(
                    ToolCallResult(
                        tool_name=tool_name,
                        description=tool.get_parameterized_one_liner(tool_params),
                        result=tool_response,
                    )
                )

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
        client: OpenAI,
        model: str,
        tool_executor: YAMLToolExecutor,
        runbook_manager: RunbookManager,
        max_steps: int,
    ):
        super().__init__(client, model, tool_executor, max_steps)
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
