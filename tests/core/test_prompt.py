import pytest
from unittest.mock import Mock
from rich.console import Console

from holmes.core.prompt import (
    build_initial_ask_messages,
    append_file_to_user_prompt,
    append_all_files_to_user_prompt,
)


@pytest.fixture
def console():
    return Console(force_terminal=False, force_jupyter=False)


@pytest.fixture
def mock_tool_executor():
    tool_executor = Mock()
    tool_executor.toolsets = []
    return tool_executor


def test_build_initial_ask_messages_basic(console, mock_tool_executor):
    """Test basic message building without any optional parameters."""
    messages = build_initial_ask_messages(
        console,
        "Test prompt",
        None,
        mock_tool_executor,
        None,
        None,
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Test prompt"


def test_build_initial_ask_messages_with_system_prompt_additions(
    console, mock_tool_executor
):
    """Test message building with system prompt additions."""
    system_additions = "Additional system instructions here."
    messages = build_initial_ask_messages(
        console,
        "Test prompt",
        None,
        mock_tool_executor,
        None,
        system_additions,
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    # Check for unique word from the system additions
    assert "Additional" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Test prompt"


def test_build_initial_ask_messages_with_file(console, mock_tool_executor, tmp_path):
    """Test message building with file attachment."""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("File content here")

    messages = build_initial_ask_messages(
        console,
        "Test prompt",
        [test_file],
        mock_tool_executor,
        None,
        None,
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Test prompt" in messages[1]["content"]
    assert "File content here" in messages[1]["content"]
    # Check for file attachment markers
    assert "<attached-file" in messages[1]["content"]
    assert "test.txt" in messages[1]["content"]
    assert "</attached-file>" in messages[1]["content"]


def test_build_initial_ask_messages_with_runbooks(console, mock_tool_executor):
    """Test message building with runbooks."""
    runbooks = {"test_runbook": {"description": "Test runbook"}}

    messages = build_initial_ask_messages(
        console,
        "Test prompt",
        None,
        mock_tool_executor,
        runbooks,
        None,
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    # The runbook should be passed to the template context
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Test prompt"


def test_build_initial_ask_messages_all_parameters(
    console, mock_tool_executor, tmp_path
):
    """Test message building with all parameters."""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("File content")

    runbooks = {"test_runbook": {"description": "Test runbook"}}
    system_additions = "Extra system instructions"

    messages = build_initial_ask_messages(
        console,
        "Test prompt",
        [test_file],
        mock_tool_executor,
        runbooks,
        system_additions,
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    # Check for unique word from system additions
    assert "Extra" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "Test prompt" in messages[1]["content"]
    assert "File content" in messages[1]["content"]


def test_append_file_to_user_prompt(tmp_path):
    """Test appending a single file to user prompt."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test file content")

    prompt = "Original prompt"
    result = append_file_to_user_prompt(prompt, test_file)

    assert "Original prompt" in result
    assert "Test file content" in result
    # Check for file attachment markers
    assert "<attached-file" in result
    assert "test.txt" in result
    assert "</attached-file>" in result


def test_append_all_files_to_user_prompt(console, tmp_path):
    """Test appending multiple files to user prompt."""
    # Create multiple test files
    file1 = tmp_path / "file1.txt"
    file1.write_text("Content 1")

    file2 = tmp_path / "file2.txt"
    file2.write_text("Content 2")

    prompt = "Original prompt"
    result = append_all_files_to_user_prompt(console, prompt, [file1, file2])

    assert "Original prompt" in result
    assert "Content 1" in result
    assert "Content 2" in result
    # Check for file attachment markers
    assert "<attached-file" in result
    assert "file1.txt" in result
    assert "file2.txt" in result
    assert result.count("</attached-file>") == 2


def test_append_all_files_to_user_prompt_no_files(console):
    """Test appending files when no files are provided."""
    prompt = "Original prompt"
    result = append_all_files_to_user_prompt(console, prompt, None)

    assert result == "Original prompt"

    # Also test with empty list
    result = append_all_files_to_user_prompt(console, prompt, [])
    assert result == "Original prompt"
