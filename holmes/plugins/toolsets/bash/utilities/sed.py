import argparse
import re
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args

# Blocked sed commands for security
BLOCKED_SED_COMMANDS = {
    "w",  # Write to file
    "W",  # Write first line of pattern space to file  
    "r",  # Read file
    "R",  # Read one line from file
    "e",  # Execute command
    "v",  # Version (in some contexts)
    "z",  # Clear pattern space (can be misused)
    "q",  # Quit (can be misused to skip processing)
    "Q",  # Quit immediately
}

# Pattern to detect dangerous sed commands
DANGEROUS_SED_PATTERN = re.compile(
    r'(?:^|;|\n)\s*(?:[0-9,]*\s*)?[wWrRezvqQ](?:\s|$|/)',
    re.MULTILINE
)


def create_sed_parser(parent_parser: Any):
    """Create sed CLI parser with safe command validation."""
    sed_parser = parent_parser.add_parser(
        "sed", help="Stream editor for filtering and transforming text", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    sed_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Sed script and options"
    )


def validate_sed_script(script: str) -> None:
    """Validate a sed script for safety."""
    # Check for blocked commands - only check for actual command patterns
    if DANGEROUS_SED_PATTERN.search(script):
        raise ValueError("sed script contains blocked commands (w, r, e, q, etc.)")
    
    # Check for execute command specifically (more targeted)
    if re.search(r'(?:^|;|\n)\s*(?:[0-9,]*\s*)?e\b', script, re.MULTILINE):
        raise ValueError("sed script contains execute commands")
    
    # Check for file operations (simpler pattern to catch write/read commands)
    if re.search(r'[wWrR]\s+\S', script):
        raise ValueError("sed script contains file operations")


def validate_sed_options(options: list[str]) -> list[str]:
    """Validate sed CLI options - block file operations and in-place editing."""
    i = 0
    script_found = False
    
    while i < len(options):
        option = options[i]
        
        # Block file reading and in-place editing for security
        if option in {"-f", "--file", "-i", "--in-place"}:
            raise ValueError(f"Option {option} is not allowed for security reasons")
        
        # Handle option-value pairs
        elif option in {"-e", "--expression"} and i + 1 < len(options):
            script = options[i + 1]
            validate_sed_script(script)
            script_found = True
            i += 2
            continue
        elif option.startswith("--") and i + 1 < len(options) and not options[i + 1].startswith("-"):
            i += 2  # Skip option and value
            continue
        
        # Handle sed script (non-flag argument)  
        elif not option.startswith('-'):
            if not script_found:
                validate_sed_script(option)
                script_found = True
            i += 1
            continue
        
        i += 1
    
    return options


def validate_sed_command(cmd: Any) -> None:
    """Validate sed command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_sed_options(cmd.options)


def stringify_sed_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed sed command back to safe command string."""
    if command.cmd != "sed":
        raise ValueError(f"Expected sed command, got {command.cmd}")
    
    # Validate the command
    validate_sed_command(command)
    
    # Build command parts
    parts = ["sed"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_sed_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))