import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_head_parser(parent_parser: Any):
    """Create head CLI parser with safe command validation."""
    head_parser = parent_parser.add_parser(
        "head", help="Display first lines of input", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    head_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Head options and parameters"
    )


def validate_head_options(options: list[str]) -> list[str]:
    """Validate head CLI options - no restrictions, just prevent file access."""
    # No file arguments allowed - head can only process piped input
    # Skip option values that follow flags
    i = 0
    while i < len(options):
        option = options[i]
        
        # Skip option-value pairs
        if option in {"-c", "--bytes", "-n", "--lines"} and i + 1 < len(options):
            i += 2  # Skip option and value
            continue
        elif option.startswith("-") and i + 1 < len(options) and not options[i + 1].startswith("-"):
            i += 2  # Skip other option-value pairs
            continue
        elif not option.startswith('-') and '=' not in option:
            # This is a standalone argument that could be a file
            raise ValueError("File arguments are not allowed - head can only process piped input")
        
        i += 1
    
    return options


def validate_head_command(cmd: Any) -> None:
    """Validate head command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_head_options(cmd.options)


def stringify_head_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed head command back to safe command string."""
    if command.cmd != "head":
        raise ValueError(f"Expected head command, got {command.cmd}")
    
    # Validate the command
    validate_head_command(command)
    
    # Build command parts
    parts = ["head"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_head_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))