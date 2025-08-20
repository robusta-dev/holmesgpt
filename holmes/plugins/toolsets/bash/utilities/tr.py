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



def stringify_tr_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:

    
    parts = ["tr"]
    parts.extend(command.options)
    
    return " ".join(escape_shell_args(parts))