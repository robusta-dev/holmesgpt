import argparse
import json
import shlex
from typing import Any

from holmes.plugins.toolsets.bash.grep import create_grep_parser, stringify_grep_command
from holmes.plugins.toolsets.bash.kubectl import (
    create_kubectl_parser,
    stringify_kubectl_command,
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parser for commands", exit_on_error=False
    )
    commands_parser = parser.add_subparsers(
        dest="cmd", required=True, help="The tool to command (e.g., kubectl)"
    )

    create_kubectl_parser(commands_parser)
    create_grep_parser(commands_parser)
    return parser


def stringify_command(command: Any, original_command: str, config=None) -> str:
    if command.cmd == "kubectl":
        return stringify_kubectl_command(command, config)
    elif command.cmd == "grep":
        return stringify_grep_command(command)
    else:
        raise ValueError(
            f"Unsupported command '{command.cmd}' in {original_command}. Supported commands are: kubectl, grep"
        )


command_parser = create_parser()


def split_into_separate_commands(command_str: str) -> list[list[str]]:
    """
    Splits a single bash command into sub commands based on the pipe '|' delimiter.

    Example:
        >>> "ls -l" -> [
            ['ls', '-l']
        ]
        >>> "kubectl get pods | grep holmes" -> [
            ['kubectl', 'get', 'pods'],
            ['grep', 'holmes']
        ]
    """
    parts = shlex.split(command_str)
    if not parts:
        return []

    commands_list: list[list[str]] = []
    current_command: list[str] = []

    for part in parts:
        if part == "|":
            if current_command:
                commands_list.append(current_command)
            current_command = []
        else:
            current_command.append(part)

    if current_command:
        commands_list.append(current_command)

    print(json.dumps(commands_list, indent=2))
    return commands_list


def make_command_safe(command_str: str, config=None) -> str:
    commands = split_into_separate_commands(command_str)

    safe_commands = [
        command_parser.parse_args(command_parts) for command_parts in commands
    ]
    safe_commands_str = [
        stringify_command(cmd, original_command=command_str, config=config)
        for cmd in safe_commands
    ]

    return " | ".join(safe_commands_str)
