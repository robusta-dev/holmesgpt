"""Custom completers for interactive mode."""

from typing import List

from prompt_toolkit.completion import Completer, Completion, merge_completers
from prompt_toolkit.completion.filesystem import ExecutableCompleter, PathCompleter
from prompt_toolkit.document import Document

from holmes.core.tool_calling_llm import ToolCallResult
from holmes.interactive.slash_commands import (
    SLASH_COMMANDS_REFERENCE,
)


class SlashCommandCompleter(Completer):
    """Completer for slash commands."""

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


class ShowCommandCompleter(Completer):
    """Completer that provides suggestions for /show command based on tool call history"""

    def __init__(self):
        self.tool_calls_history: List[ToolCallResult] = []

    def update_history(self, tool_calls_history: List[ToolCallResult]):
        """Update the tool calls history for completion suggestions"""
        self.tool_calls_history = tool_calls_history

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Only provide completion if the line starts with /show
        if text.startswith("/show "):
            # Extract the argument part after "/show "
            show_part = text[6:]  # Remove "/show "

            # Don't complete if there are already multiple words
            words = show_part.split()
            if len(words) > 1:
                return

            # Provide completions based on available tool calls
            if self.tool_calls_history:
                for i, tool_call in enumerate(self.tool_calls_history):
                    tool_index = str(i + 1)  # 1-based index
                    tool_description = tool_call.description

                    # Complete tool index numbers (show all if empty, or filter by what user typed)
                    if (
                        not show_part
                        or tool_index.startswith(show_part)
                        or show_part.lower() in tool_description.lower()
                    ):
                        yield Completion(
                            tool_index,
                            start_position=-len(show_part),
                            display=f"{tool_index} - {tool_description}",
                        )


def create_merged_completer(show_completer: ShowCommandCompleter) -> Completer:
    """Create the merged completer with all components."""
    slash_completer = SlashCommandCompleter()
    executable_completer = ConditionalExecutableCompleter()
    path_completer = SmartPathCompleter()

    return merge_completers(
        [slash_completer, executable_completer, show_completer, path_completer]
    )
