import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.docker.constants import (
    SAFE_DOCKER_COMMANDS,
    BLOCKED_DOCKER_OPERATIONS,
)


def create_docker_parser(parent_parser: Any):
    """Create Docker CLI parser with safe command validation."""
    docker_parser = parent_parser.add_parser(
        "docker", help="Docker Command Line Interface", exit_on_error=False
    )
    
    # Add command subparser
    docker_parser.add_argument(
        "command",
        help="Docker command (e.g., ps, images, inspect)"
    )
    
    # Capture remaining arguments
    docker_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Docker CLI subcommands, operations, and options"
    )


def validate_docker_command_and_operation(command: str, options: list[str]) -> None:
    """Validate that the Docker command and operation combination is safe."""
    # Extract command structure from command + options, stopping at flags or resource names
    command_parts = [command]
    
    # Find where the actual flags start or where we should stop building the command structure
    for i, option in enumerate(options):
        if option.startswith('-'):
            break
        else:
            # Check if this option could be a resource name or should be part of the command structure
            potential_command = " ".join(command_parts + [option])
            
            # If adding this option creates a valid command in our allowlist, include it
            if potential_command in SAFE_DOCKER_COMMANDS:
                command_parts.append(option)
            # If current command_parts already form a valid command, treat remaining as resource names
            elif " ".join(command_parts) in SAFE_DOCKER_COMMANDS:
                # Current command is valid, remaining options are resource names and flags
                break
            # If we're building towards a two-word command (like "container inspect")
            elif len(command_parts) < 3:  # Allow up to two-word commands
                command_parts.append(option)
            else:
                break
    else:
        # No flags found, check if we have a valid command
        if " ".join(command_parts) not in SAFE_DOCKER_COMMANDS:
            # Last parts might be resource names, try without them
            for split_point in range(len(command_parts) - 1, 0, -1):
                test_command = " ".join(command_parts[:split_point])
                if test_command in SAFE_DOCKER_COMMANDS:
                    command_parts = command_parts[:split_point]
                    break
    
    # Build final command string for validation
    base_command = " ".join(command_parts)
    
    # Check for blocked operations first (higher priority error message)
    for blocked_op in BLOCKED_DOCKER_OPERATIONS:
        if blocked_op in base_command:
            raise ValueError(
                f"Docker command contains blocked operation '{blocked_op}': {base_command}"
            )
    
    if base_command not in SAFE_DOCKER_COMMANDS:
        # Try to provide helpful error message
        matching_commands = [cmd for cmd in SAFE_DOCKER_COMMANDS if cmd.startswith(command)]
        if matching_commands:
            sample_commands = ", ".join(sorted(matching_commands)[:5])
            if len(matching_commands) > 5:
                sample_commands += f" (and {len(matching_commands) - 5} more)"
            raise ValueError(
                f"Docker command '{base_command}' is not in the allowlist. "
                f"Sample allowed commands starting with '{command}': {sample_commands}"
            )
        else:
            raise ValueError(
                f"Docker command '{command}' is not supported or command '{base_command}' is not allowed"
            )

def validate_docker_command(cmd: Any) -> None:
    """
    Validate Docker command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    if hasattr(cmd, 'options') and cmd.options:
        validate_docker_command_and_operation(cmd.command, cmd.options)
    


def stringify_docker_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed Docker command back to safe command string."""
    if command.cmd != "docker":
        raise ValueError(f"Expected Docker command, got {command.cmd}")
    
    validate_docker_command(command)
    
    parts = ["docker", command.command]
    
    if hasattr(command, 'options') and command.options:
        parts.extend(command.options)
    
    return " ".join(escape_shell_args(parts))