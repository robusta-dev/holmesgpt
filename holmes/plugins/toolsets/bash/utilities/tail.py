import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_tail_parser(parent_parser: Any):
    """Create tail CLI parser with safe command validation."""
    tail_parser = parent_parser.add_parser(
        "tail", help="Display last lines of input", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    tail_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Tail options and parameters"
    )


def validate_tail_options(options: list[str]) -> list[str]:
    """Validate tail CLI options - no restrictions, just prevent file access."""
    # No file arguments allowed - tail can only process piped input
    # Skip option values that follow flags
    i = 0
    while i < len(options):
        option = options[i]
        
        # Skip option-value pairs
        if option in {"-c", "--bytes", "-n", "--lines", "-s", "--sleep-interval", "--pid"} and i + 1 < len(options):
            i += 2  # Skip option and value
            continue
        elif option.startswith("-") and i + 1 < len(options) and not options[i + 1].startswith("-"):
            i += 2  # Skip other option-value pairs
            continue
        elif not option.startswith('-') and '=' not in option:
            # This is a standalone argument that could be a file
            raise ValueError("File arguments are not allowed - tail can only process piped input")
        
        i += 1
    
    return options


def validate_tail_command(cmd: Any) -> None:
    """Validate tail command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_tail_options(cmd.options)


def stringify_tail_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed tail command back to safe command string."""
    if command.cmd != "tail":
        raise ValueError(f"Expected tail command, got {command.cmd}")
    
    # Validate the command
    validate_tail_command(command)
    
    # Build command parts
    parts = ["tail"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_tail_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))