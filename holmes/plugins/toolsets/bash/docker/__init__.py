import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.docker.constants import (
    SAFE_DOCKER_COMMANDS,
    SAFE_DOCKER_OUTPUT_FORMATS,
    SAFE_DOCKER_GLOBAL_FLAGS,
    SAFE_DOCKER_COMMAND_FLAGS,
    BLOCKED_DOCKER_OPERATIONS,
    SAFE_DOCKER_CONTAINER_NAME_PATTERN,
    SAFE_DOCKER_IMAGE_NAME_PATTERN,
    SAFE_DOCKER_TAG_PATTERN,
    SAFE_DOCKER_NETWORK_NAME_PATTERN,
    SAFE_DOCKER_VOLUME_NAME_PATTERN,
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
    remaining_options = []
    
    # Find where the actual flags start or where we should stop building the command structure
    for i, option in enumerate(options):
        if option.startswith('-'):
            remaining_options = options[i:]
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
                remaining_options = options[i:]
                break
            # If we're building towards a two-word command (like "container inspect")
            elif len(command_parts) < 3:  # Allow up to two-word commands
                command_parts.append(option)
            else:
                # Treat as resource name/flag
                remaining_options = options[i:]
                break
    else:
        # No flags found, check if we have a valid command
        if " ".join(command_parts) not in SAFE_DOCKER_COMMANDS:
            # Last parts might be resource names, try without them
            for split_point in range(len(command_parts) - 1, 0, -1):
                test_command = " ".join(command_parts[:split_point])
                if test_command in SAFE_DOCKER_COMMANDS:
                    command_parts = command_parts[:split_point]
                    remaining_options = command_parts[split_point:] + remaining_options
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


def validate_docker_options(options: list[str]) -> list[str]:
    """Validate Docker CLI options to ensure they are safe."""
    validated_options = []
    i = 0
    
    while i < len(options):
        option = options[i]
        
        # Skip non-flag arguments (these are handled as command/operation parts)
        if not option.startswith('-'):
            # Resource names and parameters - shlex will handle proper escaping
            validated_options.append(option)
            i += 1
            continue
        
        # Handle flags that take values
        if option in {"--format", "-f", "--filter", "--since", "--until", "--tail",
                     "--output", "-o", "--name", "--id", "--container", "--network",
                     "--volume", "--repository", "--tag", "--digest", "--reference",
                     "--type", "--label", "--limit", "--time", "--timeout", "--lines"}:
            
            if option in {"--format", "-f"}:
                # Validate output format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                output_format = options[i + 1]
                if output_format not in SAFE_DOCKER_OUTPUT_FORMATS:
                    allowed_formats = ", ".join(sorted(SAFE_DOCKER_OUTPUT_FORMATS))
                    raise ValueError(
                        f"Output format '{output_format}' is not allowed. "
                        f"Allowed formats: {allowed_formats}"
                    )
                validated_options.extend([option, output_format])
                i += 2
                continue
                
            elif option in {"--name"}:
                # Validate container/resource name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                name = options[i + 1]
                if not SAFE_DOCKER_CONTAINER_NAME_PATTERN.match(name):
                    raise ValueError(f"Invalid Docker resource name format: {name}")
                validated_options.extend([option, name])
                i += 2
                continue
                
            elif option in {"--repository"}:
                # Validate image repository format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                repository = options[i + 1]
                if not SAFE_DOCKER_IMAGE_NAME_PATTERN.match(repository):
                    raise ValueError(f"Invalid Docker repository format: {repository}")
                validated_options.extend([option, repository])
                i += 2
                continue
                
            elif option in {"--tag"}:
                # Validate tag format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                tag = options[i + 1]
                if not SAFE_DOCKER_TAG_PATTERN.match(tag):
                    raise ValueError(f"Invalid Docker tag format: {tag}")
                validated_options.extend([option, tag])
                i += 2
                continue
                
            elif option in {"--network"}:
                # Validate network name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                network = options[i + 1]
                if not SAFE_DOCKER_NETWORK_NAME_PATTERN.match(network):
                    raise ValueError(f"Invalid Docker network name format: {network}")
                validated_options.extend([option, network])
                i += 2
                continue
                
            elif option in {"--volume"}:
                # Validate volume name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                volume = options[i + 1]
                if not SAFE_DOCKER_VOLUME_NAME_PATTERN.match(volume):
                    raise ValueError(f"Invalid Docker volume name format: {volume}")
                validated_options.extend([option, volume])
                i += 2
                continue
                
            else:
                # For other options with values, add both - shlex will handle proper escaping
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                value = options[i + 1]
                validated_options.extend([option, value])
                i += 2
                continue
        
        # Handle boolean flags
        elif option in SAFE_DOCKER_GLOBAL_FLAGS or option in SAFE_DOCKER_COMMAND_FLAGS:
            validated_options.append(option)
            i += 1
            continue
            
        else:
            # Unknown option
            raise ValueError(f"Unknown or unsafe Docker CLI option: {option}")
    
    return validated_options


def validate_docker_command(cmd: Any) -> None:
    """
    Validate Docker command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    # Validate command and operation
    if hasattr(cmd, 'options') and cmd.options:
        validate_docker_command_and_operation(cmd.command, cmd.options)
        
        # Validate options
        validate_docker_options(cmd.options)


def stringify_docker_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed Docker command back to safe command string."""
    if command.cmd != "docker":
        raise ValueError(f"Expected Docker command, got {command.cmd}")
    
    # Validate the command
    validate_docker_command(command)
    
    # Build command parts
    parts = ["docker", command.command]
    
    # Add validated options (which include subcommands and flags)
    if hasattr(command, 'options') and command.options:
        validated_options = validate_docker_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))