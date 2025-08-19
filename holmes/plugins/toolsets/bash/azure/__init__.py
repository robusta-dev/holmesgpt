import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.azure.constants import (
    SAFE_AZURE_COMMANDS,
    SAFE_AZURE_OUTPUT_FORMATS,
    SAFE_AZURE_GLOBAL_FLAGS,
    SAFE_AZURE_SERVICE_FLAGS,
    BLOCKED_AZURE_OPERATIONS,
    AZURE_LOCATIONS,
    SAFE_AZURE_RESOURCE_NAME_PATTERN,
    SAFE_AZURE_RESOURCE_GROUP_PATTERN,
    SAFE_AZURE_SUBSCRIPTION_PATTERN,
    SAFE_AZURE_LOCATION_PATTERN,
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


def validate_azure_options(options: list[str]) -> list[str]:
    """Validate Azure CLI options to ensure they are safe."""
    validated_options = []
    i = 0

    while i < len(options):
        option = options[i]

        # Skip non-flag arguments (these are handled as command parts)
        if not option.startswith("-"):
            validated_options.append(option)
            i += 1
            continue

        # Handle flags that take values
        if option in {
            "--output",
            "-o",
            "--subscription",
            "-s",
            "--resource-group",
            "-g",
            "--location",
            "-l",
            "--name",
            "-n",
            "--query",
            "--tag",
            "--sku",
            "--start-time",
            "--end-time",
            "--interval",
            "--aggregation",
            "--metrics",
            "--namespace",
            "--dimension",
            "--filter",
            "--orderby",
            "--top",
            "--max-items",
            "--skip-token",
        }:
            if option in {"--output", "-o"}:
                # Validate output format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                output_format = options[i + 1]
                if output_format not in SAFE_AZURE_OUTPUT_FORMATS:
                    allowed_formats = ", ".join(sorted(SAFE_AZURE_OUTPUT_FORMATS))
                    raise ValueError(
                        f"Output format '{output_format}' is not allowed. "
                        f"Allowed formats: {allowed_formats}"
                    )
                validated_options.extend([option, output_format])
                i += 2
                continue

            elif option in {"--location", "-l"}:
                # Validate location format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                location = options[i + 1]
                if (
                    not SAFE_AZURE_LOCATION_PATTERN.match(location)
                    or location not in AZURE_LOCATIONS
                ):
                    allowed_locations = (
                        ", ".join(sorted(list(AZURE_LOCATIONS)[:10])) + "..."
                    )
                    raise ValueError(
                        f"Invalid or unknown Azure location: {location}. "
                        f"Common locations: {allowed_locations}"
                    )
                validated_options.extend([option, location])
                i += 2
                continue

            elif option in {"--resource-group", "-g"}:
                # Validate resource group name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                rg_name = options[i + 1]
                if not SAFE_AZURE_RESOURCE_GROUP_PATTERN.match(rg_name):
                    raise ValueError(f"Invalid resource group name format: {rg_name}")
                validated_options.extend([option, rg_name])
                i += 2
                continue

            elif option in {"--subscription", "-s"}:
                # Validate subscription ID format (if it looks like a GUID)
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                subscription = options[i + 1]
                # Allow subscription names or validate GUID format
                if len(
                    subscription
                ) == 36 and not SAFE_AZURE_SUBSCRIPTION_PATTERN.match(subscription):
                    raise ValueError(f"Invalid subscription ID format: {subscription}")
                validated_options.extend([option, subscription])
                i += 2
                continue

            elif option in {"--name", "-n"}:
                # Validate resource name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                name = options[i + 1]
                if not SAFE_AZURE_RESOURCE_NAME_PATTERN.match(name):
                    raise ValueError(f"Invalid resource name format: {name}")
                validated_options.extend([option, name])
                i += 2
                continue

            elif option == "--query":
                # JMESPath queries are safe when properly quoted by shlex
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                query = options[i + 1]
                validated_options.extend([option, query])
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
        elif option in SAFE_AZURE_GLOBAL_FLAGS or option in SAFE_AZURE_SERVICE_FLAGS:
            validated_options.append(option)
            i += 1
            continue

        else:
            # Unknown option
            raise ValueError(f"Unknown or unsafe Azure CLI option: {option}")

    return validated_options


def validate_azure_command(cmd: Any) -> None:
    """
    Validate Azure command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    # Validate service and operation
    if hasattr(cmd, "options") and cmd.options:
        validate_azure_service_and_operation(cmd.service, cmd.options)

        # Validate options
        validate_azure_options(cmd.options)


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

    # Add validated options (which include subcommands and flags)
    if hasattr(command, "options") and command.options:
        validated_options = validate_azure_options(command.options)
        parts.extend(validated_options)

    return " ".join(escape_shell_args(parts))
