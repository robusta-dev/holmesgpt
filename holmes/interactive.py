import logging
import os
import subprocess
import tempfile
import threading
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Optional, List, DefaultDict

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.completion import Completer, Completion, merge_completers
from prompt_toolkit.completion.filesystem import ExecutableCompleter, PathCompleter
from prompt_toolkit.history import InMemoryHistory, FileHistory
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.shortcuts.prompt import CompleteStyle
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea

from rich.console import Console
from rich.markdown import Markdown, Panel

from holmes.core.prompt import build_initial_ask_messages
from holmes.core.tool_calling_llm import ToolCallingLLM, ToolCallResult
from holmes.core.tools import pretty_print_toolset_status
from holmes.core.tracing import DummySpan


class SlashCommands(Enum):
    EXIT = ("/exit", "Exit interactive mode")
    HELP = ("/help", "Show help message with all commands")
    RESET = ("/reset", "Reset the conversation context")
    TOOLS_CONFIG = ("/tools", "Show available toolsets and their status")
    TOGGLE_TOOL_OUTPUT = (
        "/auto",
        "Toggle auto-display of tool outputs after responses",
    )
    LAST_OUTPUT = ("/last", "Show all tool outputs from last response")
    CLEAR = ("/clear", "Clear the terminal screen")
    RUN = ("/run", "Run a bash command and optionally share with LLM")
    SHELL = (
        "/shell",
        "Drop into interactive shell, then optionally share session with LLM",
    )
    CONTEXT = ("/context", "Show conversation context size and token count")
    SHOW = ("/show", "Show specific tool output in scrollable view")

    def __init__(self, command, description):
        self.command = command
        self.description = description


SLASH_COMMANDS_REFERENCE = {cmd.command: cmd.description for cmd in SlashCommands}
ALL_SLASH_COMMANDS = [cmd.command for cmd in SlashCommands]


class SlashCommandCompleter(Completer):
    def __init__(self):
        self.commands = SLASH_COMMANDS_REFERENCE

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            word = text
            for cmd, description in self.commands.items():
                if cmd.startswith(word):
                    yield Completion(
                        cmd, start_position=-len(word), display=f"{cmd} - {description}"
                    )


class SmartPathCompleter(Completer):
    """Path completer that works for relative paths starting with ./ or ../"""

    def __init__(self):
        self.path_completer = PathCompleter()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()
        if not words:
            return

        last_word = words[-1]
        # Only complete if the last word looks like a relative path (not absolute paths starting with /)
        if last_word.startswith("./") or last_word.startswith("../"):
            # Create a temporary document with just the path part
            path_doc = Document(last_word, len(last_word))

            for completion in self.path_completer.get_completions(
                path_doc, complete_event
            ):
                yield Completion(
                    completion.text,
                    start_position=completion.start_position - len(last_word),
                    display=completion.display,
                    display_meta=completion.display_meta,
                )


class ConditionalExecutableCompleter(Completer):
    """Executable completer that only works after /run commands"""

    def __init__(self):
        self.executable_completer = ExecutableCompleter()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Only provide executable completion if the line starts with /run
        if text.startswith("/run "):
            # Extract the command part after "/run "
            command_part = text[5:]  # Remove "/run "

            # Only complete the first word (the executable name)
            words = command_part.split()
            if len(words) <= 1:  # Only when typing the first word
                # Create a temporary document with just the command part
                cmd_doc = Document(command_part, len(command_part))

                seen_completions = set()
                for completion in self.executable_completer.get_completions(
                    cmd_doc, complete_event
                ):
                    # Remove duplicates based on text only (display can be FormattedText which is unhashable)
                    if completion.text not in seen_completions:
                        seen_completions.add(completion.text)
                        yield Completion(
                            completion.text,
                            start_position=completion.start_position
                            - len(command_part),
                            display=completion.display,
                            display_meta=completion.display_meta,
                        )


USER_COLOR = "#DEFCC0"  # light green
AI_COLOR = "#00FFFF"  # cyan
TOOLS_COLOR = "magenta"
HELP_COLOR = "cyan"  # same as AI_COLOR for now
ERROR_COLOR = "red"
STATUS_COLOR = "yellow"

WELCOME_BANNER = f"[bold {HELP_COLOR}]Welcome to HolmesGPT:[/bold {HELP_COLOR}] Type '{SlashCommands.EXIT.command}' to exit, '{SlashCommands.HELP.command}' for commands."


def format_tool_call_output(
    tool_call: ToolCallResult, tool_index: Optional[int] = None
) -> str:
    """
    Format a single tool call result for display in a rich panel.

    Args:
        tool_call: ToolCallResult object containing the tool execution result
        tool_index: Optional 1-based index of the tool for /show command

    Returns:
        Formatted string for display in a rich panel
    """
    result = tool_call.result
    output_str = result.get_stringified_data()

    color = result.status.to_color()
    MAX_CHARS = 500
    if len(output_str) == 0:
        content = f"[{color}]<empty>[/{color}]"
    elif len(output_str) > MAX_CHARS:
        truncated = output_str[:MAX_CHARS].strip()
        remaining_chars = len(output_str) - MAX_CHARS
        show_hint = f"/show {tool_index}" if tool_index else "/show"
        content = f"[{color}]{truncated}[/{color}]\n\n[dim]... truncated ({remaining_chars:,} more chars) - {show_hint} to view full output[/dim]"
    else:
        content = f"[{color}]{output_str}[/{color}]"

    return content


def build_modal_title(tool_call: ToolCallResult, wrap_status: str) -> str:
    """Build modal title with navigation instructions."""
    return f"{tool_call.description} (exit: q, nav: ↑↓/j/k/g/G/d/u/f/b/space, wrap: w [{wrap_status}])"


def handle_show_command(
    show_arg: str, all_tool_calls_history: List[ToolCallResult], console: Console
) -> None:
    """Handle the /show command to display tool outputs."""
    if not all_tool_calls_history:
        console.print(
            f"[bold {ERROR_COLOR}]No tool calls available in the conversation.[/bold {ERROR_COLOR}]"
        )
        return

    if not show_arg:
        # Show list of available tools
        console.print(
            f"[bold {STATUS_COLOR}]Available tool outputs:[/bold {STATUS_COLOR}]"
        )
        for i, tool_call in enumerate(all_tool_calls_history):
            console.print(f"  {i+1}. {tool_call.description}")
        console.print("[dim]Usage: /show <number> or /show <tool_name>[/dim]")
        return

    # Find tool by number or name
    tool_to_show = None
    try:
        tool_index = int(show_arg) - 1  # Convert to 0-based index
        if 0 <= tool_index < len(all_tool_calls_history):
            tool_to_show = all_tool_calls_history[tool_index]
        else:
            console.print(
                f"[bold {ERROR_COLOR}]Invalid tool index. Use 1-{len(all_tool_calls_history)}[/bold {ERROR_COLOR}]"
            )
            return
    except ValueError:
        # Try to find by tool name/description
        for tool_call in all_tool_calls_history:
            if show_arg.lower() in tool_call.description.lower():
                tool_to_show = tool_call
                break

        if not tool_to_show:
            console.print(
                f"[bold {ERROR_COLOR}]Tool not found: {show_arg}[/bold {ERROR_COLOR}]"
            )
            return

    # Show the tool output in modal
    show_tool_output_modal(tool_to_show, console)


def show_tool_output_modal(tool_call: ToolCallResult, console: Console) -> None:
    """
    Display a tool output in a scrollable modal window.

    Args:
        tool_call: ToolCallResult object to display
        console: Rich console (for fallback display)
    """
    try:
        # Get the full output
        output = tool_call.result.get_stringified_data()
        title = build_modal_title(tool_call, "off")  # Word wrap starts disabled

        # Create text area with the output
        text_area = TextArea(
            text=output,
            read_only=True,
            scrollbar=True,
            line_numbers=False,
            wrap_lines=False,  # Disable word wrap by default
        )

        # Create header
        header = Window(
            FormattedTextControl(title),
            height=1,
            style="reverse",
        )

        # Create layout
        layout = Layout(
            HSplit(
                [
                    header,
                    text_area,
                ]
            )
        )

        # Create key bindings
        bindings = KeyBindings()

        # Exit commands
        @bindings.add("q")
        @bindings.add("escape")
        def _(event):
            event.app.exit()

        @bindings.add("c-c")
        def _(event):
            event.app.exit()

        # Vim/less-like navigation
        @bindings.add("j")
        @bindings.add("down")
        def _(event):
            event.app.layout.focus(text_area)
            text_area.buffer.cursor_down()

        @bindings.add("k")
        @bindings.add("up")
        def _(event):
            event.app.layout.focus(text_area)
            text_area.buffer.cursor_up()

        @bindings.add("g")
        @bindings.add("home")
        def _(event):
            event.app.layout.focus(text_area)
            text_area.buffer.cursor_position = 0

        @bindings.add("G")
        @bindings.add("end")
        def _(event):
            event.app.layout.focus(text_area)
            # Go to last line, then to beginning of that line
            text_area.buffer.cursor_position = len(text_area.buffer.text)
            text_area.buffer.cursor_left(
                count=text_area.buffer.document.cursor_position_col
            )

        @bindings.add("d")
        @bindings.add("c-d")
        @bindings.add("pagedown")
        def _(event):
            event.app.layout.focus(text_area)
            # Get current window height and scroll by half
            window_height = event.app.output.get_size().rows - 1  # -1 for header
            scroll_amount = max(1, window_height // 2)
            for _ in range(scroll_amount):
                text_area.buffer.cursor_down()

        @bindings.add("u")
        @bindings.add("c-u")
        @bindings.add("pageup")
        def _(event):
            event.app.layout.focus(text_area)
            # Get current window height and scroll by half
            window_height = event.app.output.get_size().rows - 1  # -1 for header
            scroll_amount = max(1, window_height // 2)
            for _ in range(scroll_amount):
                text_area.buffer.cursor_up()

        @bindings.add("f")
        @bindings.add("c-f")
        @bindings.add("space")
        def _(event):
            event.app.layout.focus(text_area)
            # Get current window height and scroll by full page
            window_height = event.app.output.get_size().rows - 1  # -1 for header
            scroll_amount = max(1, window_height)
            for _ in range(scroll_amount):
                text_area.buffer.cursor_down()

        @bindings.add("b")
        @bindings.add("c-b")
        def _(event):
            event.app.layout.focus(text_area)
            # Get current window height and scroll by full page
            window_height = event.app.output.get_size().rows - 1  # -1 for header
            scroll_amount = max(1, window_height)
            for _ in range(scroll_amount):
                text_area.buffer.cursor_up()

        @bindings.add("w")
        def _(event):
            # Toggle word wrap
            text_area.wrap_lines = not text_area.wrap_lines
            # Update the header to show current wrap state
            wrap_status = "on" if text_area.wrap_lines else "off"
            new_title = build_modal_title(tool_call, wrap_status)
            header.content = FormattedTextControl(new_title)

        # Create and run application
        app: Application = Application(
            layout=layout,
            key_bindings=bindings,
            full_screen=True,
        )

        app.run()

    except Exception as e:
        # Fallback to regular display
        console.print(f"[bold red]Error showing modal: {e}[/bold red]")
        console.print(format_tool_call_output(tool_call))


def handle_context_command(messages, ai: ToolCallingLLM, console: Console) -> None:
    """Handle the /context command to show conversation context statistics."""
    if messages is None:
        console.print(
            f"[bold {STATUS_COLOR}]No conversation context yet.[/bold {STATUS_COLOR}]"
        )
        return

    # Calculate context statistics
    total_tokens = ai.llm.count_tokens_for_message(messages)
    max_context_size = ai.llm.get_context_window_size()
    max_output_tokens = ai.llm.get_maximum_output_token()
    available_tokens = max_context_size - total_tokens - max_output_tokens

    # Analyze token distribution by role and tool calls
    role_token_usage: DefaultDict[str, int] = defaultdict(int)
    tool_token_usage: DefaultDict[str, int] = defaultdict(int)
    tool_call_counts: DefaultDict[str, int] = defaultdict(int)

    for msg in messages:
        role = msg.get("role", "unknown")
        msg_tokens = ai.llm.count_tokens_for_message([msg])
        role_token_usage[role] += msg_tokens

        # Track individual tool usage
        if role == "tool":
            tool_name = msg.get("name", "unknown_tool")
            tool_token_usage[tool_name] += msg_tokens
            tool_call_counts[tool_name] += 1

    # Display context information
    console.print(f"[bold {STATUS_COLOR}]Conversation Context:[/bold {STATUS_COLOR}]")
    console.print(
        f"  Context used: {total_tokens:,} / {max_context_size:,} tokens ({(total_tokens / max_context_size) * 100:.1f}%)"
    )
    console.print(
        f"  Space remaining: {available_tokens:,} for input ({(available_tokens / max_context_size) * 100:.1f}%) + {max_output_tokens:,} reserved for output ({(max_output_tokens / max_context_size) * 100:.1f}%)"
    )

    # Show token breakdown by role
    console.print("  Token breakdown:")
    for role in ["system", "user", "assistant", "tool"]:
        if role in role_token_usage:
            tokens = role_token_usage[role]
            percentage = (tokens / total_tokens) * 100 if total_tokens > 0 else 0
            role_name = {
                "system": "system prompt",
                "user": "user messages",
                "assistant": "assistant replies",
                "tool": "tool responses",
            }.get(role, role)
            console.print(f"    {role_name}: {tokens:,} tokens ({percentage:.1f}%)")

            # Show top 4 tools breakdown under tool responses
            if role == "tool" and tool_token_usage:
                sorted_tools = sorted(
                    tool_token_usage.items(), key=lambda x: x[1], reverse=True
                )

                # Show top 4 tools
                for tool_name, tool_tokens in sorted_tools[:4]:
                    tool_percentage = (tool_tokens / tokens) * 100 if tokens > 0 else 0
                    call_count = tool_call_counts[tool_name]
                    console.print(
                        f"      {tool_name}: {tool_tokens:,} tokens ({tool_percentage:.1f}%) from {call_count} tool calls"
                    )

                # Show "other" category if there are more than 4 tools
                if len(sorted_tools) > 4:
                    other_tokens = sum(
                        tool_tokens for _, tool_tokens in sorted_tools[4:]
                    )
                    other_calls = sum(
                        tool_call_counts[tool_name] for tool_name, _ in sorted_tools[4:]
                    )
                    other_percentage = (
                        (other_tokens / tokens) * 100 if tokens > 0 else 0
                    )
                    other_count = len(sorted_tools) - 4
                    console.print(
                        f"      other ({other_count} tools): {other_tokens:,} tokens ({other_percentage:.1f}%) from {other_calls} tool calls"
                    )

    if available_tokens < 0:
        console.print(
            f"[bold {ERROR_COLOR}]⚠️  Context will be truncated on next LLM call[/bold {ERROR_COLOR}]"
        )


def prompt_for_llm_sharing(
    session: PromptSession, style: Style, content: str, content_type: str
) -> Optional[str]:
    """
    Prompt user to share content with LLM and return formatted user input.

    Args:
        session: PromptSession for user input
        style: Style for prompts
        content: The content to potentially share (command output, shell session, etc.)
        content_type: Description of content type (e.g., "command", "shell session")

    Returns:
        Formatted user input string if user chooses to share, None otherwise
    """
    # Create a temporary session without history for y/n prompts
    temp_session = PromptSession(history=InMemoryHistory())  # type: ignore

    share_prompt = temp_session.prompt(
        [("class:prompt", f"Share {content_type} with LLM? (Y/n): ")], style=style
    )

    if not share_prompt.lower().startswith("n"):
        comment_prompt = temp_session.prompt(
            [("class:prompt", "Optional comment/question (press Enter to skip): ")],
            style=style,
        )

        user_input = f"I {content_type}:\\n\\n```\\n{content}\\n```\\n\\n"

        if comment_prompt.strip():
            user_input += f"Comment/Question: {comment_prompt.strip()}"

        return user_input

    return None


def handle_run_command(
    bash_command: str, session: PromptSession, style: Style, console: Console
) -> Optional[str]:
    """
    Handle the /run command to execute a bash command.

    Args:
        bash_command: The bash command to execute
        session: PromptSession for user input
        style: Style for prompts
        console: Rich console for output

    Returns:
        Formatted user input string if user chooses to share, None otherwise
    """
    if not bash_command:
        console.print(
            f"[bold {ERROR_COLOR}]Usage: /run <bash_command>[/bold {ERROR_COLOR}]"
        )
        return None

    result = None
    output = ""
    error_message = ""

    try:
        console.print(
            f"[bold {STATUS_COLOR}]Running: {bash_command}[/bold {STATUS_COLOR}]"
        )
        result = subprocess.run(
            bash_command, shell=True, capture_output=True, text=True
        )

        output = result.stdout + result.stderr
        if result.returncode == 0:
            console.print(
                f"[bold green]✓ Command succeeded (exit code: {result.returncode})[/bold green]"
            )
        else:
            console.print(
                f"[bold {ERROR_COLOR}]✗ Command failed (exit code: {result.returncode})[/bold {ERROR_COLOR}]"
            )

        if output.strip():
            console.print(
                Panel(
                    output,
                    padding=(1, 2),
                    border_style="white",
                    title="Command Output",
                    title_align="left",
                )
            )

    except KeyboardInterrupt:
        error_message = "Command interrupted by user"
        console.print(f"[bold {ERROR_COLOR}]{error_message}[/bold {ERROR_COLOR}]")
    except Exception as e:
        error_message = f"Error running command: {e}"
        console.print(f"[bold {ERROR_COLOR}]{error_message}[/bold {ERROR_COLOR}]")

    # Build command output for sharing
    command_output = f"ran the command: `{bash_command}`\n\n"
    if result is not None:
        command_output += f"Exit code: {result.returncode}\n\n"
        if output.strip():
            command_output += f"Output:\n{output}"
    elif error_message:
        command_output += f"Error: {error_message}"

    return prompt_for_llm_sharing(session, style, command_output, "ran a command")


def handle_shell_command(
    session: PromptSession, style: Style, console: Console
) -> Optional[str]:
    """
    Handle the /shell command to start an interactive shell session.

    Args:
        session: PromptSession for user input
        style: Style for prompts
        console: Rich console for output

    Returns:
        Formatted user input string if user chooses to share, None otherwise
    """
    console.print(
        f"[bold {STATUS_COLOR}]Starting interactive shell. Type 'exit' to return to HolmesGPT.[/bold {STATUS_COLOR}]"
    )
    console.print(
        "[dim]Shell session will be recorded and can be shared with LLM when you exit.[/dim]"
    )

    # Create a temporary file to capture shell session
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".log") as session_file:
        session_log_path = session_file.name

        try:
            # Start shell with script command to capture session
            shell_env = os.environ.copy()
            shell_env["PS1"] = "\\u@\\h:\\w$ "  # Set a clean prompt

            subprocess.run(f"script -q {session_log_path}", shell=True, env=shell_env)

            # Read the session log
            session_output = ""
            try:
                with open(session_log_path, "r") as f:
                    session_output = f.read()
            except Exception as e:
                console.print(
                    f"[bold {ERROR_COLOR}]Error reading session log: {e}[/bold {ERROR_COLOR}]"
                )
                return None

            if session_output.strip():
                console.print(
                    f"[bold {STATUS_COLOR}]Shell session ended.[/bold {STATUS_COLOR}]"
                )
                return prompt_for_llm_sharing(
                    session, style, session_output, "had an interactive shell session"
                )
            else:
                console.print(
                    f"[bold {STATUS_COLOR}]Shell session ended with no output.[/bold {STATUS_COLOR}]"
                )
                return None

        except KeyboardInterrupt:
            console.print(
                f"[bold {STATUS_COLOR}]Shell session interrupted.[/bold {STATUS_COLOR}]"
            )
            return None
        except Exception as e:
            console.print(
                f"[bold {ERROR_COLOR}]Error starting shell: {e}[/bold {ERROR_COLOR}]"
            )
            return None


def find_tool_index_in_history(
    tool_call: ToolCallResult, all_tool_calls_history: List[ToolCallResult]
) -> Optional[int]:
    """Find the 1-based index of a tool call in the complete history."""
    for i, historical_tool in enumerate(all_tool_calls_history):
        if historical_tool.tool_call_id == tool_call.tool_call_id:
            return i + 1  # 1-based index
    return None


def handle_last_command(
    last_response, console: Console, all_tool_calls_history: List[ToolCallResult]
) -> None:
    """Handle the /last command to show recent tool outputs."""
    if last_response is None or not last_response.tool_calls:
        console.print(
            f"[bold {ERROR_COLOR}]No tool calls available from the last response.[/bold {ERROR_COLOR}]"
        )
        return

    console.print(
        f"[bold {TOOLS_COLOR}]Used {len(last_response.tool_calls)} tools[/bold {TOOLS_COLOR}]"
    )
    for tool_call in last_response.tool_calls:
        tool_index = find_tool_index_in_history(tool_call, all_tool_calls_history)
        preview_output = format_tool_call_output(tool_call, tool_index)
        title = f"{tool_call.result.status.to_emoji()} {tool_call.description} -> returned {tool_call.result.return_code}"

        console.print(
            Panel(
                preview_output,
                padding=(1, 2),
                border_style=TOOLS_COLOR,
                title=title,
            )
        )


def display_recent_tool_outputs(
    tool_calls: List[ToolCallResult],
    console: Console,
    all_tool_calls_history: List[ToolCallResult],
) -> None:
    """Display recent tool outputs in rich panels (for auto-display after responses)."""
    console.print(
        f"[bold {TOOLS_COLOR}]Used {len(tool_calls)} tools[/bold {TOOLS_COLOR}]"
    )
    for tool_call in tool_calls:
        tool_index = find_tool_index_in_history(tool_call, all_tool_calls_history)
        preview_output = format_tool_call_output(tool_call, tool_index)
        title = f"{tool_call.result.status.to_emoji()} {tool_call.description} -> returned {tool_call.result.return_code}"

        console.print(
            Panel(
                preview_output,
                padding=(1, 2),
                border_style=TOOLS_COLOR,
                title=title,
            )
        )


def run_interactive_loop(
    ai: ToolCallingLLM,
    console: Console,
    system_prompt_rendered: str,
    initial_user_input: Optional[str],
    include_files: Optional[List[Path]],
    post_processing_prompt: Optional[str],
    show_tool_output: bool,
    tracer=None,
) -> None:
    # Initialize tracer - use DummySpan if no tracer provided
    if tracer is None:
        tracer = DummySpan()

    style = Style.from_dict(
        {
            "prompt": USER_COLOR,
            "bottom-toolbar": "#000000 bg:#ff0000",
            "bottom-toolbar.text": "#aaaa44 bg:#aa4444",
        }
    )

    # Create merged completer with slash commands, conditional executables, and smart paths
    slash_completer = SlashCommandCompleter()
    executable_completer = ConditionalExecutableCompleter()
    path_completer = SmartPathCompleter()

    command_completer = merge_completers(
        [slash_completer, executable_completer, path_completer]
    )

    # Use file-based history
    history_file = os.path.expanduser("~/.holmes/history")
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    history = FileHistory(history_file)
    if initial_user_input:
        history.append_string(initial_user_input)

    # Create custom key bindings for Ctrl+C behavior
    bindings = KeyBindings()
    status_message = ""

    @bindings.add("c-c")
    def _(event):
        """Handle Ctrl+C: clear input if text exists, otherwise quit."""
        buffer = event.app.current_buffer
        if buffer.text:
            nonlocal status_message
            status_message = f"Input cleared. Use {SlashCommands.EXIT.command} or Ctrl+C again to quit."
            buffer.reset()

            # call timer to clear status message after 3 seconds
            def clear_status():
                nonlocal status_message
                status_message = ""
                event.app.invalidate()

            timer = threading.Timer(3, clear_status)
            timer.start()
        else:
            # Quit if no text
            raise KeyboardInterrupt()

    def get_bottom_toolbar():
        if status_message:
            return [("bg:#ff0000 fg:#000000", status_message)]
        return None

    session = PromptSession(
        completer=command_completer,
        history=history,
        complete_style=CompleteStyle.COLUMN,
        reserve_space_for_menu=12,
        key_bindings=bindings,
        bottom_toolbar=get_bottom_toolbar,
    )  # type: ignore

    input_prompt = [("class:prompt", "User: ")]

    console.print(WELCOME_BANNER)
    if initial_user_input:
        console.print(
            f"[bold {USER_COLOR}]User:[/bold {USER_COLOR}] {initial_user_input}"
        )
    messages = None
    last_response = None
    all_tool_calls_history: List[
        ToolCallResult
    ] = []  # Track all tool calls throughout conversation

    while True:
        try:
            if initial_user_input:
                user_input = initial_user_input
                initial_user_input = None
            else:
                user_input = session.prompt(input_prompt, style=style)  # type: ignore

            if user_input.startswith("/"):
                original_input = user_input.strip()
                command = original_input.lower()

                # Handle prefix matching for slash commands
                matches = [cmd for cmd in ALL_SLASH_COMMANDS if cmd.startswith(command)]
                if len(matches) == 1:
                    command = matches[0]
                elif len(matches) > 1:
                    console.print(
                        f"[bold {ERROR_COLOR}]Ambiguous command '{command}'. Matches: {', '.join(matches)}[/bold {ERROR_COLOR}]"
                    )
                    continue

                if command == SlashCommands.EXIT.command:
                    return
                elif command == SlashCommands.HELP.command:
                    console.print(
                        f"[bold {HELP_COLOR}]Available commands:[/bold {HELP_COLOR}]"
                    )
                    for cmd, description in SLASH_COMMANDS_REFERENCE.items():
                        console.print(f"  [bold]{cmd}[/bold] - {description}")
                    continue
                elif command == SlashCommands.RESET.value:
                    console.print(
                        f"[bold {STATUS_COLOR}]Context reset. You can now ask a new question.[/bold {STATUS_COLOR}]"
                    )
                    messages = None
                    last_response = None
                    all_tool_calls_history.clear()
                    continue
                elif command == SlashCommands.TOOLS_CONFIG.command:
                    pretty_print_toolset_status(ai.tool_executor.toolsets, console)
                    continue
                elif command == SlashCommands.TOGGLE_TOOL_OUTPUT.command:
                    show_tool_output = not show_tool_output
                    status = "enabled" if show_tool_output else "disabled"
                    console.print(
                        f"[bold yellow]Auto-display of tool outputs {status}.[/bold yellow]"
                    )
                    continue
                elif command == SlashCommands.LAST_OUTPUT.command:
                    handle_last_command(last_response, console, all_tool_calls_history)
                    continue
                elif command == SlashCommands.CLEAR.command:
                    console.clear()
                    continue
                elif command == SlashCommands.CONTEXT.command:
                    handle_context_command(messages, ai, console)
                    continue
                elif command.startswith(SlashCommands.SHOW.command):
                    # Parse the command to extract tool index or name
                    show_arg = original_input[len(SlashCommands.SHOW.command) :].strip()
                    handle_show_command(show_arg, all_tool_calls_history, console)
                    continue
                elif command.startswith(SlashCommands.RUN.command):
                    bash_command = original_input[
                        len(SlashCommands.RUN.command) :
                    ].strip()
                    shared_input = handle_run_command(
                        bash_command, session, style, console
                    )
                    if shared_input is None:
                        continue  # User chose not to share, continue to next input
                    user_input = shared_input
                elif command == SlashCommands.SHELL.command:
                    shared_input = handle_shell_command(session, style, console)
                    if shared_input is None:
                        continue  # User chose not to share or no output, continue to next input
                    user_input = shared_input
                else:
                    console.print(f"Unknown command: {command}")
                    continue
            elif not user_input.strip():
                continue

            if messages is None:
                messages = build_initial_ask_messages(
                    console, system_prompt_rendered, user_input, include_files
                )
            else:
                messages.append({"role": "user", "content": user_input})

            console.print(f"\n[bold {AI_COLOR}]Thinking...[/bold {AI_COLOR}]\n")

            with tracer.start_trace(user_input) as trace_span:
                # Log the user's question as input to the top-level span
                trace_span.log(
                    input=user_input,
                    metadata={"type": "user_question"},
                )
                response = ai.call(
                    messages, post_processing_prompt, trace_span=trace_span
                )
                trace_span.log(
                    output=response.result,
                )
                trace_url = tracer.get_trace_url()

            messages = response.messages  # type: ignore
            last_response = response

            if response.tool_calls:
                all_tool_calls_history.extend(response.tool_calls)

            if show_tool_output and response.tool_calls:
                display_recent_tool_outputs(
                    response.tool_calls, console, all_tool_calls_history
                )
            console.print(
                Panel(
                    Markdown(f"{response.result}"),
                    padding=(1, 2),
                    border_style=AI_COLOR,
                    title=f"[bold {AI_COLOR}]AI Response[/bold {AI_COLOR}]",
                    title_align="left",
                )
            )

            if trace_url:
                console.print(f"🔍 View trace: {trace_url}")

            console.print("")
        except typer.Abort:
            break
        except EOFError:  # Handle Ctrl+D
            break
        except Exception as e:
            logging.error("An error occurred during interactive mode:", exc_info=e)
            console.print(f"[bold {ERROR_COLOR}]Error: {e}[/bold {ERROR_COLOR}]")

    console.print(
        f"[bold {STATUS_COLOR}]Exiting interactive mode.[/bold {STATUS_COLOR}]"
    )
