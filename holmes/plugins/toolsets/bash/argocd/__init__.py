import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.argocd.constants import (
    SAFE_ARGOCD_COMMANDS,
    SAFE_ARGOCD_OUTPUT_FORMATS,
    SAFE_ARGOCD_GLOBAL_FLAGS,
    SAFE_ARGOCD_COMMAND_FLAGS,
    BLOCKED_ARGOCD_OPERATIONS,
    SAFE_ARGOCD_APP_NAME_PATTERN,
    SAFE_ARGOCD_PROJECT_NAME_PATTERN,
    SAFE_ARGOCD_CLUSTER_NAME_PATTERN,
    SAFE_ARGOCD_NAMESPACE_PATTERN,
    SAFE_ARGOCD_REPO_URL_PATTERN,
    ARGOCD_LOG_LEVELS,
    ARGOCD_LOG_FORMATS,
)


def create_argocd_parser(parent_parser: Any):
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
    remaining_options = []

    # Find where the actual flags start
    for i, option in enumerate(options):
        if option.startswith("-"):
            remaining_options = options[i:]
            break
        operation_parts.append(option)
    else:
        # No flags found, all are operation parts
        operation_parts = options
        remaining_options = []

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


def validate_argocd_options(options: list[str]) -> list[str]:
    """Validate Argo CD CLI options to ensure they are safe."""
    validated_options = []
    i = 0

    while i < len(options):
        option = options[i]

        # Skip non-flag arguments (these are handled as command/operation parts)
        if not option.startswith("-"):
            # Resource names and parameters - shlex will handle proper escaping
            validated_options.append(option)
            i += 1
            continue

        # Handle flags that take values
        if option in {
            "--output",
            "-o",
            "--app-namespace",
            "-N",
            "--namespace",
            "--selector",
            "-l",
            "--project",
            "-p",
            "--cluster",
            "-c",
            "--repo",
            "-r",
            "--tail",
            "--filter",
            "--container",
            "--group",
            "--kind",
            "--name",
            "--since",
            "--since-time",
            "--timeout",
            "--revision",
            "--server",
            "--loglevel",
            "--logformat",
            "--config",
            "--port",
            "--address",
        }:
            if option in {"--output", "-o"}:
                # Validate output format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                output_format = options[i + 1]
                if output_format not in SAFE_ARGOCD_OUTPUT_FORMATS:
                    allowed_formats = ", ".join(sorted(SAFE_ARGOCD_OUTPUT_FORMATS))
                    raise ValueError(
                        f"Output format '{output_format}' is not allowed. "
                        f"Allowed formats: {allowed_formats}"
                    )
                validated_options.extend([option, output_format])
                i += 2
                continue

            elif option in {"--app-namespace", "-N", "--namespace"}:
                # Validate namespace format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                namespace = options[i + 1]
                if not SAFE_ARGOCD_NAMESPACE_PATTERN.match(namespace):
                    raise ValueError(f"Invalid namespace format: {namespace}")
                validated_options.extend([option, namespace])
                i += 2
                continue

            elif option in {"--project", "-p"}:
                # Validate project name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                project = options[i + 1]
                if not SAFE_ARGOCD_PROJECT_NAME_PATTERN.match(project):
                    raise ValueError(f"Invalid project name format: {project}")
                validated_options.extend([option, project])
                i += 2
                continue

            elif option in {"--cluster", "-c"}:
                # Validate cluster name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                cluster = options[i + 1]
                if not SAFE_ARGOCD_CLUSTER_NAME_PATTERN.match(cluster):
                    raise ValueError(f"Invalid cluster name format: {cluster}")
                validated_options.extend([option, cluster])
                i += 2
                continue

            elif option in {"--repo", "-r"}:
                # Validate repo URL format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                repo = options[i + 1]
                if repo.startswith("http") and not SAFE_ARGOCD_REPO_URL_PATTERN.match(
                    repo
                ):
                    raise ValueError(f"Invalid repository URL format: {repo}")
                validated_options.extend([option, repo])
                i += 2
                continue

            elif option == "--loglevel":
                # Validate log level
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                loglevel = options[i + 1]
                if loglevel not in ARGOCD_LOG_LEVELS:
                    allowed_levels = ", ".join(sorted(ARGOCD_LOG_LEVELS))
                    raise ValueError(
                        f"Invalid log level '{loglevel}'. Allowed levels: {allowed_levels}"
                    )
                validated_options.extend([option, loglevel])
                i += 2
                continue

            elif option == "--logformat":
                # Validate log format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                logformat = options[i + 1]
                if logformat not in ARGOCD_LOG_FORMATS:
                    allowed_formats = ", ".join(sorted(ARGOCD_LOG_FORMATS))
                    raise ValueError(
                        f"Invalid log format '{logformat}'. Allowed formats: {allowed_formats}"
                    )
                validated_options.extend([option, logformat])
                i += 2
                continue

            elif option == "--selector" or option == "-l":
                # Label selectors are safe when properly quoted by shlex
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                selector = options[i + 1]
                validated_options.extend([option, selector])
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
        elif option in SAFE_ARGOCD_GLOBAL_FLAGS or option in SAFE_ARGOCD_COMMAND_FLAGS:
            validated_options.append(option)
            i += 1
            continue

        else:
            # Unknown option
            raise ValueError(f"Unknown or unsafe Argo CD CLI option: {option}")

    return validated_options


def validate_argocd_command(cmd: Any) -> None:
    """
    Validate Argo CD command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    # Validate command and operation
    if hasattr(cmd, "options") and cmd.options:
        validate_argocd_command_and_operation(cmd.command, cmd.options)

        # Validate options
        validate_argocd_options(cmd.options)


def stringify_argocd_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed Argo CD command back to safe command string."""
    if command.cmd != "argocd":
        raise ValueError(f"Expected Argo CD command, got {command.cmd}")

    # Validate the command
    validate_argocd_command(command)

    # Build command parts
    parts = ["argocd", command.command]

    # Add validated options (which include subcommands and flags)
    if hasattr(command, "options") and command.options:
        validated_options = validate_argocd_options(command.options)
        parts.extend(validated_options)

    return " ".join(escape_shell_args(parts))
