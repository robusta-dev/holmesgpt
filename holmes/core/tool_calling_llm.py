import concurrent.futures
import json
import logging
import textwrap
from typing import Dict, List, Optional, Type, Union, Callable, Any

from holmes.core.models import (
    ToolApprovalDecision,
    ToolCallResult,
    TruncationResult,
    TruncationMetadata,
    PendingToolApproval,
)

import sentry_sdk
from openai import BadRequestError
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)
from pydantic import BaseModel, Field
from rich.console import Console

from holmes.common.env_vars import (
    TEMPERATURE,
    MAX_OUTPUT_TOKEN_RESERVATION,
    LOG_LLM_USAGE_RESPONSE,
)

from holmes.core.investigation_structured_output import (
    DEFAULT_SECTIONS,
    REQUEST_STRUCTURED_OUTPUT_FROM_LLM,
    InputSectionsDataType,
    get_output_format_for_investigation,
    is_response_an_incorrect_tool_call,
)
from holmes.core.issue import Issue
from holmes.core.llm import LLM, get_llm_usage
from holmes.core.performance_timing import PerformanceTiming
from holmes.core.resource_instruction import ResourceInstructions
from holmes.core.runbooks import RunbookManager
from holmes.core.safeguards import prevent_overly_repeated_tool_call
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.core.tools_utils.tool_context_window_limiter import (
    prevent_overly_big_tool_response,
)
from holmes.plugins.prompts import load_and_render_prompt
from holmes.utils import sentry_helper
from holmes.utils.global_instructions import (
    Instructions,
    add_global_instructions_to_user_prompt,
)
from holmes.utils.tags import format_tags_in_string, parse_messages_tags
from holmes.core.tools_utils.tool_executor import ToolExecutor
from holmes.core.tracing import DummySpan
from holmes.utils.colors import AI_COLOR
from holmes.utils.stream import StreamEvents, StreamMessage

# Create a named logger for cost tracking
cost_logger = logging.getLogger("holmes.costs")


TRUNCATION_NOTICE = "\n\n[TRUNCATED]"


class LLMCosts(BaseModel):
    """Tracks cost and token usage for LLM calls."""

    total_cost: float = 0.0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _extract_cost_from_response(full_response) -> float:
    """Extract cost value from LLM response.

    Args:
        full_response: The raw LLM response object

    Returns:
        The cost as a float, or 0.0 if not available
    """
    try:
        cost_value = (
            full_response._hidden_params.get("response_cost", 0)
            if hasattr(full_response, "_hidden_params")
            else 0
        )
        # Ensure cost is a float
        return float(cost_value) if cost_value is not None else 0.0
    except Exception:
        return 0.0


def _process_cost_info(
    full_response, costs: Optional[LLMCosts] = None, log_prefix: str = "LLM call"
) -> None:
    """Process cost and token information from LLM response.

    Logs the cost information and optionally accumulates it into a costs object.

    Args:
        full_response: The raw LLM response object
        costs: Optional LLMCosts object to accumulate costs into
        log_prefix: Prefix for logging messages (e.g., "LLM call", "Post-processing")
    """
    try:
        cost = _extract_cost_from_response(full_response)
        usage = getattr(full_response, "usage", {})

        if usage:
            if LOG_LLM_USAGE_RESPONSE:  # shows stats on token cache usage
                logging.info(f"LLM usage response:\n{usage}\n")
            prompt_toks = usage.get("prompt_tokens", 0)
            completion_toks = usage.get("completion_tokens", 0)
            total_toks = usage.get("total_tokens", 0)
            cost_logger.debug(
                f"{log_prefix} cost: ${cost:.6f} | Tokens: {prompt_toks} prompt + {completion_toks} completion = {total_toks} total"
            )
            # Accumulate costs and tokens if costs object provided
            if costs:
                costs.total_cost += cost
                costs.prompt_tokens += prompt_toks
                costs.completion_tokens += completion_toks
                costs.total_tokens += total_toks
        elif cost > 0:
            cost_logger.debug(
                f"{log_prefix} cost: ${cost:.6f} | Token usage not available"
            )
            if costs:
                costs.total_cost += cost
    except Exception as e:
        logging.debug(f"Could not extract cost information: {e}")


# TODO: I think there's a bug here because we don't account for the 'role' or json structure like '{...}' when counting tokens
# However, in practice it works because we reserve enough space for the output tokens that the minor inconsistency does not matter
# We should fix this in the future
# TODO: we truncate using character counts not token counts - this means we're overly agressive with truncation - improve it by considering
# token truncation and not character truncation
def truncate_messages_to_fit_context(
    messages: list, max_context_size: int, maximum_output_token: int, count_tokens_fn
) -> TruncationResult:
    """
    Helper function to truncate tool messages to fit within context limits.

    Args:
        messages: List of message dictionaries with roles and content
        max_context_size: Maximum context window size for the model
        maximum_output_token: Maximum tokens reserved for model output
        count_tokens_fn: Function to count tokens for a list of messages

    Returns:
        Modified list of messages with truncated tool responses

    Raises:
        Exception: If non-tool messages exceed available context space
    """
    messages_except_tools = [
        message for message in messages if message["role"] != "tool"
    ]
    message_size_without_tools = count_tokens_fn(messages_except_tools)

    tool_call_messages = [message for message in messages if message["role"] == "tool"]

    reserved_for_output_tokens = min(maximum_output_token, MAX_OUTPUT_TOKEN_RESERVATION)
    if message_size_without_tools >= (max_context_size - reserved_for_output_tokens):
        logging.error(
            f"The combined size of system_prompt and user_prompt ({message_size_without_tools} tokens) exceeds the model's context window for input."
        )
        raise Exception(
            f"The combined size of system_prompt and user_prompt ({message_size_without_tools} tokens) exceeds the maximum context size of {max_context_size - reserved_for_output_tokens} tokens available for input."
        )

    if len(tool_call_messages) == 0:
        return TruncationResult(truncated_messages=messages, truncations=[])

    available_space = (
        max_context_size - message_size_without_tools - reserved_for_output_tokens
    )
    remaining_space = available_space
    tool_call_messages.sort(
        key=lambda x: count_tokens_fn([{"role": "tool", "content": x["content"]}])
    )

    truncations = []

    # Allocate space starting with small tools and going to larger tools, while maintaining fairness
    # Small tools can often get exactly what they need, while larger tools may need to be truncated
    # We ensure fairness (no tool gets more than others that need it) and also maximize utilization (we don't leave space unused)
    for i, msg in enumerate(tool_call_messages):
        remaining_tools = len(tool_call_messages) - i
        max_allocation = remaining_space // remaining_tools
        needed_space = count_tokens_fn([{"role": "tool", "content": msg["content"]}])
        allocated_space = min(needed_space, max_allocation)

        if needed_space > allocated_space:
            truncation_metadata = _truncate_tool_message(
                msg, allocated_space, needed_space
            )
            truncations.append(truncation_metadata)

        remaining_space -= allocated_space
    return TruncationResult(truncated_messages=messages, truncations=truncations)


def _truncate_tool_message(
    msg: dict, allocated_space: int, needed_space: int
) -> TruncationMetadata:
    msg_content = msg["content"]
    tool_call_id = msg["tool_call_id"]
    tool_name = msg["name"]

    # Ensure the indicator fits in the allocated space
    if allocated_space > len(TRUNCATION_NOTICE):
        original = msg_content if isinstance(msg_content, str) else str(msg_content)
        msg["content"] = (
            original[: allocated_space - len(TRUNCATION_NOTICE)] + TRUNCATION_NOTICE
        )
        end_index = allocated_space - len(TRUNCATION_NOTICE)
    else:
        msg["content"] = TRUNCATION_NOTICE[:allocated_space]
        end_index = allocated_space

    msg.pop("token_count", None)  # Remove token_count if present
    logging.info(
        f"Truncating tool message '{tool_name}' from {needed_space} to {allocated_space} tokens"
    )
    truncation_metadata = TruncationMetadata(
        tool_call_id=tool_call_id,
        start_index=0,
        end_index=end_index,
        tool_name=tool_name,
        original_token_count=needed_space,
    )
    return truncation_metadata


class LLMResult(LLMCosts):
    tool_calls: Optional[List[ToolCallResult]] = None
    result: Optional[str] = None
    unprocessed_result: Optional[str] = None
    instructions: List[str] = Field(default_factory=list)
    # TODO: clean up these two
    prompt: Optional[str] = None
    messages: Optional[List[dict]] = None
    metadata: Optional[Dict[Any, Any]] = None

    def get_tool_usage_summary(self):
        return "AI used info from issue and " + ",".join(
            [f"`{tool_call.description}`" for tool_call in self.tool_calls]
        )


class ToolCallingLLM:
    llm: LLM

    def __init__(
        self, tool_executor: ToolExecutor, max_steps: int, llm: LLM, tracer=None
    ):
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.tracer = tracer
        self.llm = llm
        self.approval_callback: Optional[
            Callable[[StructuredToolResult], tuple[bool, Optional[str]]]
        ] = None

    def process_tool_decisions(
        self, messages: List[Dict[str, Any]], tool_decisions: List[ToolApprovalDecision]
    ) -> List[Dict[str, Any]]:
        """
        Process tool approval decisions and execute approved tools.

        Args:
            messages: Current conversation messages
            tool_decisions: List of ToolApprovalDecision objects

        Returns:
            Updated messages list with tool execution results
        """
        # Import here to avoid circular imports

        # Find the last message with pending approvals
        pending_message_idx = None
        pending_tool_calls = None

        for i in reversed(range(len(messages))):
            msg = messages[i]
            if msg.get("role") == "assistant" and msg.get("pending_approval"):
                pending_message_idx = i
                pending_tool_calls = msg.get("tool_calls", [])
                break

        if pending_message_idx is None or not pending_tool_calls:
            # No pending approvals found
            if tool_decisions:
                logging.warning(
                    f"Received {len(tool_decisions)} tool decisions but no pending approvals found"
                )
            return messages

        # Create decision lookup
        decisions_by_id = {
            decision.tool_call_id: decision for decision in tool_decisions
        }

        # Validate that all decisions have corresponding pending tool calls
        pending_tool_ids = {tool_call["id"] for tool_call in pending_tool_calls}
        invalid_decisions = [
            decision.tool_call_id
            for decision in tool_decisions
            if decision.tool_call_id not in pending_tool_ids
        ]

        if invalid_decisions:
            logging.warning(
                f"Received decisions for non-pending tool calls: {invalid_decisions}"
            )

        # Process each tool call
        for tool_call in pending_tool_calls:
            tool_call_id = tool_call["id"]
            decision = decisions_by_id.get(tool_call_id)

            if decision and decision.approved:
                try:
                    tool_call_obj = ChatCompletionMessageToolCall(**tool_call)
                    llm_tool_result = self._invoke_llm_tool_call(
                        tool_to_call=tool_call_obj,
                        previous_tool_calls=[],
                        trace_span=DummySpan(),
                        tool_number=None,
                    )
                    messages.append(llm_tool_result.as_tool_call_message())

                except Exception as e:
                    logging.error(
                        f"Failed to execute approved tool {tool_call_id}: {e}"
                    )
                    messages.append(
                        {
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "name": tool_call["function"]["name"],
                            "content": f"Tool execution failed: {str(e)}",
                        }
                    )
            else:
                # Tool was rejected or no decision found, add rejection message
                messages.append(
                    {
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "name": tool_call["function"]["name"],
                        "content": "Tool execution was denied by the user.",
                    }
                )

        return messages

    def prompt_call(
        self,
        system_prompt: str,
        user_prompt: str,
        post_process_prompt: Optional[str] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        sections: Optional[InputSectionsDataType] = None,
        trace_span=DummySpan(),
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
            trace_span=trace_span,
        )

    def messages_call(
        self,
        messages: List[Dict[str, str]],
        post_process_prompt: Optional[str] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        trace_span=DummySpan(),
    ) -> LLMResult:
        return self.call(
            messages, post_process_prompt, response_format, trace_span=trace_span
        )

    @sentry_sdk.trace
    def call(  # type: ignore
        self,
        messages: List[Dict[str, str]],
        post_process_prompt: Optional[str] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        user_prompt: Optional[str] = None,
        sections: Optional[InputSectionsDataType] = None,
        trace_span=DummySpan(),
        tool_number_offset: int = 0,
    ) -> LLMResult:
        perf_timing = PerformanceTiming("tool_calling_llm.call")
        tool_calls = []  # type: ignore
        costs = LLMCosts()

        tools = self.tool_executor.get_all_tools_openai_format(
            target_model=self.llm.model
        )
        perf_timing.measure("get_all_tools_openai_format")
        max_steps = self.max_steps
        i = 0
        metadata: Dict[Any, Any] = {}
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
                truncated_res = self.truncate_messages_to_fit_context(
                    messages, max_context_size, maximum_output_token
                )
                metadata["truncations"] = [
                    t.model_dump() for t in truncated_res.truncations
                ]
                messages = truncated_res.truncated_messages
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
                logging.debug(f"got response {full_response.to_json()}")  # type: ignore

                # Extract and accumulate cost information
                _process_cost_info(full_response, costs, "LLM call")

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

            response = full_response.choices[0]  # type: ignore

            response_message = response.message  # type: ignore
            if response_message and response_format:
                # Litellm API is bugged. Stringify and parsing ensures all attrs of the choice are available.
                dict_response = json.loads(full_response.to_json())  # type: ignore
                incorrect_tool_call = is_response_an_incorrect_tool_call(
                    sections, dict_response.get("choices", [{}])[0]
                )

                if incorrect_tool_call:
                    logging.warning(
                        "Detected incorrect tool call. Structured output will be disabled. This can happen on models that do not support tool calling. For Azure AI, make sure the model name contains 'gpt-4o'. To disable this holmes behaviour, set REQUEST_STRUCTURED_OUTPUT_FROM_LLM to `false`."
                    )
                    # disable structured output going forward and and retry
                    sentry_helper.capture_structured_output_incorrect_tool_call()
                    response_format = None
                    max_steps = max_steps + 1
                    continue

            new_message = response_message.model_dump(
                exclude_defaults=True, exclude_unset=True, exclude_none=True
            )
            messages.append(new_message)

            tools_to_call = getattr(response_message, "tool_calls", None)
            text_response = response_message.content

            if (
                hasattr(response_message, "reasoning_content")
                and response_message.reasoning_content
            ):
                logging.debug(
                    f"[bold {AI_COLOR}]AI (reasoning) 🤔:[/bold {AI_COLOR}] {response_message.reasoning_content}\n"
                )

            if not tools_to_call:
                # For chatty models post process and summarize the result
                # this only works for calls where user prompt is explicitly passed through
                if post_process_prompt and user_prompt:
                    logging.info("Running post processing on investigation.")
                    raw_response = text_response
                    post_processed_response, post_processing_cost = (
                        self._post_processing_call(
                            prompt=user_prompt,
                            investigation=raw_response,
                            user_prompt=post_process_prompt,
                        )
                    )
                    costs.total_cost += post_processing_cost

                    self.llm.count_tokens_for_message(messages)
                    perf_timing.end(f"- completed in {i} iterations -")
                    metadata["usage"] = get_llm_usage(full_response)
                    metadata["max_tokens"] = max_context_size
                    metadata["max_output_tokens"] = maximum_output_token
                    return LLMResult(
                        result=post_processed_response,
                        unprocessed_result=raw_response,
                        tool_calls=tool_calls,
                        prompt=json.dumps(messages, indent=2),
                        messages=messages,
                        **costs.model_dump(),  # Include all cost fields
                        metadata=metadata,
                    )

                perf_timing.end(f"- completed in {i} iterations -")
                return LLMResult(
                    result=text_response,
                    tool_calls=tool_calls,
                    prompt=json.dumps(messages, indent=2),
                    messages=messages,
                    **costs.model_dump(),  # Include all cost fields
                    metadata=metadata,
                )

            if text_response and text_response.strip():
                logging.info(f"[bold {AI_COLOR}]AI:[/bold {AI_COLOR}] {text_response}")
            logging.info(
                f"The AI requested [bold]{len(tools_to_call) if tools_to_call else 0}[/bold] tool call(s)."
            )
            perf_timing.measure("pre-tool-calls")
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = []
                futures_tool_numbers: dict[
                    concurrent.futures.Future, Optional[int]
                ] = {}
                tool_number: Optional[int]
                for tool_index, t in enumerate(tools_to_call, 1):
                    logging.debug(f"Tool to call: {t}")
                    tool_number = tool_number_offset + tool_index
                    future = executor.submit(
                        self._invoke_llm_tool_call,
                        tool_to_call=t,
                        previous_tool_calls=tool_calls,
                        trace_span=trace_span,
                        tool_number=tool_number,
                    )
                    futures_tool_numbers[future] = tool_number
                    futures.append(future)

                for future in concurrent.futures.as_completed(futures):
                    tool_call_result: ToolCallResult = future.result()

                    tool_number = (
                        futures_tool_numbers[future]
                        if future in futures_tool_numbers
                        else None
                    )

                    if (
                        tool_call_result.result.status
                        == StructuredToolResultStatus.APPROVAL_REQUIRED
                    ):
                        with trace_span.start_span(type="tool") as tool_span:
                            tool_call_result = self._handle_tool_call_approval(
                                tool_call_result=tool_call_result,
                                tool_number=tool_number,
                            )
                            ToolCallingLLM._log_tool_call_result(
                                tool_span, tool_call_result
                            )

                    tool_calls.append(tool_call_result.as_tool_result_response())
                    messages.append(tool_call_result.as_tool_call_message())

                    perf_timing.measure(f"tool completed {tool_call_result.tool_name}")

                # Update the tool number offset for the next iteration
                tool_number_offset += len(tools_to_call)

                # Add a blank line after all tools in this batch complete
                if tools_to_call:
                    logging.info("")

        raise Exception(f"Too many LLM calls - exceeded max_steps: {i}/{max_steps}")

    def _directly_invoke_tool_call(
        self,
        tool_name: str,
        tool_params: dict,
        user_approved: bool,
        tool_number: Optional[int] = None,
    ) -> StructuredToolResult:
        tool = self.tool_executor.get_tool_by_name(tool_name)
        if not tool:
            logging.warning(
                f"Skipping tool execution for {tool_name}: args: {tool_params}"
            )
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Failed to find tool {tool_name}",
                params=tool_params,
            )

        try:
            tool_response = tool.invoke(
                tool_params, tool_number=tool_number, user_approved=user_approved
            )
        except Exception as e:
            logging.error(
                f"Tool call to {tool_name} failed with an Exception", exc_info=True
            )
            tool_response = StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Tool call failed: {e}",
                params=tool_params,
            )
        return tool_response

    def _get_tool_call_result(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_arguments: str,
        previous_tool_calls: list[dict],
        tool_number: Optional[int] = None,
    ) -> ToolCallResult:
        tool_params = {}
        try:
            tool_params = json.loads(tool_arguments)
        except Exception:
            logging.warning(
                f"Failed to parse arguments for tool: {tool_name}. args: {tool_arguments}"
            )

        tool_response = prevent_overly_repeated_tool_call(
            tool_name=tool_name,
            tool_params=tool_params,
            tool_calls=previous_tool_calls,
        )

        if not tool_response:
            tool_response = self._directly_invoke_tool_call(
                tool_name=tool_name,
                tool_params=tool_params,
                user_approved=False,
                tool_number=tool_number,
            )

        if not isinstance(tool_response, StructuredToolResult):
            # Should never be needed but ensure Holmes does not crash if one of the tools does not return the right type
            logging.error(
                f"Tool {tool_name} return type is not StructuredToolResult. Nesting the tool result into StructuredToolResult..."
            )
            tool_response = StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=tool_response,
                params=tool_params,
            )

        tool = self.tool_executor.get_tool_by_name(tool_name)

        return ToolCallResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            description=str(tool.get_parameterized_one_liner(tool_params))
            if tool
            else "",
            result=tool_response,
        )

    @staticmethod
    def _log_tool_call_result(tool_span, tool_call_result: ToolCallResult):
        tool_span.set_attributes(name=tool_call_result.tool_name)
        tool_span.log(
            input=tool_call_result.result.params,
            output=tool_call_result.result.data,
            error=tool_call_result.result.error,
            metadata={
                "status": tool_call_result.result.status,
                "description": tool_call_result.description,
            },
        )

    def _invoke_llm_tool_call(
        self,
        tool_to_call: ChatCompletionMessageToolCall,
        previous_tool_calls: list[dict],
        trace_span=None,
        tool_number=None,
    ) -> ToolCallResult:
        if trace_span is None:
            trace_span = DummySpan()
        with trace_span.start_span(type="tool") as tool_span:
            if not hasattr(tool_to_call, "function"):
                # Handle the union type - ChatCompletionMessageToolCall can be either
                # ChatCompletionMessageFunctionToolCall (with 'function' field and type='function')
                # or ChatCompletionMessageCustomToolCall (with 'custom' field and type='custom').
                # We use hasattr to check for the 'function' attribute as it's more flexible
                # and doesn't require importing the specific type.
                tool_name = "Unknown_Custom_Tool"
                logging.error(f"Unsupported custom tool call: {tool_to_call}")
                tool_call_result = ToolCallResult(
                    tool_call_id=tool_to_call.id,
                    tool_name=tool_name,
                    description="NA",
                    result=StructuredToolResult(
                        status=StructuredToolResultStatus.ERROR,
                        error="Custom tool calls are not supported",
                        params=None,
                    ),
                )
            else:
                tool_name = tool_to_call.function.name
                tool_arguments = tool_to_call.function.arguments
                tool_id = tool_to_call.id
                tool_call_result = self._get_tool_call_result(
                    tool_id,
                    tool_name,
                    tool_arguments,
                    previous_tool_calls=previous_tool_calls,
                    tool_number=tool_number,
                )

            prevent_overly_big_tool_response(
                tool_call_result=tool_call_result, llm=self.llm
            )

            ToolCallingLLM._log_tool_call_result(tool_span, tool_call_result)
            return tool_call_result

    def _handle_tool_call_approval(
        self,
        tool_call_result: ToolCallResult,
        tool_number: Optional[int],
    ) -> ToolCallResult:
        """
        Handle approval for a single tool call if required.

        Args:
            tool_call_result: A single tool call result that may require approval
            tool_number: The tool call number

        Returns:
            Updated tool call result with approved/denied status
        """

        # If no approval callback, convert to ERROR because it is assumed the client may not be able to handle approvals
        if not self.approval_callback:
            tool_call_result.result.status = StructuredToolResultStatus.ERROR
            return tool_call_result

        # Get approval from user
        approved, feedback = self.approval_callback(tool_call_result.result)

        if approved:
            logging.debug(
                f"User approved command: {tool_call_result.result.invocation}"
            )
            new_response = self._directly_invoke_tool_call(
                tool_name=tool_call_result.tool_name,
                tool_params=tool_call_result.result.params or {},
                user_approved=True,
                tool_number=tool_number,
            )
            tool_call_result.result = new_response
        else:
            # User denied - update to error
            feedback_text = f" User feedback: {feedback}" if feedback else ""
            tool_call_result.result.status = StructuredToolResultStatus.ERROR
            tool_call_result.result.error = (
                f"User denied command execution.{feedback_text}"
            )

        return tool_call_result

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
    ) -> tuple[Optional[str], float]:
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

            # Extract and log cost information for post-processing
            post_processing_cost = _extract_cost_from_response(full_response)
            if post_processing_cost > 0:
                cost_logger.debug(
                    f"Post-processing LLM cost: ${post_processing_cost:.6f}"
                )

            return full_response.choices[0].message.content, post_processing_cost  # type: ignore
        except Exception:
            logging.exception("Failed to run post processing", exc_info=True)
            return investigation, 0.0

    @sentry_sdk.trace
    def truncate_messages_to_fit_context(
        self, messages: list, max_context_size: int, maximum_output_token: int
    ) -> TruncationResult:
        truncated_res = truncate_messages_to_fit_context(
            messages,
            max_context_size,
            maximum_output_token,
            self.llm.count_tokens_for_message,
        )
        if truncated_res.truncations:
            sentry_helper.capture_tool_truncations(truncated_res.truncations)
        return truncated_res

    def call_stream(
        self,
        system_prompt: str = "",
        user_prompt: Optional[str] = None,
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        sections: Optional[InputSectionsDataType] = None,
        msgs: Optional[list[dict]] = None,
        enable_tool_approval: bool = False,
    ):
        """
        This function DOES NOT call llm.completion(stream=true).
        This function streams holmes one iteration at a time instead of waiting for all iterations to complete.
        """
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
        if msgs:
            messages.extend(msgs)
        perf_timing = PerformanceTiming("tool_calling_llm.call")
        tool_calls: list[dict] = []
        tools = self.tool_executor.get_all_tools_openai_format(
            target_model=self.llm.model
        )
        perf_timing.measure("get_all_tools_openai_format")
        max_steps = self.max_steps
        metadata: Dict[Any, Any] = {}
        i = 0
        tool_number_offset = 0

        while i < max_steps:
            i += 1
            perf_timing.measure(f"start iteration {i}")
            logging.debug(f"running iteration {i}")

            tools = None if i == max_steps else tools
            tool_choice = "auto" if tools else None

            total_tokens = self.llm.count_tokens_for_message(messages)  # type: ignore
            max_context_size = self.llm.get_context_window_size()
            maximum_output_token = self.llm.get_maximum_output_token()
            perf_timing.measure("count tokens")

            if (total_tokens + maximum_output_token) > max_context_size:
                logging.warning("Token limit exceeded. Truncating tool responses.")
                truncated_res = self.truncate_messages_to_fit_context(
                    messages, max_context_size, maximum_output_token
                )
                metadata["truncations"] = [
                    t.model_dump() for t in truncated_res.truncations
                ]
                messages = truncated_res.truncated_messages
                perf_timing.measure("truncate_messages_to_fit_context")
            else:
                metadata["truncations"] = []

            logging.debug(f"sending messages={messages}\n\ntools={tools}")
            try:
                full_response = self.llm.completion(
                    messages=parse_messages_tags(messages),  # type: ignore
                    tools=tools,
                    tool_choice=tool_choice,
                    response_format=response_format,
                    temperature=TEMPERATURE,
                    stream=False,
                    drop_params=True,
                )

                # Log cost information for this iteration (no accumulation in streaming)
                _process_cost_info(full_response, log_prefix="LLM iteration")

                perf_timing.measure("llm.completion")
            # catch a known error that occurs with Azure and replace the error message with something more obvious to the user
            except BadRequestError as e:
                if "Unrecognized request arguments supplied: tool_choice, tools" in str(
                    e
                ):
                    raise Exception(
                        "The Azure model you chose is not supported. Model version 1106 and higher required."
                    ) from e
                else:
                    raise

            response_message = full_response.choices[0].message  # type: ignore
            if response_message and response_format:
                # Litellm API is bugged. Stringify and parsing ensures all attrs of the choice are available.
                dict_response = json.loads(full_response.to_json())  # type: ignore
                incorrect_tool_call = is_response_an_incorrect_tool_call(
                    sections, dict_response.get("choices", [{}])[0]
                )

                if incorrect_tool_call:
                    logging.warning(
                        "Detected incorrect tool call. Structured output will be disabled. This can happen on models that do not support tool calling. For Azure AI, make sure the model name contains 'gpt-4o'. To disable this holmes behaviour, set REQUEST_STRUCTURED_OUTPUT_FROM_LLM to `false`."
                    )
                    # disable structured output going forward and and retry
                    sentry_helper.capture_structured_output_incorrect_tool_call()
                    response_format = None
                    max_steps = max_steps + 1
                    continue

            messages.append(
                response_message.model_dump(
                    exclude_defaults=True, exclude_unset=True, exclude_none=True
                )
            )

            tools_to_call = getattr(response_message, "tool_calls", None)
            if not tools_to_call:
                self.llm.count_tokens_for_message(messages)
                metadata["usage"] = get_llm_usage(full_response)
                metadata["max_tokens"] = max_context_size
                metadata["max_output_tokens"] = maximum_output_token
                yield StreamMessage(
                    event=StreamEvents.ANSWER_END,
                    data={
                        "content": response_message.content,
                        "messages": messages,
                        "metadata": metadata,
                    },
                )
                return

            reasoning = getattr(response_message, "reasoning_content", None)
            message = response_message.content
            if reasoning or message:
                yield StreamMessage(
                    event=StreamEvents.AI_MESSAGE,
                    data={"content": message, "reasoning": reasoning},
                )

            perf_timing.measure("pre-tool-calls")

            # Check if any tools require approval first
            pending_approvals = []
            approval_required_tools = []

            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = []
                for tool_index, t in enumerate(tools_to_call, 1):  # type: ignore
                    tool_number = tool_number_offset + tool_index
                    future = executor.submit(
                        self._invoke_llm_tool_call,
                        tool_to_call=t,  # type: ignore
                        previous_tool_calls=tool_calls,
                        trace_span=DummySpan(),  # Streaming mode doesn't support tracing yet
                        tool_number=tool_number,
                    )
                    futures.append(future)
                    yield StreamMessage(
                        event=StreamEvents.START_TOOL,
                        data={"tool_name": t.function.name, "id": t.id},
                    )

                for future in concurrent.futures.as_completed(futures):
                    tool_call_result: ToolCallResult = future.result()

                    if (
                        tool_call_result.result.status
                        == StructuredToolResultStatus.APPROVAL_REQUIRED
                    ):
                        if enable_tool_approval:
                            pending_approvals.append(
                                PendingToolApproval(
                                    tool_call_id=tool_call_result.tool_call_id,
                                    tool_name=tool_call_result.tool_name,
                                    description=tool_call_result.description,
                                    params=tool_call_result.result.params or {},
                                )
                            )
                            approval_required_tools.append(tool_call_result)

                            yield StreamMessage(
                                event=StreamEvents.TOOL_RESULT,
                                data=tool_call_result.as_streaming_tool_result_response(),
                            )
                        else:
                            tool_call_result.result.status = (
                                StructuredToolResultStatus.ERROR
                            )
                            tool_call_result.result.error = f"Tool call rejected for security reasons: {tool_call_result.result.error}"

                            tool_calls.append(
                                tool_call_result.as_tool_result_response()
                            )
                            messages.append(tool_call_result.as_tool_call_message())

                            yield StreamMessage(
                                event=StreamEvents.TOOL_RESULT,
                                data=tool_call_result.as_streaming_tool_result_response(),
                            )

                    else:
                        tool_calls.append(tool_call_result.as_tool_result_response())
                        messages.append(tool_call_result.as_tool_call_message())

                        yield StreamMessage(
                            event=StreamEvents.TOOL_RESULT,
                            data=tool_call_result.as_streaming_tool_result_response(),
                        )

                # If we have approval required tools, end the stream with pending approvals
                if pending_approvals:
                    # Add assistant message with pending tool calls
                    assistant_msg = {
                        "role": "assistant",
                        "content": response_message.content,
                        "tool_calls": [
                            {
                                "id": result.tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": result.tool_name,
                                    "arguments": json.dumps(result.result.params or {}),
                                },
                            }
                            for result in approval_required_tools
                        ],
                        "pending_approval": True,
                    }
                    messages.append(assistant_msg)

                    # End stream with approvals required
                    yield StreamMessage(
                        event=StreamEvents.APPROVAL_REQUIRED,
                        data={
                            "content": None,
                            "messages": messages,
                            "pending_approvals": [
                                approval.model_dump() for approval in pending_approvals
                            ],
                            "requires_approval": True,
                        },
                    )
                    return

                # Update the tool number offset for the next iteration
                tool_number_offset += len(tools_to_call)

        raise Exception(
            f"Too many LLM calls - exceeded max_steps: {i}/{self.max_steps}"
        )


# TODO: consider getting rid of this entirely and moving templating into the cmds in holmes_cli.py
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
        cluster_name: Optional[str],
    ):
        super().__init__(tool_executor, max_steps, llm)
        self.runbook_manager = runbook_manager
        self.cluster_name = cluster_name

    def investigate(
        self,
        issue: Issue,
        prompt: str,
        instructions: Optional[ResourceInstructions],
        console: Optional[Console] = None,
        global_instructions: Optional[Instructions] = None,
        post_processing_prompt: Optional[str] = None,
        sections: Optional[InputSectionsDataType] = None,
        trace_span=DummySpan(),
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
                "toolsets": self.tool_executor.toolsets,
                "cluster_name": self.cluster_name,
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
            trace_span=trace_span,
        )
        res.instructions = runbooks
        return res
