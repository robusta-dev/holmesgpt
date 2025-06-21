import logging
from enum import Enum
from typing import Optional, List
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from holmes.core.prompt import build_initial_ask_messages
from holmes.core.tool_calling_llm import ToolCallingLLM


class SlashCommands(Enum):
    EXIT = "/exit"
    HELP = "/help"
    RESET = "/reset"


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


WELCOME_BANNER = Rule(
    "[bold cyan]Entering interactive mode. Type '/exit' to exit, '/help' for more commands.[/bold cyan]"
)


def run_interactive_loop(
    ai: ToolCallingLLM,
    console: Console,
    system_prompt_rendered: str,
    user_input: Optional[str],
    include_files: Optional[List[Path]],
    post_processing_prompt: Optional[str],
    show_tool_output: bool,
) -> None:
    style = Style.from_dict(
        {
            "prompt": "#00ffff",  # cyan
        }
    )

    command_completer = SlashCommandCompleter([c.value for c in SlashCommands])
    session = PromptSession(completer=command_completer)  # type: ignore
    input_prompt = [("class:prompt", "User> ")]

    console.print(WELCOME_BANNER)
    if user_input:
        console.print("[bold yellow]User:[/bold yellow] " + user_input)

    if not user_input:
        console.print(WELCOME_BANNER)
        user_input = session.prompt(input_prompt, style=style)  # type: ignore

    messages = build_initial_ask_messages(
        console, system_prompt_rendered, user_input, include_files
    )

    while True:
        try:
            messages.append({"role": "user", "content": user_input})
            console.print("[bold blue]Thinking...[/bold blue]")
            response = ai.call(messages, post_processing_prompt)
            messages = response.messages  # type: ignore

            if show_tool_output and response.tool_calls:
                for tool_call in response.tool_calls:
                    console.print("[bold magenta]Used Tool:[/bold magenta]", end="")
                    console.print(
                        f"{tool_call.description}. Output=\n{tool_call.result}",
                        markup=False,
                    )
            console.print("[bold green]AI:[/bold green]", end=" ")
            console.print(Markdown(response.result))  # type: ignore

            # fetch input until we get 'real input' that isn't a slash command
            while True:
                user_input = session.prompt(input_prompt, style=style)  # type: ignore
                if user_input.startswith("/"):
                    command = user_input.strip().lower()
                    if command == SlashCommands.EXIT.value:
                        return
                    elif command == SlashCommands.HELP.value:
                        console.print("Available commands: /exit, /help, /reset")
                    elif command == SlashCommands.RESET.value:
                        console.print(
                            "[bold yellow]Context reset. You can now ask a new question.[/bold yellow]"
                        )
                        user_input = session.prompt(input_prompt, style=style)  # type: ignore
                        messages = build_initial_ask_messages(
                            console, system_prompt_rendered, user_input, include_files
                        )
                    else:
                        print(f"Unknown command: {command}")
                    continue
                elif not user_input.strip():
                    continue
                else:
                    break

        except typer.Abort:
            break
        except EOFError:  # Handle Ctrl+D
            break
        except Exception as e:
            logging.error("An error occurred during interactive mode:", exc_info=e)
            console.print(f"[bold red]Error: {e}[/bold red]")
    console.print("[bold cyan]Exiting interactive mode.[/bold cyan]")
