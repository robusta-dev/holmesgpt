from typing import List

from holmes.core.models import (
    ConversationRequest,
    HolmesConversationHistory,
    ConversationInvestigationResult,
    ToolCallConversationResult,
)
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.tool_calling_llm import ToolCallingLLM


def truncate_conversation_history_tools(
    conversation_history: List[HolmesConversationHistory], tool_size: int
) -> List[HolmesConversationHistory]:
    return [
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
        for history in conversation_history
    ]


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

    truncated_conversation_history = truncate_conversation_history_tools(
        conversation_request.context.conversation_history, tool_size
    )
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


def handle_chat_conversation(
    conversation_request: ConversationRequest, ai: ToolCallingLLM
) -> str:
    template_path = "generic_ask_for_chat_conversation.jinja2"
    number_of_tools = sum(
        [
            len(history.answer.tools)
            for history in conversation_request.context.conversation_history
        ]
    )

    if number_of_tools == 0:
        template_context = {
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

    truncated_conversation_history = truncate_conversation_history_tools(
        conversation_request.context.conversation_history, tool_size
    )

    template_context = {
        "conversation_history": truncated_conversation_history,
    }
    system_prompt = load_and_render_prompt(template_path, template_context)
    return system_prompt
