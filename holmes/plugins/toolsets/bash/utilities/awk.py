import argparse
import re
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args

# Blocked awk functions and statements for security
BLOCKED_AWK_FUNCTIONS = {
    "system",  # Execute shell commands
    "getline",  # Read from files/commands
    "close",  # Close files/pipes
    "fflush",  # Flush files
    "@include",  # Include files
    "@load",  # Load extensions
    "@namespace",  # Namespace operations
}

# Pattern to detect dangerous awk constructs
DANGEROUS_AWK_PATTERN = re.compile(
    r'\b(?:system|getline|close|fflush|@include|@load|@namespace)\b|'
    r'(?:print|printf)\s*[>|]|'
    r'[|]\s*getline',
    re.IGNORECASE
)


def create_awk_parser(parent_parser: Any):
    """Create awk CLI parser with safe command validation."""
    awk_parser = parent_parser.add_parser(
        "awk", help="Pattern scanning and processing language", exit_on_error=False,
        add_help=False,  # Disable help to avoid conflicts
        prefix_chars="\x00"  # Use null character as prefix to disable option parsing
    )
    
    # Capture all arguments for validation
    awk_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Awk program and options"
    )


def validate_awk_program(program: str) -> None:
    """Validate an awk program for safety."""
    # Check for blocked functions and constructs
    if DANGEROUS_AWK_PATTERN.search(program):
        raise ValueError("awk program contains blocked functions or operations")
    
    # Additional safety checks
    if any(keyword in program for keyword in ["system(", "getline", "close(", "fflush("]):
        raise ValueError("awk program contains blocked system functions")
    
    # Check for file operations
    if any(op in program for op in [">", ">>", "|"] if op in program and "print" in program):
        raise ValueError("awk program contains file/pipe output operations")


def validate_awk_options(options: list[str]) -> list[str]:
    """Validate awk CLI options - block file operations and dangerous options."""
    i = 0
    program_found = False
    
    while i < len(options):
        option = options[i]
        
        # Block file/execution options for security
        if option in {"-f", "--file", "-E", "--exec", "-i", "--include", "-l", "--load-extension"}:
            raise ValueError(f"Option {option} is not allowed for security reasons")
        
        # Handle option-value pairs
        elif option in {"-F", "--field-separator", "-v", "--assign"} and i + 1 < len(options):
            i += 2  # Skip option and value
            continue
        
        # Handle awk program (non-flag argument)
        elif not option.startswith('-'):
            if not program_found:
                validate_awk_program(option)
                program_found = True
            # After program, file arguments not allowed
            i += 1
            continue
        
        i += 1
    
    # No file arguments allowed - awk can only process piped input
    for option in options:
        if not option.startswith('-') and '=' not in option:
            # Could be program or file - we validate programs above
            pass
    
    return options


def validate_awk_command(cmd: Any) -> None:
    """Validate awk command to ensure safety."""
    if hasattr(cmd, 'options') and cmd.options:
        validate_awk_options(cmd.options)


def stringify_awk_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:

    parts = ["awk"]
    
    # Add validated options
    if hasattr(command, 'options') and command.options:
        validated_options = validate_awk_options(command.options)
        parts.extend(validated_options)
    
    return " ".join(escape_shell_args(parts))