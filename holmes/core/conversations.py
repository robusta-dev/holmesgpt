from typing import List

from holmes.core.models import (
    ConversationRequest,
    HolmesConversationHistory,
    ConversationInvestigationResult,
    ToolCallConversationResult,
    IssueChatRequest,
)
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.tool_calling_llm import ToolCallingLLM


def calculate_tool_size(
    ai: ToolCallingLLM, messages_without_tools: list[dict], number_of_tools: int
) -> int:
    context_window = ai.get_context_window_size()
    message_size_without_tools = ai.count_tokens_for_message(messages_without_tools)
    maximum_output_token = ai.get_maximum_output_token()

    tool_size = min(
        10000,
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


def build_issue_chat_messages(issue_chat_request: IssueChatRequest, ai: ToolCallingLLM):
    template_path = "generic_ask_for_issue_conversation.jinja2"

    conversation_history = issue_chat_request.conversation_history
    user_prompt = issue_chat_request.ask
    investigation_analysis = issue_chat_request.investigation_result.result
    tools_for_investigation = issue_chat_request.investigation_result.tools

    if not conversation_history or len(conversation_history) == 0:
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
    ask: str, conversation_history: list, ai: ToolCallingLLM
) -> list[dict]:
    template_path = "generic_ask.jinja2"

    if not conversation_history or len(conversation_history) == 0:
        system_prompt = load_and_render_prompt(template_path, {})
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
        return messages

    conversation_history_without_tools = [
        message for message in conversation_history if message.get("role") != "tool"
    ]

    tool_size = calculate_tool_size(
        ai, conversation_history_without_tools, number_of_tools
    )
    truncate_tool_messages(conversation_history, tool_size)

    return conversation_history
