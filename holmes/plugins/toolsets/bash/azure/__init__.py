import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.azure.constants import (
    SAFE_AZURE_COMMANDS,
    BLOCKED_AZURE_OPERATIONS,
)


def create_azure_parser(parent_parser: Any):
    """Create Azure CLI parser with safe command validation."""
    azure_parser = parent_parser.add_parser(
        "az", help="Azure Command Line Interface", exit_on_error=False
    )

    # Add service/command subparser
    azure_parser.add_argument(
        "service", help="Azure service or command (e.g., vm, network, storage)"
    )

    # Capture remaining arguments
    azure_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Azure CLI subcommands, operations, and options",
    )


def validate_azure_service_and_operation(service: str, options: list[str]) -> None:
    """Validate that the Azure service and operation combination is safe."""
    # If no options provided, this is just listing the service help
    if not options:
        return

    # Extract the command path from options
    command_parts = []

    # Find where the actual flags start
    for i, option in enumerate(options):
        if option.startswith("-"):
            break
        command_parts.append(option)
    else:
        # No flags found, all are command parts
        command_parts = options

    # Build full command string and check against allowlist
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

    # Check for blocked operations
    for blocked_op in BLOCKED_AZURE_OPERATIONS:
        if blocked_op in full_command:
            raise ValueError(
                f"Azure command contains blocked operation '{blocked_op}': {full_command}"
            )


def validate_azure_command(cmd: Any) -> None:
    """
    Validate Azure command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    # Validate service and operation
    if hasattr(cmd, "options") and cmd.options:
        validate_azure_service_and_operation(cmd.service, cmd.options)



def stringify_azure_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed Azure command back to safe command string."""
    if command.cmd != "az":
        raise ValueError(f"Expected Azure command, got {command.cmd}")

    # Validate the command
    validate_azure_command(command)

    # Build command parts
    parts = ["az", command.service]

    if hasattr(command, "options") and command.options:
        parts.extend(command.options)

    return " ".join(escape_shell_args(parts))
