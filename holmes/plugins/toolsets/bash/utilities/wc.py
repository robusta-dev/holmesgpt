import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_wc_parser(parent_parser: Any):
    """Create wc CLI parser with safe command validation."""
    wc_parser = parent_parser.add_parser(
        "wc", help="Count words, lines, bytes, and characters", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    wc_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Wc options and parameters"
    )


def validate_wc_options(options: list[str]) -> list[str]:
    """Validate wc CLI options - block file reading options."""
    for option in options:
        # Block file reading options
        if option == "--files0-from":
            raise ValueError("Option --files0-from is not allowed for security reasons")
        
        # No file arguments allowed - wc can only process piped input
        if not option.startswith('-') and '=' not in option:
            raise ValueError("File arguments are not allowed - wc can only process piped input")
    
    return options


def validate_wc_command(cmd: Any) -> None:
    """Validate wc command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_wc_options(cmd.options)


def stringify_wc_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed wc command back to safe command string."""
    if command.cmd != "wc":
        raise ValueError(f"Expected wc command, got {command.cmd}")
    
    # Validate the command
    validate_wc_command(command)
    
    # Build command parts
    parts = ["wc"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_wc_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))