import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.helm.constants import (
    SAFE_HELM_COMMANDS,
    SAFE_HELM_GET_SUBCOMMANDS,
    SAFE_HELM_SHOW_SUBCOMMANDS,
    SAFE_HELM_OUTPUT_FORMATS,
    SAFE_HELM_GLOBAL_FLAGS,
    SAFE_HELM_COMMAND_FLAGS,
    BLOCKED_HELM_OPERATIONS,
    SAFE_HELM_RELEASE_NAME_PATTERN,
    SAFE_HELM_CHART_NAME_PATTERN,
    SAFE_HELM_NAMESPACE_PATTERN,
    SAFE_HELM_REPO_NAME_PATTERN,
    SAFE_HELM_REPO_URL_PATTERN,
)


def create_helm_parser(parent_parser: Any):
    """Create Helm CLI parser with safe command validation."""
    helm_parser = parent_parser.add_parser(
        "helm", help="Helm Package Manager for Kubernetes", exit_on_error=False
    )
    
    # Add command subparser
    helm_parser.add_argument(
        "command",
        help="Helm command (e.g., list, get, status, show)"
    )
    
    # Capture remaining arguments
    helm_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Helm CLI subcommands, operations, and options"
    )


def validate_helm_command_and_operation(command: str, options: list[str]) -> None:
    """Validate that the Helm command and operation combination is safe."""
    # Special handling for commands with subcommands (get, show, repo, etc.)
    if command in ["get", "show", "repo", "dependency"]:
        if not options:
            # Command without subcommand is allowed (shows help)
            return
            
        # Extract subcommand for validation
        subcommand_parts = []
        remaining_options = []
        
        for i, option in enumerate(options):
            if option.startswith('-'):
                remaining_options = options[i:]
                break
            subcommand_parts.append(option)
        else:
            subcommand_parts = options
            remaining_options = []
            
        if subcommand_parts:
            # Separate command structure from resource names
            command_structure = [command]
            resource_names = []
            
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
                resource_names = subcommand_parts[1:]  # Everything after subcommand is resource names
                
            elif command == "show" and len(subcommand_parts) >= 1:
                subcommand = subcommand_parts[0]
                if subcommand not in SAFE_HELM_SHOW_SUBCOMMANDS:
                    allowed_subcmds = ", ".join(sorted(SAFE_HELM_SHOW_SUBCOMMANDS))
                    raise ValueError(
                        f"Helm show subcommand '{subcommand}' is not allowed. "
                        f"Allowed subcommands: {allowed_subcmds}"
                    )
                command_structure.append(subcommand)
                resource_names = subcommand_parts[1:]  # Everything after subcommand is resource names
                
            elif command == "repo" and subcommand_parts[0] == "list":
                command_structure.extend(["list"])
                resource_names = subcommand_parts[1:]
                
            elif command == "dependency" and subcommand_parts[0] == "list":
                command_structure.extend(["list"])
                resource_names = subcommand_parts[1:]
                
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
            expected_commands = [command, f"{command} {command_structure[1]}"] if len(command_structure) > 1 else [command]
            
            # Check if the base command or expected pattern is in allowlist
            if not any(cmd in SAFE_HELM_COMMANDS for cmd in expected_commands):
                raise ValueError(
                    f"Helm command structure '{base_command}' is not allowed"
                )
    else:
        # For other commands, check if the base command is allowed
        if command not in SAFE_HELM_COMMANDS:
            allowed_commands = ", ".join(sorted([cmd for cmd in SAFE_HELM_COMMANDS if " " not in cmd]))
            raise ValueError(
                f"Helm command '{command}' is not in the allowlist. "
                f"Allowed commands: {allowed_commands}"
            )
    
    # Check for blocked operations first (higher priority error message)
    full_command_check = " ".join([command] + (options[:2] if len(options) >= 2 else options))
    for blocked_op in BLOCKED_HELM_OPERATIONS:
        if blocked_op in full_command_check:
            raise ValueError(
                f"Helm command contains blocked operation '{blocked_op}': {full_command_check}"
            )


def validate_helm_options(options: list[str]) -> list[str]:
    """Validate Helm CLI options to ensure they are safe."""
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
        if option in {"--output", "-o", "--namespace", "-n", "--revision", "--kube-context",
                     "--kubeconfig", "--kube-config", "--values", "-f", "--set", "--set-file",
                     "--set-string", "--version", "--filter", "--selector", "-l", "--max",
                     "--offset", "--template", "--name-template", "--output-dir", "--show-only",
                     "--kube-version", "--release-name", "--url", "--keyring", "--time-format"}:
            
            if option in {"--output", "-o"}:
                # Validate output format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                output_format = options[i + 1]
                if output_format not in SAFE_HELM_OUTPUT_FORMATS:
                    allowed_formats = ", ".join(sorted(SAFE_HELM_OUTPUT_FORMATS))
                    raise ValueError(
                        f"Output format '{output_format}' is not allowed. "
                        f"Allowed formats: {allowed_formats}"
                    )
                validated_options.extend([option, output_format])
                i += 2
                continue
                
            elif option in {"--namespace", "-n"}:
                # Validate namespace format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                namespace = options[i + 1]
                if not SAFE_HELM_NAMESPACE_PATTERN.match(namespace):
                    raise ValueError(f"Invalid Helm namespace format: {namespace}")
                validated_options.extend([option, namespace])
                i += 2
                continue
                
            elif option in {"--release-name"}:
                # Validate release name format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                release_name = options[i + 1]
                if not SAFE_HELM_RELEASE_NAME_PATTERN.match(release_name):
                    raise ValueError(f"Invalid Helm release name format: {release_name}")
                validated_options.extend([option, release_name])
                i += 2
                continue
                
            elif option == "--url":
                # Validate repository URL format for repo commands
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                url = options[i + 1]
                if not SAFE_HELM_REPO_URL_PATTERN.match(url):
                    raise ValueError(f"Invalid Helm repository URL format: {url}")
                validated_options.extend([option, url])
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
        elif option in SAFE_HELM_GLOBAL_FLAGS or option in SAFE_HELM_COMMAND_FLAGS:
            validated_options.append(option)
            i += 1
            continue
            
        else:
            # Unknown option
            raise ValueError(f"Unknown or unsafe Helm CLI option: {option}")
    
    return validated_options


def validate_helm_command(cmd: Any) -> None:
    """
    Validate Helm command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    # Validate command and operation
    if hasattr(cmd, 'options') and cmd.options:
        validate_helm_command_and_operation(cmd.command, cmd.options)
        
        # Validate options
        validate_helm_options(cmd.options)


def stringify_helm_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed Helm command back to safe command string."""
    if command.cmd != "helm":
        raise ValueError(f"Expected Helm command, got {command.cmd}")
    
    # Validate the command
    validate_helm_command(command)
    
    # Build command parts
    parts = ["helm", command.command]
    
    # Add validated options (which include subcommands and flags)
    if hasattr(command, 'options') and command.options:
        validated_options = validate_helm_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))