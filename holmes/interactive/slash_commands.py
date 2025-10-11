"""Slash command definitions for interactive mode."""

from enum import Enum


class SlashCommands(Enum):
    EXIT = ("/exit", "Exit interactive mode")
    HELP = ("/help", "Show help message with all commands")
    CLEAR = ("/clear", "Clear screen and reset conversation context")
    TOOLS_CONFIG = ("/tools", "Show available toolsets and their status")
    TOGGLE_TOOL_OUTPUT = (
        "/auto",
        "Toggle auto-display of tool outputs after responses",
    )
    LAST_OUTPUT = ("/last", "Show all tool outputs from last response")
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
