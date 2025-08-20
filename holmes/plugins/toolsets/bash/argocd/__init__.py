import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.argocd.constants import (
    SAFE_ARGOCD_COMMANDS,
    BLOCKED_ARGOCD_OPERATIONS,
)


class ArgocdCommand(BashCommand):
    def __init__(self):
        super().__init__("argocd")

    def add_parser(self, parent_parser: Any):
        """Create Argo CD CLI parser with safe command validation."""
        argocd_parser = parent_parser.add_parser(
            "argocd", help="Argo CD Command Line Interface", exit_on_error=False
        )

        # Add command subparser
        argocd_parser.add_argument(
            "command", help="Argo CD command (e.g., app, cluster, proj, repo)"
        )

        # Capture remaining arguments
        argocd_parser.add_argument(
            "options",
            nargs=argparse.REMAINDER,
            default=[],
            help="Argo CD CLI subcommands, operations, and options",
        )
        return argocd_parser

    def validate_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> None:
        validate_argocd_command(command)

    def stringify_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> str:
        """Convert parsed Argo CD command back to safe command string."""
        parts = ["argocd", command.command]

        if hasattr(command, "options") and command.options:
            parts.extend(command.options)

        return " ".join(escape_shell_args(parts))


def create_argocd_parser(parent_parser: Any):
    argocd_command = ArgocdCommand()
    return argocd_command.add_parser(parent_parser)


def validate_argocd_command_and_operation(command: str, options: list[str]) -> None:
    """Validate that the Argo CD command and operation combination is safe."""
    # Check if this is a top-level command
    if command not in SAFE_ARGOCD_COMMANDS:
        allowed_commands = ", ".join(sorted(SAFE_ARGOCD_COMMANDS.keys()))
        raise ValueError(
            f"Argo CD command '{command}' is not in the allowlist. "
            f"Allowed commands: {allowed_commands}"
        )

    command_config = SAFE_ARGOCD_COMMANDS[command]

    # Handle commands with no subcommands (like version, context)
    if isinstance(command_config, set) and len(command_config) == 0:
        # This command has no subcommands, only flags are allowed
        return

    # If no options provided, this might be just showing command help
    if not options:
        return

    # Extract the operation from options
    operation_parts = []

    # Find where the actual flags start
    for i, option in enumerate(options):
        if option.startswith("-"):
            break
        operation_parts.append(option)
    else:
        # No flags found, all are operation parts
        operation_parts = options

    # For commands with subcommands, validate the operation
    if isinstance(command_config, set) and len(command_config) > 0:
        if operation_parts:
            operation = operation_parts[0]
            if operation not in command_config:
                allowed_ops = ", ".join(sorted(command_config))
                raise ValueError(
                    f"Operation '{operation}' not allowed for command '{command}'. "
                    f"Allowed operations: {allowed_ops}"
                )

    # Check for blocked operations in the full command
    full_command = " ".join([command] + operation_parts)
    for blocked_op in BLOCKED_ARGOCD_OPERATIONS:
        if blocked_op in full_command:
            raise ValueError(
                f"Argo CD command contains blocked operation '{blocked_op}': {full_command}"
            )


def validate_argocd_command(cmd: Any) -> None:
    """
    Validate Argo CD command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    # Validate command and operation
    if hasattr(cmd, "options") and cmd.options:
        validate_argocd_command_and_operation(cmd.command, cmd.options)


def stringify_argocd_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    argocd_command = ArgocdCommand()
    return argocd_command.stringify_command(command, original_command, config)
