import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.helm.constants import (
    SAFE_HELM_COMMANDS,
    SAFE_HELM_GET_SUBCOMMANDS,
    SAFE_HELM_SHOW_SUBCOMMANDS,
    BLOCKED_HELM_OPERATIONS,
)


class HelmCommand(BashCommand):
    def __init__(self):
        super().__init__("helm")

    def add_parser(self, parent_parser: Any):
        """Create Helm CLI parser with safe command validation."""
        helm_parser = parent_parser.add_parser(
            "helm", help="Helm Package Manager for Kubernetes", exit_on_error=False
        )

        # Add command subparser
        helm_parser.add_argument(
            "command", help="Helm command (e.g., list, get, status, show)"
        )

        # Capture remaining arguments
        helm_parser.add_argument(
            "options",
            nargs=argparse.REMAINDER,
            default=[],
            help="Helm CLI subcommands, operations, and options",
        )
        return helm_parser

    def validate_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> None:
        if hasattr(command, "options") and command.options:
            validate_helm_command_and_operation(command.command, command.options)

    def stringify_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> str:
        """Convert parsed Helm command back to safe command string."""
        # Build command parts
        parts = ["helm", command.command]

        if hasattr(command, "options") and command.options:
            parts.extend(command.options)

        return " ".join(escape_shell_args(parts))


# Keep old functions for backward compatibility temporarily
def create_helm_parser(parent_parser: Any):
    helm_command = HelmCommand()
    return helm_command.add_parser(parent_parser)


def validate_helm_command_and_operation(command: str, options: list[str]) -> None:
    """Validate that the Helm command and operation combination is safe."""
    # Special handling for commands with subcommands (get, show, repo, etc.)
    if command in ["get", "show", "repo", "dependency"]:
        if not options:
            # Command without subcommand is allowed (shows help)
            return

        subcommand_parts = []

        for i, option in enumerate(options):
            if option.startswith("-"):
                break
            subcommand_parts.append(option)
        else:
            subcommand_parts = options

        if subcommand_parts:
            # Separate command structure from resource names
            command_structure = [command]

            # For get and show commands, first part is the subcommand, rest are resource names
            if command == "get" and len(subcommand_parts) >= 1:
                subcommand = subcommand_parts[0]
                if subcommand not in SAFE_HELM_GET_SUBCOMMANDS:
                    allowed_subcmds = ", ".join(sorted(SAFE_HELM_GET_SUBCOMMANDS))
                    raise ValueError(
                        f"Helm get subcommand '{subcommand}' is not allowed. "
                        f"Allowed subcommands: {allowed_subcmds}"
                    )
                command_structure.append(subcommand)

            elif command == "show" and len(subcommand_parts) >= 1:
                subcommand = subcommand_parts[0]
                if subcommand not in SAFE_HELM_SHOW_SUBCOMMANDS:
                    allowed_subcmds = ", ".join(sorted(SAFE_HELM_SHOW_SUBCOMMANDS))
                    raise ValueError(
                        f"Helm show subcommand '{subcommand}' is not allowed. "
                        f"Allowed subcommands: {allowed_subcmds}"
                    )
                command_structure.append(subcommand)

            elif command == "repo" and subcommand_parts[0] == "list":
                command_structure.extend(["list"])

            elif command == "dependency" and subcommand_parts[0] == "list":
                command_structure.extend(["list"])

            else:
                # For other repo/dependency commands, build full command structure
                full_command = " ".join([command] + subcommand_parts)
                if full_command not in SAFE_HELM_COMMANDS:
                    raise ValueError(
                        f"Helm command '{full_command}' is not in the allowlist"
                    )
                return  # Exit early for these commands

            # For get/show/repo list/dependency list, validate the base command structure is allowed
            base_command = " ".join(command_structure)
            expected_commands = (
                [command, f"{command} {command_structure[1]}"]
                if len(command_structure) > 1
                else [command]
            )

            # Check if the base command or expected pattern is in allowlist
            if not any(cmd in SAFE_HELM_COMMANDS for cmd in expected_commands):
                raise ValueError(
                    f"Helm command structure '{base_command}' is not allowed"
                )
    else:
        # For other commands, check if the base command is allowed
        if command not in SAFE_HELM_COMMANDS:
            allowed_commands = ", ".join(
                sorted([cmd for cmd in SAFE_HELM_COMMANDS if " " not in cmd])
            )
            raise ValueError(
                f"Helm command '{command}' is not in the allowlist. "
                f"Allowed commands: {allowed_commands}"
            )

    # Check for blocked operations first (higher priority error message)
    full_command_check = " ".join(
        [command] + (options[:2] if len(options) >= 2 else options)
    )
    for blocked_op in BLOCKED_HELM_OPERATIONS:
        if blocked_op in full_command_check:
            raise ValueError(
                f"Helm command contains blocked operation '{blocked_op}': {full_command_check}"
            )
