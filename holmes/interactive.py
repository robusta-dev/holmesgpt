import logging
from enum import Enum
from typing import Optional, List
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown, Panel

from holmes.core.prompt import build_initial_ask_messages
from holmes.core.tool_calling_llm import ToolCallingLLM, ToolCallResult
from holmes.core.tools import pretty_print_toolset_status


class SlashCommands(Enum):
    EXIT = "/exit"
    HELP = "/help"
    RESET = "/reset"
    TOOLS_CONFIG = "/config"
    TOGGLE_TOOL_OUTPUT = "/toggle-output"
    SHOW_OUTPUT = "/output"


SLASH_COMMANDS_REFERENCE = {
    SlashCommands.EXIT.value: "Exit interactive mode",
    SlashCommands.HELP.value: "Show help message with all commands",
    SlashCommands.RESET.value: "Reset the conversation context",
    SlashCommands.TOOLS_CONFIG.value: "Show available toolsets and their status",
    SlashCommands.TOGGLE_TOOL_OUTPUT.value: "Toggle tool output display on/off",
    SlashCommands.SHOW_OUTPUT.value: "Show all tool outputs from last response",
}

ALL_SLASH_COMMANDS = [cmd.value for cmd in SlashCommands]


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


USER_COLOR = "#DEFCC0"  # light green
AI_COLOR = "#00FFFF"  # cyan
TOOLS_COLOR = "magenta"
HELP_COLOR = "cyan"  # same as AI_COLOR for now
ERROR_COLOR = "red"
STATUS_COLOR = "yellow"

WELCOME_BANNER = f"[bold {HELP_COLOR}]Welcome to HolmesGPT:[/bold {HELP_COLOR}] Type '{SlashCommands.EXIT.value}' to exit, '{SlashCommands.HELP.value}' for commands."


def format_tool_call_output(tool_call: ToolCallResult) -> str:
    """
    Format a single tool call result for display in a rich panel.

    Args:
        tool_call: ToolCallResult object containing the tool execution result

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
        content = f"[{color}]{truncated}[/{color}]\n\n[dim]... truncated ({remaining_chars:,} more chars)[/dim]"
    else:
        content = f"[{color}]{output_str}[/{color}]"

    return content


def display_tool_calls(tool_calls: List[ToolCallResult], console: Console) -> None:
    """
    Display tool calls in rich panels.

    Args:
        tool_calls: List of ToolCallResult objects to display
        console: Rich console for output
    """
    console.print(
        f"[bold {TOOLS_COLOR}]Used {len(tool_calls)} tools[/bold {TOOLS_COLOR}]"
    )
    for tool_call in tool_calls:
        preview_output = format_tool_call_output(tool_call)
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
) -> None:
    style = Style.from_dict(
        {
            "prompt": USER_COLOR,
        }
    )

    command_completer = SlashCommandCompleter()
    history = InMemoryHistory()
    if initial_user_input:
        history.append_string(initial_user_input)
    session = PromptSession(
        completer=command_completer,
        history=history,
    )  # type: ignore
    input_prompt = [("class:prompt", "User: ")]

    console.print(WELCOME_BANNER)
    if initial_user_input:
        console.print(
            f"[bold {USER_COLOR}]User:[/bold {USER_COLOR}] {initial_user_input}"
        )
    messages = None
    last_response = None

    while True:
        try:
            if initial_user_input:
                user_input = initial_user_input
                initial_user_input = None
            else:
                user_input = session.prompt(input_prompt, style=style)  # type: ignore

            if user_input.startswith("/"):
                command = user_input.strip().lower()
                if command == SlashCommands.EXIT.value:
                    return
                elif command == SlashCommands.HELP.value:
                    console.print(
                        f"[bold {HELP_COLOR}]Available commands:[/bold {HELP_COLOR}]"
                    )
                    for cmd, description in SLASH_COMMANDS_REFERENCE.items():
                        console.print(f"  [bold]{cmd}[/bold] - {description}")
                elif command == SlashCommands.RESET.value:
                    console.print(
                        f"[bold {STATUS_COLOR}]Context reset. You can now ask a new question.[/bold {STATUS_COLOR}]"
                    )
                    messages = None
                    continue
                elif command == SlashCommands.TOOLS_CONFIG.value:
                    pretty_print_toolset_status(ai.tool_executor.toolsets, console)
                elif command == SlashCommands.TOGGLE_TOOL_OUTPUT.value:
                    show_tool_output = not show_tool_output
                    status = "enabled" if show_tool_output else "disabled"
                    console.print(
                        f"[bold yellow]Tool output display {status}.[/bold yellow]"
                    )
                elif command == SlashCommands.SHOW_OUTPUT.value:
                    if last_response is None or not last_response.tool_calls:
                        console.print(
                            f"[bold {ERROR_COLOR}]No tool calls available from the last response.[/bold {ERROR_COLOR}]"
                        )
                        continue

                    display_tool_calls(last_response.tool_calls, console)
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
            response = ai.call(messages, post_processing_prompt)
            messages = response.messages  # type: ignore
            last_response = response

            if show_tool_output and response.tool_calls:
                display_tool_calls(response.tool_calls, console)
            console.print(
                Panel(
                    Markdown(f"{response.result}"),
                    padding=(1, 2),
                    border_style=AI_COLOR,
                    title=f"[bold {AI_COLOR}]AI Response[/bold {AI_COLOR}]",
                    title_align="left",
                )
            )
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
