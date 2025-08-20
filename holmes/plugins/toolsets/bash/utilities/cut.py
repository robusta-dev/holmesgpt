import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_cut_parser(parent_parser: Any):
    """Create cut CLI parser with safe command validation."""
    cut_parser = parent_parser.add_parser(
        "cut", help="Extract columns from text", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    cut_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Cut options and parameters"
    )


def validate_cut_options(options: list[str]) -> list[str]:
    """Validate cut CLI options - no restrictions, just prevent file access."""
    # No file arguments allowed - cut can only process piped input
    for option in options:
        if not option.startswith('-') and '=' not in option:
            raise ValueError("File arguments are not allowed - cut can only process piped input")
    
    return options


def validate_cut_command(cmd: Any) -> None:
    """Validate cut command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_cut_options(cmd.options)


def stringify_cut_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed cut command back to safe command string."""
    if command.cmd != "cut":
        raise ValueError(f"Expected cut command, got {command.cmd}")
    
    # Validate the command
    validate_cut_command(command)
    
    # Build command parts
    parts = ["cut"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_cut_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))