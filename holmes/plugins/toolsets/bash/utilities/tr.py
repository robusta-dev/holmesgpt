import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_tr_parser(parent_parser: Any):
    """Create tr CLI parser with safe command validation."""
    tr_parser = parent_parser.add_parser(
        "tr", help="Translate or delete characters", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    tr_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Tr options and character sets"
    )


def validate_tr_options(options: list[str]) -> list[str]:
    """Validate tr CLI options - no restrictions, just prevent file access."""
    # No file arguments allowed - tr can only process piped input
    for option in options:
        if not option.startswith('-') and '=' not in option and len(option) > 100:
            # Allow character sets but prevent extremely long arguments
            raise ValueError("Character sets too long - tr can only process piped input")
    
    return options


def validate_tr_command(cmd: Any) -> None:
    """Validate tr command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_tr_options(cmd.options)


def stringify_tr_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed tr command back to safe command string."""
    if command.cmd != "tr":
        raise ValueError(f"Expected tr command, got {command.cmd}")
    
    # Validate the command
    validate_tr_command(command)
    
    # Build command parts
    parts = ["tr"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_tr_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))