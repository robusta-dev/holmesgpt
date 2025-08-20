import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.azure.constants import (
    SAFE_AZURE_COMMANDS,
    BLOCKED_AZURE_OPERATIONS,
)


class AzureCommand(BashCommand):
    def __init__(self):
        super().__init__("az")

    def add_parser(self, parent_parser: Any):
        azure_parser = parent_parser.add_parser(
            "az", help="Azure Command Line Interface", exit_on_error=False
        )

        azure_parser.add_argument(
            "service", help="Azure service or command (e.g., vm, network, storage)"
        )

        azure_parser.add_argument(
            "options",
            nargs=argparse.REMAINDER,
            default=[],
            help="Azure CLI subcommands, operations, and options",
        )
        return azure_parser

    def validate_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> None:
        if hasattr(command, "options") and command.options:
            validate_azure_service_and_operation(command.service, command.options)

    def stringify_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> str:
        parts = ["az", command.service]

        if hasattr(command, "options") and command.options:
            parts.extend(command.options)

        return " ".join(escape_shell_args(parts))


# Keep old functions for backward compatibility temporarily
def create_azure_parser(parent_parser: Any):
    azure_command = AzureCommand()
    return azure_command.add_parser(parent_parser)


def validate_azure_service_and_operation(service: str, options: list[str]) -> None:
    # If no options provided, this is just listing the service help
    if not options:
        return

    command_parts = []

    for i, option in enumerate(options):
        if option.startswith("-"):
            break
        command_parts.append(option)
    else:
        command_parts = options

    full_command = " ".join([service] + command_parts)

    if full_command not in SAFE_AZURE_COMMANDS:
        # Try to provide helpful error message
        matching_commands = [
            cmd for cmd in SAFE_AZURE_COMMANDS if cmd.startswith(service)
        ]
        if matching_commands:
            sample_commands = ", ".join(sorted(matching_commands)[:5])
            if len(matching_commands) > 5:
                sample_commands += f" (and {len(matching_commands) - 5} more)"
            raise ValueError(
                f"Azure command '{full_command}' is not in the allowlist. "
                f"Sample allowed commands for '{service}': {sample_commands}"
            )
        else:
            raise ValueError(
                f"Azure service '{service}' is not supported or command '{full_command}' is not allowed"
            )

    for blocked_op in BLOCKED_AZURE_OPERATIONS:
        if blocked_op in full_command:
            raise ValueError(
                f"Azure command contains blocked operation '{blocked_op}': {full_command}"
            )
