import argparse
import shlex
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.grep import create_grep_parser, stringify_grep_command
from holmes.plugins.toolsets.bash.kubectl import KubectlCommand
from holmes.plugins.toolsets.bash.aws import AWSCommand
from holmes.plugins.toolsets.bash.azure import Azurecommand
from holmes.plugins.toolsets.bash.argocd import ArgocdCommand
from holmes.plugins.toolsets.bash.docker import DockerCommand
from holmes.plugins.toolsets.bash.helm import HelmCommand
# Utilities imports
from holmes.plugins.toolsets.bash.utilities.cut import CutCommand
from holmes.plugins.toolsets.bash.utilities.sort import SortCommand
from holmes.plugins.toolsets.bash.utilities.uniq import UniqCommand
from holmes.plugins.toolsets.bash.utilities.head import HeadCommand
from holmes.plugins.toolsets.bash.utilities.tail import TailCommand
from holmes.plugins.toolsets.bash.utilities.wc import WCCommand
from holmes.plugins.toolsets.bash.utilities.tr import TrCommand
from holmes.plugins.toolsets.bash.utilities.base64_util import Base64Command
from holmes.plugins.toolsets.bash.utilities.jq import JqCommand
from holmes.plugins.toolsets.bash.utilities.awk import AwkCommand
from holmes.plugins.toolsets.bash.utilities.sed import SedCommand


commands:list[BashCommand] = [
    WCCommand(),
    KubectlCommand(), 
    AWSCommand(),
    Azurecommand(),
    ArgocdCommand(),
    DockerCommand(),
    HelmCommand(),
    CutCommand(),
    SortCommand(),
    UniqCommand(),
    HeadCommand(),
    TailCommand(),
    TrCommand(),
    Base64Command(),
    JqCommand(),
    AwkCommand(),
    SedCommand()
]



def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="command_parser",  # Set explicit program name
        description="Parser for commands",
        exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts with -h in subcommands
    )
    commands_parser = parser.add_subparsers(
        dest="cmd", required=True, help="The tool to command (e.g., kubectl)"
    )

    for command in commands:
        command.add_parser(commands_parser)

    return parser

def validate_command(command: Any, original_command: str, config: Optional[BashExecutorConfig]):

    pass

def stringify_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    
    bash_command_instance = next((cmd for cmd in commands if cmd.name == command.cmd), None)

    if bash_command_instance:
        return bash_command_instance.st (command, original_command, config)
    elif command.cmd == "grep":
        return stringify_grep_command(command)
    elif command.cmd == "aws":
        return stringify_aws_command(command, original_command, config)
    elif command.cmd == "az":
        return stringify_azure_command(command, original_command, config)
    elif command.cmd == "argocd":
        return stringify_argocd_command(command, original_command, config)
    elif command.cmd == "docker":
        return stringify_docker_command(command, original_command, config)
    elif command.cmd == "helm":
        return stringify_helm_command(command, original_command, config)
    # Handle utilities
    elif command.cmd == "cut":
        return stringify_cut_command(command, original_command, config)
    elif command.cmd == "sort":
        return stringify_sort_command(command, original_command, config)
    elif command.cmd == "uniq":
        return stringify_uniq_command(command, original_command, config)
    elif command.cmd == "head":
        return stringify_head_command(command, original_command, config)
    elif command.cmd == "tail":
        return stringify_tail_command(command, original_command, config)
    elif command.cmd == "wc":
        return wc_command.stringify_command(command, original_command, config)
    elif command.cmd == "tr":
        return stringify_tr_command(command, original_command, config)
    elif command.cmd == "base64":
        return stringify_base64_command(command, original_command, config)
    elif command.cmd == "jq":
        return stringify_jq_command(command, original_command, config)
    elif command.cmd == "awk":
        return stringify_awk_command(command, original_command, config)
    elif command.cmd == "sed":
        return stringify_sed_command(command, original_command, config)
    else:
        # This code path should not happen b/c the parsing of the command should catch an unsupported command
        raise ValueError(
            f"Unsupported command '{command.cmd}' in {original_command}. Supported commands are: kubectl, grep, aws, az, argocd, docker, helm, cut, sort, uniq, head, tail, wc, tr, base64, jq, awk, sed"
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
        elif part == "&&":
            raise ValueError(
                'Double ampersand "&&" is not a supported way to chain commands. Run each command separately.'
            )
        else:
            current_command.append(part)

    if current_command:
        commands_list.append(current_command)

    return commands_list


def make_command_safe(command_str: str, config: Optional[BashExecutorConfig]) -> str:
    commands = split_into_separate_commands(command_str)

    try:
        parsed_commands = [
            command_parser.parse_args(command_parts) for command_parts in commands
        ]


        safe_commands = [
            command_parser.parse_args(command_parts) for command_parts in commands
        ]
        if safe_commands and safe_commands[0].cmd == "grep":
            raise ValueError(
                "The command grep can only be used after another command using the pipe `|` character to connect both commands"
            )
        safe_commands_str = [
            stringify_command(cmd, original_command=command_str, config=config)
            for cmd in safe_commands
        ]

        return " | ".join(safe_commands_str)
    except SystemExit:
        # argparse throws a SystemExit error when it can't parse command or arguments
        # This ideally should be captured differently by ensuring all possible args
        # are accounted for in the implementation for each command.
        # When falling back, we raise a generic error
        raise ValueError(
            f"The following command failed to be parsed for safety: {command_str}"
        ) from None
