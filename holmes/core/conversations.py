from typing import Dict, List, Optional

from holmes.core.models import (
    ConversationRequest,
    HolmesConversationHistory,
    ConversationInvestigationResult,
    ToolCallConversationResult,
    IssueChatRequest,
    WorkloadHealthChatRequest,
)
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.tool_calling_llm import ToolCallingLLM
from holmes.core.tool_calling_llm import Instructions
from holmes.utils.global_instructions import add_global_instructions_to_user_prompt

DEFAULT_TOOL_SIZE = 10000


def calculate_tool_size(
    ai: ToolCallingLLM, messages_without_tools: list[dict], number_of_tools: int
) -> int:
    if number_of_tools == 0:
        return DEFAULT_TOOL_SIZE

    context_window = ai.llm.get_context_window_size()
    message_size_without_tools = ai.llm.count_tokens_for_message(messages_without_tools)
    maximum_output_token = ai.llm.get_maximum_output_token()

    tool_size = min(
        DEFAULT_TOOL_SIZE,
        int(
            (context_window - message_size_without_tools - maximum_output_token)
            / number_of_tools
        ),
    )
    return tool_size


def truncate_tool_outputs(
    tools: list, tool_size: int
) -> list[ToolCallConversationResult]:
    return [
        ToolCallConversationResult(
            name=tool.name,
            description=tool.description,
            output=tool.output[:tool_size],
        )
        for tool in tools
    ]


def truncate_tool_messages(conversation_history: list, tool_size: int) -> None:
    for message in conversation_history:
        if message.get("role") == "tool":
            message["content"] = message["content"][:tool_size]


# handle_issue_conversation is a method for older api /api/conversation which does not support conversation history
def handle_issue_conversation(
    conversation_request: ConversationRequest, ai: ToolCallingLLM
) -> str:
    template_path = "builtin://generic_ask_for_issue_conversation.jinja2"

    number_of_tools = len(
        conversation_request.context.investigation_result.tools
    ) + sum(
        [
            len(history.answer.tools)
            for history in conversation_request.context.conversation_history
        ]
    )

    if number_of_tools == 0:
        template_context = {
            "investigation": conversation_request.context.investigation_result.result,
            "tools_called_for_investigation": conversation_request.context.investigation_result.tools,
            "conversation_history": conversation_request.context.conversation_history,
        }
        system_prompt = load_and_render_prompt(template_path, template_context)
        return system_prompt

    conversation_history_without_tools = [
        HolmesConversationHistory(
            ask=history.ask,
            answer=ConversationInvestigationResult(analysis=history.answer.analysis),
        )
        for history in conversation_request.context.conversation_history
    ]
    template_context = {
        "investigation": conversation_request.context.investigation_result.result,
        "tools_called_for_investigation": None,
        "conversation_history": conversation_history_without_tools,
    }
    system_prompt = load_and_render_prompt(template_path, template_context)
    messages_without_tools = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": conversation_request.user_prompt,
        },
    ]

    tool_size = calculate_tool_size(ai, messages_without_tools, number_of_tools)

    truncated_conversation_history = [
        HolmesConversationHistory(
            ask=history.ask,
            answer=ConversationInvestigationResult(
                analysis=history.answer.analysis,
                tools=[
                    ToolCallConversationResult(
                        name=tool.name,
                        description=tool.description,
                        output=tool.output[:tool_size],
                    )
                    for tool in history.answer.tools
                ],
            ),
        )
        for history in conversation_request.context.conversation_history
    ]
    truncated_investigation_result_tool_calls = [
        ToolCallConversationResult(
            name=tool.name, description=tool.description, output=tool.output[:tool_size]
        )
        for tool in conversation_request.context.investigation_result.tools
    ]

    template_context = {
        "investigation": conversation_request.context.investigation_result.result,
        "tools_called_for_investigation": truncated_investigation_result_tool_calls,
        "conversation_history": truncated_conversation_history,
    }
    system_prompt = load_and_render_prompt(template_path, template_context)
    return system_prompt


def build_issue_chat_messages(
    issue_chat_request: IssueChatRequest,
    ai: ToolCallingLLM,
    global_instructions: Optional[Instructions] = None,
):
    """
    This function generates a list of messages for issue conversation and ensures that the message sequence adheres to the model's context window limitations
    by truncating tool outputs as necessary before sending to llm.

    We always expect conversation_history to be passed in the openAI format which is supported by litellm and passed back by us.
    That's why we assume that first message in the conversation is system message and truncate tools for it.

    System prompt handling:
    1. For new conversations (empty conversation_history):
       - Creates a new system prompt using generic_ask_for_issue_conversation.jinja2 template
       - Includes investigation analysis, tools (if any), and issue type information
       - If there are tools, calculates appropriate tool size and truncates tool outputs

    2. For existing conversations:
       - Preserves the conversation history
       - Updates the first message (system prompt) with recalculated content
       - Truncates tool outputs if necessary to fit context window
       - Maintains the original conversation flow while ensuring context limits

    Example structure of conversation history:
    conversation_history = [
    # System prompt
    {"role": "system", "content": "...."},
    # User message
    {"role": "user", "content": "Can you get the weather forecast for today?"},
    # Assistant initiates a tool call
    {
        "role": "assistant",
        "content": None,
        "tool_call": {
            "name": "get_weather",
            "arguments": "{\"location\": \"San Francisco\"}"
        }
    },
    # Tool/Function response
    {
        "role": "tool",
        "name": "get_weather",
        "content": "{\"forecast\": \"Sunny, 70 degrees Fahrenheit.\"}"
    },
    # Assistant's final response to the user
    {
        "role": "assistant",
        "content": "The weather in San Francisco today is sunny with a high of 70 degrees Fahrenheit."
    },
    ]
    """
    template_path = "builtin://generic_ask_for_issue_conversation.jinja2"

    conversation_history = issue_chat_request.conversation_history
    user_prompt = issue_chat_request.ask
    investigation_analysis = issue_chat_request.investigation_result.result
    tools_for_investigation = issue_chat_request.investigation_result.tools

    if not conversation_history or len(conversation_history) == 0:
        user_prompt = add_global_instructions_to_user_prompt(
            user_prompt, global_instructions
        )

        number_of_tools_for_investigation = len(tools_for_investigation)
        if number_of_tools_for_investigation == 0:
            system_prompt = load_and_render_prompt(
                template_path,
                {
                    "investigation": investigation_analysis,
                    "tools_called_for_investigation": tools_for_investigation,
                    "issue": issue_chat_request.issue_type,
                },
            )
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
            return messages

        template_context_without_tools = {
            "investigation": investigation_analysis,
            "tools_called_for_investigation": None,
            "issue": issue_chat_request.issue_type,
        }
        system_prompt_without_tools = load_and_render_prompt(
            template_path, template_context_without_tools
        )
        messages_without_tools = [
            {
                "role": "system",
                "content": system_prompt_without_tools,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
        tool_size = calculate_tool_size(
            ai, messages_without_tools, number_of_tools_for_investigation
        )

        truncated_investigation_result_tool_calls = [
            ToolCallConversationResult(
                name=tool.name,
                description=tool.description,
                output=tool.output[:tool_size],
            )
            for tool in tools_for_investigation
        ]

        truncated_template_context = {
            "investigation": investigation_analysis,
            "tools_called_for_investigation": truncated_investigation_result_tool_calls,
            "issue": issue_chat_request.issue_type,
        }
        system_prompt_with_truncated_tools = load_and_render_prompt(
            template_path, truncated_template_context
        )
        return [
            {
                "role": "system",
                "content": system_prompt_with_truncated_tools,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    user_prompt = add_global_instructions_to_user_prompt(
        user_prompt, global_instructions
    )

    conversation_history.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )
    number_of_tools = len(tools_for_investigation) + len(
        [message for message in conversation_history if message.get("role") == "tool"]
    )

    if number_of_tools == 0:
        return conversation_history

    conversation_history_without_tools = [
        message for message in conversation_history if message.get("role") != "tool"
    ]
    template_context_without_tools = {
        "investigation": investigation_analysis,
        "tools_called_for_investigation": None,
        "issue": issue_chat_request.issue_type,
    }
    system_prompt_without_tools = load_and_render_prompt(
        template_path, template_context_without_tools
    )
    conversation_history_without_tools[0]["content"] = system_prompt_without_tools

    tool_size = calculate_tool_size(
        ai, conversation_history_without_tools, number_of_tools
    )

    truncated_investigation_result_tool_calls = [
        ToolCallConversationResult(
            name=tool.name, description=tool.description, output=tool.output[:tool_size]
        )
        for tool in tools_for_investigation
    ]

    template_context = {
        "investigation": investigation_analysis,
        "tools_called_for_investigation": truncated_investigation_result_tool_calls,
        "issue": issue_chat_request.issue_type,
    }
    system_prompt_with_truncated_tools = load_and_render_prompt(
        template_path, template_context
    )
    conversation_history[0]["content"] = system_prompt_with_truncated_tools

    truncate_tool_messages(conversation_history, tool_size)

    return conversation_history


def build_chat_messages(
    ask: str,
    conversation_history: Optional[List[Dict[str, str]]],
    ai: ToolCallingLLM,
    global_instructions: Optional[Instructions] = None,
) -> List[dict]:
    """
    This function generates a list of messages for general chat conversation and ensures that the message sequence adheres to the model's context window limitations
    by truncating tool outputs as necessary before sending to llm.

    We always expect conversation_history to be passed in the openAI format which is supported by litellm and passed back by us.
    That's why we assume that first message in the conversation is system message and truncate tools for it.

    System prompt handling:
    1. For new conversations (empty conversation_history):
       - Creates a new system prompt using generic_ask_conversation.jinja2 template
       - Uses an empty template context (no specific analysis or tools required)
       - Adds global instructions to the user prompt if provided

    2. For existing conversations:
       - Preserves the conversation history as is
       - No need to update system prompt as it doesn't contain tool-specific content
       - Only truncates tool messages if they exist in the conversation
       - Maintains the original conversation flow while ensuring context limits

    Example structure of conversation history:
    conversation_history = [
    # System prompt for general chat
    {"role": "system", "content": "...."},
    # User message with a general question
    {"role": "user", "content": "Can you analyze the logs from my application?"},
    # Assistant initiates a tool call
    {
        "role": "assistant",
        "content": None,
        "tool_call": {
            "name": "fetch_application_logs",
            "arguments": "{\"service\": \"backend\", \"time_range\": \"last_hour\"}"
        }
    },
    # Tool/Function response
    {
        "role": "tool",
        "name": "fetch_application_logs",
        "content": "{\"log_entries\": [\"Error in processing request\", \"Connection timeout\"]}"
    },
    # Assistant's final response to the user
    {
        "role": "assistant",
        "content": "I've analyzed your application logs and found some issues: there are error messages related to request processing and connection timeouts."
    },
    ]
    """
    template_path = "builtin://generic_ask_conversation.jinja2"

    if not conversation_history or len(conversation_history) == 0:
        system_prompt = load_and_render_prompt(template_path, {})
        ask = add_global_instructions_to_user_prompt(ask, global_instructions)

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": ask,
            },
        ]
        return messages

    ask = add_global_instructions_to_user_prompt(ask, global_instructions)

    conversation_history.append(
        {
            "role": "user",
            "content": ask,
        },
    )
    number_of_tools = len(
        [message for message in conversation_history if message.get("role") == "tool"]
    )
    if number_of_tools == 0:
        return conversation_history

    conversation_history_without_tools = [
        message for message in conversation_history if message.get("role") != "tool"
    ]

    tool_size = calculate_tool_size(
        ai, conversation_history_without_tools, number_of_tools
    )
    truncate_tool_messages(conversation_history, tool_size)
    return conversation_history


def build_workload_health_chat_messages(
    workload_health_chat_request: WorkloadHealthChatRequest,
    ai: ToolCallingLLM,
    global_instructions: Optional[Instructions] = None,
):
    """
    This function generates a list of messages for workload health conversation and ensures that the message sequence adheres to the model's context window limitations
    by truncating tool outputs as necessary before sending to llm.

    We always expect conversation_history to be passed in the openAI format which is supported by litellm and passed back by us.
    That's why we assume that first message in the conversation is system message and truncate tools for it.

    System prompt handling:
    1. For new conversations (empty conversation_history):
       - Creates a new system prompt using kubernetes_workload_chat.jinja2 template
       - Includes workload analysis, tools (if any), and resource information
       - If there are tools, calculates appropriate tool size and truncates tool outputs

    2. For existing conversations:
       - Preserves the conversation history
       - Updates the first message (system prompt) with recalculated content
       - Truncates tool outputs if necessary to fit context window
       - Maintains the original conversation flow while ensuring context limits

    Example structure of conversation history:
    conversation_history = [
    # System prompt with workload analysis
    {"role": "system", "content": "...."},
    # User message asking about workload health
    {"role": "user", "content": "What's the current health status of my deployment?"},
    # Assistant initiates a tool call
    {
        "role": "assistant",
        "content": None,
        "tool_call": {
            "name": "check_workload_metrics",
            "arguments": "{\"namespace\": \"default\", \"workload\": \"my-deployment\"}"
        }
    },
    # Tool/Function response
    {
        "role": "tool",
        "name": "check_workload_metrics",
        "content": "{\"cpu_usage\": \"45%\", \"memory_usage\": \"60%\", \"status\": \"Running\"}"
    },
    # Assistant's final response to the user
    {
        "role": "assistant",
        "content": "Your deployment is running normally with CPU usage at 45% and memory usage at 60%."
    },
    ]
    """

    template_path = "builtin://kubernetes_workload_chat.jinja2"

    conversation_history = workload_health_chat_request.conversation_history
    user_prompt = workload_health_chat_request.ask
    workload_analysis = workload_health_chat_request.workload_health_result.analysis
    tools_for_workload = workload_health_chat_request.workload_health_result.tools
    resource = workload_health_chat_request.resource

    if not conversation_history or len(conversation_history) == 0:
        user_prompt = add_global_instructions_to_user_prompt(
            user_prompt, global_instructions
        )

        number_of_tools_for_workload = len(tools_for_workload)
        if number_of_tools_for_workload == 0:
            system_prompt = load_and_render_prompt(
                template_path,
                {
                    "workload_analysis": workload_analysis,
                    "tools_called_for_workload": tools_for_workload,
                    "resource": resource,
                },
            )
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
            return messages

        template_context_without_tools = {
            "workload_analysis": workload_analysis,
            "tools_called_for_workload": None,
            "resource": resource,
        }
        system_prompt_without_tools = load_and_render_prompt(
            template_path, template_context_without_tools
        )
        messages_without_tools = [
            {
                "role": "system",
                "content": system_prompt_without_tools,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
        tool_size = calculate_tool_size(
            ai, messages_without_tools, number_of_tools_for_workload
        )

        truncated_workload_result_tool_calls = [
            ToolCallConversationResult(
                name=tool.name,
                description=tool.description,
                output=tool.output[:tool_size],
            )
            for tool in tools_for_workload
        ]

        truncated_template_context = {
            "workload_analysis": workload_analysis,
            "tools_called_for_workload": truncated_workload_result_tool_calls,
            "resource": resource,
        }
        system_prompt_with_truncated_tools = load_and_render_prompt(
            template_path, truncated_template_context
        )
        return [
            {
                "role": "system",
                "content": system_prompt_with_truncated_tools,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    user_prompt = add_global_instructions_to_user_prompt(
        user_prompt, global_instructions
    )

    conversation_history.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )
    number_of_tools = len(tools_for_workload) + len(
        [message for message in conversation_history if message.get("role") == "tool"]
    )

    if number_of_tools == 0:
        return conversation_history

    conversation_history_without_tools = [
        message for message in conversation_history if message.get("role") != "tool"
    ]
    template_context_without_tools = {
        "workload_analysis": workload_analysis,
        "tools_called_for_workload": None,
        "resource": resource,
    }
    system_prompt_without_tools = load_and_render_prompt(
        template_path, template_context_without_tools
    )
    conversation_history_without_tools[0]["content"] = system_prompt_without_tools

    tool_size = calculate_tool_size(
        ai, conversation_history_without_tools, number_of_tools
    )

    truncated_workload_result_tool_calls = [
        ToolCallConversationResult(
            name=tool.name, description=tool.description, output=tool.output[:tool_size]
        )
        for tool in tools_for_workload
    ]

    template_context = {
        "workload_analysis": workload_analysis,
        "tools_called_for_workload": truncated_workload_result_tool_calls,
        "resource": resource,
    }
    system_prompt_with_truncated_tools = load_and_render_prompt(
        template_path, template_context
    )
    conversation_history[0]["content"] = system_prompt_with_truncated_tools

    truncate_tool_messages(conversation_history, tool_size)

    return conversation_history
