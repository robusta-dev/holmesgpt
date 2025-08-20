import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_uniq_parser(parent_parser: Any):
    """Create uniq CLI parser with safe command validation."""
    uniq_parser = parent_parser.add_parser(
        "uniq", help="Remove or count duplicate lines", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    uniq_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Uniq options and parameters"
    )


def validate_uniq_options(options: list[str]) -> list[str]:
    """Validate uniq CLI options - no restrictions, just prevent file access."""
    # No file arguments allowed - uniq can only process piped input
    for option in options:
        if not option.startswith('-') and '=' not in option:
            raise ValueError("File arguments are not allowed - uniq can only process piped input")
    
    return options


def validate_uniq_command(cmd: Any) -> None:
    """Validate uniq command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_uniq_options(cmd.options)


def stringify_uniq_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed uniq command back to safe command string."""
    if command.cmd != "uniq":
        raise ValueError(f"Expected uniq command, got {command.cmd}")
    
    # Validate the command
    validate_uniq_command(command)
    
    # Build command parts
    parts = ["uniq"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_uniq_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))