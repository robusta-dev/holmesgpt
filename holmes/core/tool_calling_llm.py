import concurrent.futures
import json
import logging
import textwrap
from typing import List, Optional, Dict, Type, Union
from holmes.core.investigation_structured_output import (
    DEFAULT_SECTIONS,
    InputSectionsDataType,
    get_output_format_for_investigation,
    is_response_an_incorrect_tool_call,
    DISABLE_SYNTHETIC_STRUCTURED_OUTPUT,
)
from holmes.core.performance_timing import PerformanceTiming
from holmes.utils.tags import format_tags_in_string, parse_messages_tags
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.llm import LLM
from openai import BadRequestError
from openai._types import NOT_GIVEN
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)
from pydantic import BaseModel
from rich.console import Console

from holmes.core.issue import Issue
from holmes.core.runbooks import RunbookManager
from holmes.core.tools import ToolExecutor


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


class ResourceInstructionDocument(BaseModel):
    """Represents context necessary for an investigation in the form of a URL
    It is expected that Holmes will use that URL to fetch additional context about an error.
    This URL can for example be the location of a runbook
    """

    url: str


class Instructions(BaseModel):
    instructions: List[str] = []


class ResourceInstructions(BaseModel):
    instructions: List[str] = []
    documents: List[ResourceInstructionDocument] = []


class ToolCallingLLM:
    llm: LLM

    def __init__(self, tool_executor: ToolExecutor, max_steps: int, llm: LLM):
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.llm = llm

    def prompt_call(
        self,
        system_prompt: str,
        user_prompt: str,
        post_process_prompt: Optional[str] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        sections: Optional[InputSectionsDataType] = None,
    ) -> LLMResult:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.call(
            messages,
            post_process_prompt,
            response_format,
            user_prompt=user_prompt,
            sections=sections,
        )

    def messages_call(
        self,
        messages: List[Dict[str, str]],
        post_process_prompt: Optional[str] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
    ) -> LLMResult:
        return self.call(messages, post_process_prompt, response_format)

    def call(
        self,
        messages: List[Dict[str, str]],
        post_process_prompt: Optional[str] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        user_prompt: Optional[str] = None,
        sections: Optional[InputSectionsDataType] = None,
    ) -> LLMResult:
        perf_timing = PerformanceTiming("tool_calling_llm.call")
        tool_calls = []
        tools = self.tool_executor.get_all_tools_openai_format()
        perf_timing.measure("get_all_tools_openai_format")
        max_steps = self.max_steps
        for i in range(max_steps):
            perf_timing.measure(f"start iteration {i}")
            logging.debug(f"running iteration {i}")
            # on the last step we don't allow tools - we want to force a reply, not a request to run another tool
            tools = NOT_GIVEN if i == max_steps - 1 else tools
            tool_choice = NOT_GIVEN if tools == NOT_GIVEN else "auto"

            total_tokens = self.llm.count_tokens_for_message(messages)
            max_context_size = self.llm.get_context_window_size()
            maximum_output_token = self.llm.get_maximum_output_token()
            perf_timing.measure("count tokens")

            if (total_tokens + maximum_output_token) > max_context_size:
                logging.warning("Token limit exceeded. Truncating tool responses.")
                messages = self.truncate_messages_to_fit_context(
                    messages, max_context_size, maximum_output_token
                )
                perf_timing.measure("truncate_messages_to_fit_context")

            logging.debug(f"sending messages={messages}\n\ntools={tools}")
            try:
                full_response = self.llm.completion(
                    messages=parse_messages_tags(messages),
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=0.00000001,
                    response_format=response_format,
                    drop_params=True,
                )
                logging.debug(f"got response {full_response.to_json()}")

                perf_timing.measure("llm.completion")
            # catch a known error that occurs with Azure and replace the error message with something more obvious to the user
            except BadRequestError as e:
                if "Unrecognized request arguments supplied: tool_choice, tools" in str(
                    e
                ):
                    raise Exception(
                        "The Azure model you chose is not supported. Model version 1106 and higher required."
                    )
                else:
                    raise
            response = full_response.choices[0]

            response_message = response.message
            if (
                response_message
                and response_format
                and not DISABLE_SYNTHETIC_STRUCTURED_OUTPUT
            ):
                incorrect_tool_call = is_response_an_incorrect_tool_call(
                    sections, response
                )
                if incorrect_tool_call:
                    logging.warning(
                        "Detected incorrect tool call. Structured output will be disabled. This can happen on models that do not support tool calling. For Azure AI, make sure the model name contains 'gpt-4o'. To disable this holmes behaviour, set DISABLE_SYNTHETIC_STRUCTURED_OUTPUT to `1` or `True`."
                    )
                    # disable structured output and retry an eval without it
                    response_format = None
                    max_steps = max_steps + 1
                    continue

            messages.append(
                response_message.model_dump(
                    exclude_defaults=True, exclude_unset=True, exclude_none=True
                )
            )

            tools_to_call = getattr(response_message, "tool_calls", None)
            text_response = response_message.content
            if not tools_to_call:
                # For chatty models post process and summarize the result
                # this only works for calls where user prompt is explicitly passed through
                if post_process_prompt and user_prompt:
                    logging.info("Running post processing on investigation.")
                    raw_response = text_response
                    post_processed_response = self._post_processing_call(
                        prompt=user_prompt,
                        investigation=raw_response,
                        user_prompt=post_process_prompt,
                    )

                    perf_timing.end()
                    return LLMResult(
                        result=post_processed_response,
                        unprocessed_result=raw_response,
                        tool_calls=tool_calls,
                        prompt=json.dumps(messages, indent=2),
                        messages=messages,
                    )

                perf_timing.end()
                return LLMResult(
                    result=text_response,
                    tool_calls=tool_calls,
                    prompt=json.dumps(messages, indent=2),
                    messages=messages,
                )

            perf_timing.measure("pre-tool-calls")
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
                    perf_timing.measure(f"tool completed {tool_call_result.tool_name}")

    def _invoke_tool(
        self, tool_to_call: ChatCompletionMessageToolCall
    ) -> ToolCallResult:
        tool_name = tool_to_call.function.name
        tool_params = None
        try:
            tool_params = json.loads(tool_to_call.function.arguments)
        except Exception:
            logging.warning(
                f"Failed to parse arguments for tool: {tool_name}. args: {tool_to_call.function.arguments}"
            )
        tool_call_id = tool_to_call.id
        tool = self.tool_executor.get_tool_by_name(tool_name)

        if (not tool) or (tool_params is None):
            logging.warning(
                f"Skipping tool execution for {tool_name}: args: {tool_to_call.function.arguments}"
            )
            return ToolCallResult(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                description="NA",
                result="NA",
            )

        tool_response = tool.invoke(tool_params)

        return ToolCallResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            description=tool.get_parameterized_one_liner(tool_params),
            result=tool_response,
        )

    @staticmethod
    def __load_post_processing_user_prompt(
        input_prompt, investigation, user_prompt: Optional[str] = None
    ) -> str:
        if not user_prompt:
            user_prompt = "builtin://generic_post_processing.jinja2"
        return load_and_render_prompt(
            user_prompt, {"investigation": investigation, "prompt": input_prompt}
        )

    def _post_processing_call(
        self,
        prompt,
        investigation,
        user_prompt: Optional[str] = None,
        system_prompt: str = "You are an AI assistant summarizing Kubernetes issues.",
    ) -> Optional[str]:
        try:
            user_prompt = ToolCallingLLM.__load_post_processing_user_prompt(
                prompt, investigation, user_prompt
            )

            logging.debug(f'Post processing prompt:\n"""\n{user_prompt}\n"""')
            messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": format_tags_in_string(user_prompt),
                },
            ]
            full_response = self.llm.completion(messages=messages, temperature=0)
            logging.debug(f"Post processing response {full_response}")
            return full_response.choices[0].message.content
        except Exception:
            logging.exception("Failed to run post processing", exc_info=True)
            return investigation

    def truncate_messages_to_fit_context(
        self, messages: list, max_context_size: int, maximum_output_token: int
    ) -> list:
        messages_except_tools = [
            message for message in messages if message["role"] != "tool"
        ]
        message_size_without_tools = self.llm.count_tokens_for_message(
            messages_except_tools
        )

        tool_call_messages = [
            message for message in messages if message["role"] == "tool"
        ]

        if message_size_without_tools >= (max_context_size - maximum_output_token):
            logging.error(
                f"The combined size of system_prompt and user_prompt ({message_size_without_tools} tokens) exceeds the model's context window for input."
            )
            raise Exception(
                f"The combined size of system_prompt and user_prompt ({message_size_without_tools} tokens) exceeds the model's context window for input."
            )

        tool_size = min(
            10000,
            int(
                (max_context_size - message_size_without_tools - maximum_output_token)
                / len(tool_call_messages)
            ),
        )

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
        tool_executor: ToolExecutor,
        runbook_manager: RunbookManager,
        max_steps: int,
        llm: LLM,
    ):
        super().__init__(tool_executor, max_steps, llm)
        self.runbook_manager = runbook_manager

    def investigate(
        self,
        issue: Issue,
        prompt: str,
        instructions: Optional[ResourceInstructions],
        console: Optional[Console] = None,
        global_instructions: Optional[Instructions] = None,
        post_processing_prompt: Optional[str] = None,
        sections: Optional[InputSectionsDataType] = None,
    ) -> LLMResult:
        runbooks = self.runbook_manager.get_instructions_for_issue(issue)

        if not sections or len(sections) == 0:
            sections = DEFAULT_SECTIONS

        if instructions is not None and instructions.instructions:
            runbooks.extend(instructions.instructions)

        if console and runbooks:
            console.print(
                f"[bold]Analyzing with {len(runbooks)} runbooks: {runbooks}[/bold]"
            )
        elif console:
            console.print(
                "[bold]No runbooks found for this issue. Using default behaviour. (Add runbooks to guide the investigation.)[/bold]"
            )
        system_prompt = load_and_render_prompt(
            prompt, {"issue": issue, "sections": sections}
        )

        if instructions is not None and len(instructions.documents) > 0:
            docPrompts = []
            for document in instructions.documents:
                docPrompts.append(
                    f"* fetch information from this URL: {document.url}\n"
                )
            runbooks.extend(docPrompts)

        user_prompt = ""
        if runbooks:
            for runbook_str in runbooks:
                user_prompt += f"* {runbook_str}\n"

            user_prompt = f'My instructions to check \n"""{user_prompt}"""'

        if (
            global_instructions
            and global_instructions.instructions
            and len(global_instructions.instructions[0]) > 0
        ):
            user_prompt += f"\n\nGlobal Instructions (use only if relevant): {global_instructions.instructions[0]}\n"

        user_prompt = f"{user_prompt}\n This is context from the issue {issue.raw}"

        logging.debug(
            "Rendered system prompt:\n%s", textwrap.indent(system_prompt, "    ")
        )
        logging.debug("Rendered user prompt:\n%s", textwrap.indent(user_prompt, "    "))

        res = self.prompt_call(
            system_prompt,
            user_prompt,
            post_processing_prompt,
            response_format=get_output_format_for_investigation(sections),
            sections=sections,
        )
        res.instructions = runbooks
        return res
