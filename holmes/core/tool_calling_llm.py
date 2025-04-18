import concurrent.futures
import json
import logging
import textwrap
from typing import List, Optional, Dict, Type, Union
from pydantic_core import from_json
import sentry_sdk
import requests

from holmes.common.env_vars import TEMPERATURE
from holmes.core.investigation_structured_output import (
    DEFAULT_SECTIONS,
    REQUEST_STRUCTURED_OUTPUT_FROM_LLM,
    InputSectionsDataType,
    get_output_format_for_investigation,
    is_response_an_incorrect_tool_call,
    process_response_into_sections,
)
from holmes.core.performance_timing import PerformanceTiming
from holmes.utils.global_instructions import (
    Instructions,
    add_global_instructions_to_user_prompt,
)
from holmes.utils.tags import format_tags_in_string, parse_messages_tags
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.llm import LLM
from openai import BadRequestError
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)
from pydantic import BaseModel
from rich.console import Console

from holmes.core.issue import Issue
from holmes.core.runbooks import RunbookManager
from holmes.core.tools import ToolExecutor
from litellm.types.utils import Message
from holmes.common.env_vars import ROBUSTA_API_ENDPOINT, STREAM_CHUNKS_PER_PARSE
from holmes.core.investigation_structured_output import (
    parse_markdown_into_sections_from_hash_sign,
)
from holmes.core.tools import StructuredToolResult, ToolResultStatus


class ToolCallResult(BaseModel):
    tool_call_id: str
    tool_name: str
    description: str
    result: StructuredToolResult
    size: Optional[int] = None

    def as_dict(self):
        return {
            "tool_call_id": self.tool_call_id,
            "description": self.description,
            "role": "tool",
            "name": self.tool_name,
            "content": self.result,
        }


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

    @sentry_sdk.trace
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
        i = 0
        while i < max_steps:
            i += 1
            perf_timing.measure(f"start iteration {i}")
            logging.debug(f"running iteration {i}")
            # on the last step we don't allow tools - we want to force a reply, not a request to run another tool
            tools = None if i == max_steps else tools
            tool_choice = "auto" if tools else None

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
                    temperature=TEMPERATURE,
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
            if response_message and response_format:
                # Litellm API is bugged. Stringify and parsing ensures all attrs of the choice are available.
                dict_response = json.loads(full_response.to_json())
                incorrect_tool_call = is_response_an_incorrect_tool_call(
                    sections, dict_response.get("choices", [{}])[0]
                )

                if incorrect_tool_call:
                    logging.warning(
                        "Detected incorrect tool call. Structured output will be disabled. This can happen on models that do not support tool calling. For Azure AI, make sure the model name contains 'gpt-4o'. To disable this holmes behaviour, set REQUEST_STRUCTURED_OUTPUT_FROM_LLM to `false`."
                    )
                    # disable structured output going forward and and retry
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

                    perf_timing.end(f"- completed in {i} iterations -")
                    return LLMResult(
                        result=post_processed_response,
                        unprocessed_result=raw_response,
                        tool_calls=tool_calls,
                        prompt=json.dumps(messages, indent=2),
                        messages=messages,
                    )

                perf_timing.end(f"- completed in {i} iterations -")
                return LLMResult(
                    result=text_response,
                    tool_calls=tool_calls,
                    prompt=json.dumps(messages, indent=2),
                    messages=messages,
                )

            perf_timing.measure("pre-tool-calls")
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                futures = []
                for t in tools_to_call:
                    logging.debug(f"Tool to call: {t}")
                    futures.append(executor.submit(self._invoke_tool, t))

                for future in concurrent.futures.as_completed(futures):
                    tool_call_result: ToolCallResult = future.result()
                    tool_calls.append(tool_call_result)

                    tool_response = tool_call_result.result.data
                    if tool_call_result.result.status == ToolResultStatus.ERROR:
                        tool_response = f"{tool_call_result.result.error or 'Tool execution failed'}:\n\n{tool_call_result.result.data or ''}".strip()

                    messages.append(
                        {
                            "tool_call_id": tool_call_result.tool_call_id,
                            "role": "tool",
                            "name": tool_call_result.tool_name,
                            "content": tool_response,
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

        tool_response = None
        try:
            tool_response = tool.invoke(tool_params)
        except Exception as e:
            logging.error(
                f"Tool call to {tool_name} failed with an Exception", exc_info=True
            )
            tool_response = StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Tool call failed: {e}",
                params=tool_params,
            )

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

    @sentry_sdk.trace
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
            if message["role"] == "tool" and len(message["content"]) > tool_size:
                message["content"] = message["content"][:tool_size]
                if "token_count" in message:
                    del message["token_count"]
        return messages

    def call_stream(
        self,
        system_prompt: str,
        user_prompt: Optional[str] = None,
        stream: bool = False,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        sections: Optional[InputSectionsDataType] = None,
        runbooks: List[str] = None,
    ):
        def stream_analysis(it, peek_chunk):
            buffer = peek_chunk.get("data", "")
            yield create_sse_message(peek_chunk.get("event"), peek_chunk.get("data"))
            chunk_counter = 0

            for chunk in it:
                buffer += chunk
                chunk_counter += 1
                if chunk_counter == STREAM_CHUNKS_PER_PARSE:
                    chunk_counter = 0
                    yield create_sse_message(
                        "ai_answer",
                        {
                            "sections": parse_markdown_into_sections_from_hash_sign(
                                buffer
                            )
                            or {},
                            "analysis": buffer,
                            "instructions": runbooks or [],
                        },
                    )

            yield create_sse_message(
                "ai_answer_end",
                {
                    "sections": parse_markdown_into_sections_from_hash_sign(buffer)
                    or {},
                    "analysis": buffer,
                    "instructions": runbooks or [],
                },
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        perf_timing = PerformanceTiming("tool_calling_llm.call")
        tools = self.tool_executor.get_all_tools_openai_format()
        perf_timing.measure("get_all_tools_openai_format")
        i = 0

        while i < self.max_steps:
            i += 1
            perf_timing.measure(f"start iteration {i}")
            logging.debug(f"running iteration {i}")

            tools = [] if i == self.max_steps - 1 else tools
            tool_choice = None if tools == [] else "auto"

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
                if stream:
                    response = requests.post(
                        f"{ROBUSTA_API_ENDPOINT}/chat/completions",
                        json={
                            "messages": parse_messages_tags(messages),
                            "tools": tools,
                            "tool_choice": tool_choice,
                            "temperature": TEMPERATURE,
                            "response_format": response_format,
                            "stream": True,
                            "drop_param": True,
                        },
                        headers={"Authorization": f"Bearer {self.llm.api_key}"},
                        stream=True,
                    )
                    response.raise_for_status()
                    it = response.iter_content(chunk_size=None, decode_unicode=True)
                    peek_chunk = from_json(next(it))
                    tools = peek_chunk.get("tool_calls")

                    if not tools:
                        yield from stream_analysis(it, peek_chunk)
                        perf_timing.measure("llm.completion")
                        return

                    response_message = Message(**peek_chunk)
                    tools_to_call = response_message.tool_calls
                else:
                    full_response = self.llm.completion(
                        messages=parse_messages_tags(messages),
                        tools=tools,
                        tool_choice=tool_choice,
                        temperature=TEMPERATURE,
                        response_format=response_format,
                        stream=False,
                        drop_params=True,
                    )
                    perf_timing.measure("llm.completion")

                    response_message = full_response.choices[0].message
                    if response_message and response_format:
                        # Litellm API is bugged. Stringify and parsing ensures all attrs of the choice are available.
                        dict_response = json.loads(full_response.to_json())
                        incorrect_tool_call = is_response_an_incorrect_tool_call(
                            sections, dict_response.get("choices", [{}])[0]
                        )

                        if incorrect_tool_call:
                            logging.warning(
                                "Detected incorrect tool call. Structured output will be disabled. This can happen on models that do not support tool calling. For Azure AI, make sure the model name contains 'gpt-4o'. To disable this holmes behaviour, set REQUEST_STRUCTURED_OUTPUT_FROM_LLM to `false`."
                            )
                            # disable structured output going forward and and retry
                            response_format = None
                            i -= 1
                            continue

                    tools_to_call = getattr(response_message, "tool_calls", None)
                    if not tools_to_call:
                        (text_response, sections) = process_response_into_sections(
                            response_message.content
                        )

                        yield create_sse_message(
                            "ai_answer_end",
                            {
                                "sections": sections or {},
                                "analysis": text_response,
                                "instructions": runbooks or [],
                            },
                        )
                        return
            # catch a known error that occurs with Azure and replace the error message with something more obvious to the user
            except BadRequestError as e:
                if "Unrecognized request arguments supplied: tool_choice, tools" in str(
                    e
                ):
                    raise Exception(
                        "The Azure model you chose is not supported. Model version 1106 and higher required."
                    )
            except Exception:
                raise

            messages.append(
                response_message.model_dump(
                    exclude_defaults=True, exclude_unset=True, exclude_none=True
                )
            )

            perf_timing.measure("pre-tool-calls")
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = []
                for t in tools_to_call:
                    futures.append(executor.submit(self._invoke_tool, t))
                    yield create_sse_message(
                        "start_tool_calling", {"tool_name": t.function.name, "id": t.id}
                    )

                for future in concurrent.futures.as_completed(futures):
                    tool_call_result: ToolCallResult = future.result()
                    logging.warning(f"tool_call_result={tool_call_result}")
                    tool_response = tool_call_result.result.data
                    logging.warning(f"tool_response={tool_response}")
                    if tool_call_result.result.status == ToolResultStatus.ERROR:
                        tool_response = f"{tool_call_result.result.error or 'Tool execution failed'}:\n\n{tool_call_result.result.data or ''}".strip()

                    if isinstance(tool_response, dict):
                        tool_response = json.dumps(tool_response)
                    if isinstance(tool_response, list):
                        tool_response = json.dumps(tool_response)

                    logging.warning(f"after serializing tool_response={tool_response}")
                    message_to_append = {
                        "tool_call_id": tool_call_result.tool_call_id,
                        "role": "tool",
                        "name": tool_call_result.tool_name,
                        "content": tool_response,
                    }
                    logging.warning(f"message_to_append={message_to_append}")
                    messages.append(message_to_append)
                    perf_timing.measure(f"tool completed {tool_call_result.tool_name}")

                    result_dict = {
                        "tool_call_id": tool_call_result.tool_call_id,
                        "role": "tool",
                        "name": tool_call_result.tool_name,
                        "result": tool_response,
                    }
                    logging.warning(f"result_dict={result_dict}")
                    yield create_sse_message("tool_calling_result", result_dict)


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

        request_structured_output_from_llm = True
        response_format = None

        # This section is about setting vars to request the LLM to return structured output.
        # It does not mean that Holmes will not return structured sections for investigation as it is
        # capable of splitting the markdown into sections
        if not sections or len(sections) == 0:
            # If no sections are passed, we will not ask the LLM for structured output
            sections = DEFAULT_SECTIONS
            request_structured_output_from_llm = False
            logging.info(
                "No section received from the client. Default sections will be used."
            )
        elif self.llm.model and self.llm.model.startswith("bedrock"):
            # Structured output does not work well with Bedrock Anthropic Sonnet 3.5 through litellm
            request_structured_output_from_llm = False

        if not REQUEST_STRUCTURED_OUTPUT_FROM_LLM:
            request_structured_output_from_llm = False

        if request_structured_output_from_llm:
            response_format = get_output_format_for_investigation(sections)
            logging.info("Structured output is enabled for this request")
        else:
            logging.info("Structured output is disabled for this request")

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
            prompt,
            {
                "issue": issue,
                "sections": sections,
                "structured_output": request_structured_output_from_llm,
                "enabled_toolsets": self.tool_executor.enabled_toolsets,
            },
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

        user_prompt = add_global_instructions_to_user_prompt(
            user_prompt, global_instructions
        )
        user_prompt = f"{user_prompt}\n This is context from the issue {issue.raw}"

        logging.debug(
            "Rendered system prompt:\n%s", textwrap.indent(system_prompt, "    ")
        )
        logging.debug("Rendered user prompt:\n%s", textwrap.indent(user_prompt, "    "))

        res = self.prompt_call(
            system_prompt,
            user_prompt,
            post_processing_prompt,
            response_format=response_format,
            sections=sections,
        )
        res.instructions = runbooks
        return res


def create_sse_message(event_type: str, data: dict = {}):
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
