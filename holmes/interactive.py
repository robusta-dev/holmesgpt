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
    TOOLS = "/tools"


ALL_SLASH_COMMANDS = [cmd.value for cmd in SlashCommands]


class SlashCommandCompleter(Completer):
    def __init__(self, commands: list[str]):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            word = text
            for cmd in self.commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))


WELCOME_BANNER = "[bold cyan]Welcome to HolmesGPT:[/bold cyan] Type '/exit' to exit, '/help' for commands."


USER_COLOR = "#DEFCC0"  # light green
AI_COLOR = "#00FFFF"  # cyan


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
    elif len(output_str) > 100:
        truncated = output_str[:MAX_CHARS].strip()
        remaining_chars = len(output_str) - MAX_CHARS
        content = f"[{color}]{truncated}[/{color}]\n\n[dim]... truncated ({remaining_chars:,} more chars)[/dim]"
    else:
        content = f"[{color}]{output_str}[/{color}]"

    return content


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

    command_completer = SlashCommandCompleter([c.value for c in SlashCommands])
    history = InMemoryHistory()
    if initial_user_input:
        history.append_string(initial_user_input)
    session = PromptSession(completer=command_completer, history=history)  # type: ignore
    input_prompt = [("class:prompt", "User: ")]

    console.print(WELCOME_BANNER)
    if initial_user_input:
        console.print(
            f"[bold {USER_COLOR}]User:[/bold {USER_COLOR}] {initial_user_input}"
        )
    messages = None

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
                    console.print(f"Available commands: {ALL_SLASH_COMMANDS}")
                elif command == SlashCommands.RESET.value:
                    console.print(
                        "[bold yellow]Context reset. You can now ask a new question.[/bold yellow]"
                    )
                    messages = None
                    continue
                elif command == SlashCommands.TOOLS.value:
                    pretty_print_toolset_status(ai.tool_executor.toolsets, console)
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

            console.print("\n[bold blue]Thinking...[/bold blue]\n")
            response = ai.call(messages, post_processing_prompt)
            messages = response.messages  # type: ignore

            if show_tool_output and response.tool_calls:
                console.print(
                    f"[bold magenta]Used {len(response.tool_calls)} tools[/bold magenta]"
                )
                for tool_call in response.tool_calls:
                    preview_output = format_tool_call_output(tool_call)

                    console.print(
                        Panel(
                            preview_output,
                            padding=(1, 2),
                            border_style="magenta",
                            title=f"{tool_call.result.status.to_emoji()} {tool_call.description} -> returned {tool_call.result.return_code}",
                        )
                    )
            console.print(
                Panel(
                    Markdown(f"{response.result}"),
                    padding=(1, 2),
                    border_style=AI_COLOR,
                    title="[bold cyan]AI Response[/bold cyan]",
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
            console.print(f"[bold red]Error: {e}[/bold red]")
    console.print("[bold cyan]Exiting interactive mode.[/bold cyan]")
