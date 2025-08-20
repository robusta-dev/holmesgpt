import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_sort_parser(parent_parser: Any):
    """Create sort CLI parser with safe command validation."""
    sort_parser = parent_parser.add_parser(
        "sort", help="Sort lines of text", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    sort_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Sort options and parameters"
    )


def validate_sort_options(options: list[str]) -> list[str]:
    """Validate sort CLI options - prevent file access and temp directory options."""
    for i, option in enumerate(options):
        # Block temporary directory options for security
        if option in {"-T", "--temporary-directory"}:
            raise ValueError(f"Option {option} is not allowed for security reasons")
        
        # No file arguments allowed - sort can only process piped input
        if not option.startswith('-') and '=' not in option:
            raise ValueError("File arguments are not allowed - sort can only process piped input")
    
    return options


def validate_sort_command(cmd: Any) -> None:
    """Validate sort command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_sort_options(cmd.options)


def stringify_sort_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed sort command back to safe command string."""
    if command.cmd != "sort":
        raise ValueError(f"Expected sort command, got {command.cmd}")
    
    # Validate the command
    validate_sort_command(command)
    
    # Build command parts
    parts = ["sort"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_sort_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))