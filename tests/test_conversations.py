import pytest
import copy
from unittest.mock import MagicMock, patch
from holmes.core.tool_calling_llm import ToolCallingLLM
from holmes.core.conversations import (
    build_chat_messages,
    calculate_tool_size,
    DEFAULT_TOOL_SIZE,
    build_issue_chat_messages
)
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.models import IssueChatRequest, ToolCallConversationResult, IssueInvestigationResult

template_path = "builtin://generic_ask.jinja2"


USER_TEST_PROMPT = "Can u show me deployments on my cluster?"


@pytest.fixture
def mock_ai(mocker):
    return mocker.MagicMock(spec=ToolCallingLLM)


def test_build_chat_messages_empty_history(mock_ai, mocker):
    conversation_history = []
    mock_load_and_render_prompt = mocker.patch(
        "holmes.core.conversations.load_and_render_prompt", wraps=load_and_render_prompt
    )
    mocked_calculate_tool_size = mocker.patch(
        "holmes.core.conversations.calculate_tool_size", wraps=calculate_tool_size
    )
    messages = build_chat_messages(USER_TEST_PROMPT, conversation_history, mock_ai)

    expected_messages = [
        {"role": "system", "content": load_and_render_prompt(template_path, {})},
        {"role": "user", "content": USER_TEST_PROMPT},
    ]

    assert messages == expected_messages
    mock_load_and_render_prompt.assert_called_once_with(template_path, {})
    mocked_calculate_tool_size.assert_not_called()


def test_build_chat_messages_with_history_no_tools(mock_ai, mocker):
    conversation_history = [
        {"role": "system", "content": "System prompt..."},
        {"role": "user", "content": "Test Example"},
    ]
    mock_load_and_render_prompt = mocker.patch(
        "holmes.core.conversations.load_and_render_prompt", wraps=load_and_render_prompt
    )
    mocked_calculate_tool_size = mocker.patch(
        "holmes.core.conversations.calculate_tool_size", wraps=calculate_tool_size
    )

    messages = build_chat_messages(USER_TEST_PROMPT, conversation_history.copy(), mock_ai)

    expected_history = conversation_history + [{"role": "user", "content": USER_TEST_PROMPT}]
    assert messages == expected_history
    mock_load_and_render_prompt.assert_not_called()
    mocked_calculate_tool_size.assert_not_called()


def test_build_chat_messages_with_tools(mock_ai, mocker):
    conversation_history = [
        {"role": "system", "content": "System prompt..."},
        {"role": "user", "content": "Test Example"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "tool", "content": "Tool response"},
    ]

    mock_ai.llm = MagicMock()
    mock_ai.llm.get_context_window_size.return_value = 2048

    conversation_history_copy = copy.deepcopy(conversation_history)

    mock_load_and_render_prompt = mocker.patch(
        "holmes.core.conversations.load_and_render_prompt"
    )
    mocked_calculate_tool_size = mocker.patch(
        "holmes.core.conversations.calculate_tool_size"
    )
    mocked_calculate_tool_size.return_value = 2
    mocked_truncate_tool_messages = mocker.patch(
        "holmes.core.conversations.truncate_tool_messages"
    )

    messages = build_chat_messages(USER_TEST_PROMPT, conversation_history_copy, mock_ai)

    expected_messages = conversation_history + [{"role": "user", "content": USER_TEST_PROMPT}]
    assert messages == expected_messages

    number_of_tools = len(
        [message for message in expected_messages if message.get("role") == "tool"]
    )
    conversation_history_without_tools = [
        message for message in expected_messages if message.get("role") != "tool"
    ]

    mock_load_and_render_prompt.assert_not_called()
    mocked_calculate_tool_size.assert_called_once_with(
        mock_ai, conversation_history_without_tools, number_of_tools
    )
    mocked_truncate_tool_messages.assert_called_once_with(expected_messages, 2)


def test_calculate_tool_size_no_tools(mock_ai):
    result = calculate_tool_size(mock_ai, [], number_of_tools=0)
    assert result == DEFAULT_TOOL_SIZE, "Expected default tool size when no tools are present"


def test_calculate_tool_size_with_enough_space(mock_ai):
    mock_ai = MagicMock()
    mock_ai.llm.get_context_window_size.return_value = 2048
    mock_ai.llm.count_tokens_for_message.return_value = 200
    mock_ai.llm.get_maximum_output_token.return_value = 50

    result = calculate_tool_size(mock_ai, [{"role": "user", "content": "Test message"}], number_of_tools=2)
    expected_size = (2048 - 200 - 50) // 2
    assert result == expected_size, f"Expected tool size to be {expected_size} when there is enough space"


def test_calculate_tool_size_with_limited_space(mock_ai):
    mock_ai = MagicMock()
    mock_ai.llm.get_context_window_size.return_value = 500
    mock_ai.llm.count_tokens_for_message.return_value = 450
    mock_ai.llm.get_maximum_output_token.return_value = 30

    result = calculate_tool_size(mock_ai, [{"role": "user", "content": "Test message"}], number_of_tools=2)
    expected_size = (500 - 450 - 30) // 2
    assert result == expected_size, f"Expected tool size to be {expected_size} when space is limited"


def test_calculate_tool_size_exceeds_default(mock_ai):
    mock_ai = MagicMock()
    mock_ai.llm.get_context_window_size.return_value = 120000
    mock_ai.llm.count_tokens_for_message.return_value = 100
    mock_ai.llm.get_maximum_output_token.return_value = 50

    result = calculate_tool_size(mock_ai, [{"role": "user", "content": "Test message"}], number_of_tools=1)
    assert result == DEFAULT_TOOL_SIZE, "Expected tool size to be capped at DEFAULT_TOOL_SIZE when calculated size exceeds it"


def mock_load_and_render_prompt(template_path, context):
    return f"Rendered prompt with context: {context}"


def test_build_issue_chat_messages_no_history_no_tools(monkeypatch):
    monkeypatch.setattr('your_module.load_and_render_prompt', mock_load_and_render_prompt)

    ai = MagicMock()
    ai.llm.get_context_window_size.return_value = 2048
    ai.llm.count_tokens_for_message.return_value = 100 
    ai.llm.get_maximum_output_token.return_value = 512

    issue_chat_request = IssueChatRequest(
        ask="What is the status of my issue?",
        investigation_result=IssueInvestigationResult(
            result="We have analyzed your issue and found some information.",
            tools=[]
        ),
        issue_type="Technical"
    )
    issue_chat_request.conversation_history = []

    messages = build_issue_chat_messages(issue_chat_request, ai)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "We have analyzed your issue" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "What is the status of my issue?"

def test_build_issue_chat_messages_no_history_with_tools(monkeypatch):
    monkeypatch.setattr('your_module.load_and_render_prompt', mock_load_and_render_prompt)

    ai = MagicMock()
    ai.llm.get_context_window_size.return_value = 2048
    ai.llm.count_tokens_for_message.return_value = 100  # Example token count
    ai.llm.get_maximum_output_token.return_value = 512

    tools = [
        ToolCallConversationResult(
            name="get_user_info",
            description="Fetches user information",
            output="User info output that is very long and might need to be truncated"
        ),
        ToolCallConversationResult(
            name="get_issue_details",
            description="Fetches issue details",
            output="Issue details output that is very long and might need to be truncated"
        ),
    ]
    issue_chat_request = IssueChatRequest(
        ask="Please provide an update on my issue.",
        investigation_result=IssueInvestigationResult(
            result="We have investigated the issue.",
            tools=tools
        ),
        issue_type="Technical"
    )
    issue_chat_request.conversation_history = []

    messages = build_issue_chat_messages(issue_chat_request, ai)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "We have investigated the issue" in messages[0]["content"]
    assert "get_user_info" in messages[0]["content"]
    assert "get_issue_details" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Please provide an update on my issue."


def test_build_issue_chat_messages_with_history_and_tools(monkeypatch):
    monkeypatch.setattr('holmes.core.conversations.load_and_render_prompt', mock_load_and_render_prompt)

    ai = MagicMock()
    ai.llm.get_context_window_size.return_value = 2048
    ai.llm.count_tokens_for_message.return_value = 300  
    ai.llm.get_maximum_output_token.return_value = 512

    conversation_history = [
        {
            "role": "system",
            "content": "Initial system prompt."
        },
        {
            "role": "user",
            "content": "Initial user message."
        },
        {
            "role": "assistant",
            "content": "Assistant's initial response."
        },
        {
            "role": "tool",
            "name": "previous_tool",
            "content": "Previous tool output."
        }
    ]
    tools = [
        ToolCallConversationResult(
            name="new_tool",
            description="New tool description",
            output="New tool output that is long and might need truncation"
        )
    ]
    issue_chat_request = IssueChatRequest(
        ask="Can you provide more details?",
        investigation_result=IssueInvestigationResult(
            result="Further investigation results.",
            tools=tools
        ),
        issue_type="Technical"
    )
    issue_chat_request.conversation_history = conversation_history

    messages = build_issue_chat_messages(issue_chat_request, ai)

    assert len(messages) == len(conversation_history) + 1
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Can you provide more details?"

    assert messages[0]["role"] == "system"
    assert "Further investigation results." in messages[0]["content"]

    assert "new_tool" in messages[0]["content"]

def test_build_issue_chat_messages_tool_output_truncation(monkeypatch):
    monkeypatch.setattr('holmes.core.conversations.load_and_render_prompt', mock_load_and_render_prompt)

    ai = MagicMock()
    ai.llm.get_context_window_size.return_value = 100 
    ai.llm.count_tokens_for_message.return_value = 50
    ai.llm.get_maximum_output_token.return_value = 10

    tools = [
        ToolCallConversationResult(
            name="large_tool",
            description="Tool with large output",
            output="A" * 1000  
        )
    ]
    issue_chat_request = IssueChatRequest(
        ask="What's the update?",
        investigation_result=IssueInvestigationResult(
            result="Investigation result.",
            tools=tools
        ),
        issue_type="Technical"
    )
    issue_chat_request.conversation_history = []

    messages = build_issue_chat_messages(issue_chat_request, ai)

    number_of_tools = 1
    context_window = ai.llm.get_context_window_size.return_value
    message_size_without_tools = ai.llm.count_tokens_for_message.return_value
    maximum_output_token = ai.llm.get_maximum_output_token.return_value

    tool_size = min(
        DEFAULT_TOOL_SIZE,
        int((context_window - message_size_without_tools - maximum_output_token) / number_of_tools)
    )
    expected_truncated_output = "A" * tool_size

    assert messages[0]["role"] == "system"
    assert expected_truncated_output in messages[0]["content"]
    assert len(expected_truncated_output) == tool_size

def test_build_issue_chat_messages_with_history_no_tools(monkeypatch):
    monkeypatch.setattr('holmes.core.conversations.load_and_render_prompt', mock_load_and_render_prompt)
    
    ai = MagicMock()
    ai.llm.get_context_window_size.return_value = 2048
    ai.llm.count_tokens_for_message.return_value = 100
    ai.llm.get_maximum_output_token.return_value = 512

    conversation_history = [
        {
            "role": "system",
            "content": "Previous system prompt."
        },
        {
            "role": "user",
            "content": "Previous user message."
        },
        {
            "role": "assistant",
            "content": "Previous assistant response."
        }
    ]
    issue_chat_request = IssueChatRequest(
        ask="Any updates?",
        investigation_result=IssueInvestigationResult(
            result="No new findings.",
            tools=[]
        ),
        issue_type="Technical"
    )
    issue_chat_request.conversation_history = conversation_history

    messages = build_issue_chat_messages(issue_chat_request, ai)

    assert len(messages) == len(conversation_history) + 1
    assert messages[0]["role"] == "system"
    assert "No new findings." in messages[0]["content"]
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Any updates?"
