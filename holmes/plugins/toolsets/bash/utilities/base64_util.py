import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_base64_parser(parent_parser: Any):
    """Create base64 CLI parser with safe command validation."""
    base64_parser = parent_parser.add_parser(
        "base64", help="Base64 encode/decode", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    base64_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Base64 options and parameters"
    )


def validate_base64_options(options: list[str]) -> list[str]:
    """Validate base64 CLI options - no restrictions, just prevent file access."""
    # No file arguments allowed - base64 can only process piped input
    for option in options:
        if not option.startswith('-') and '=' not in option:
            raise ValueError("File arguments are not allowed - base64 can only process piped input")
    
    return options


def validate_base64_command(cmd: Any) -> None:
    """Validate base64 command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_base64_options(cmd.options)


def stringify_base64_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed base64 command back to safe command string."""
    if command.cmd != "base64":
        raise ValueError(f"Expected base64 command, got {command.cmd}")
    
    # Validate the command
    validate_base64_command(command)
    
    # Build command parts
    parts = ["base64"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_base64_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))