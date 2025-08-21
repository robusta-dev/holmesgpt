import argparse
import re
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args

# Pattern to detect dangerous constructs that could bypass shlex escaping
# Specifically prevents:
# - Environment variable access: $VAR, ${VAR}, $(command)
# - Command substitution: `command`, $(command)
# - Process substitution: <(command), >(command)
# But allows: $ at end of line (regex anchor), $ inside character classes [...]
UNSAFE_GREP_PATTERN = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*|\$\{|\$\(|`|<\(|>\(")


def validate_grep_keyword(value: str) -> str:
    """Validate the grep keyword parameter."""

    if not value:
        raise argparse.ArgumentTypeError("Grep keyword cannot be empty")

    if UNSAFE_GREP_PATTERN.search(value):
        raise argparse.ArgumentTypeError(
            f"Grep keyword contains unsafe characters (variable expansion or command substitution): {value}"
        )

    return value


class GrepCommand(BashCommand):
    def __init__(self):
        super().__init__("grep")

    def add_parser(self, parent_parser: Any):
        parser = parent_parser.add_parser(
            "grep",
            help="Search text patterns in files or input",
            exit_on_error=False,
        )
        parser.add_argument(
            "keyword",
            type=lambda x: validate_grep_keyword(x),
            help="The pattern to search for",
        )
        parser.add_argument(
            "-i", "--ignore-case", action="store_true", help="Ignore case distinctions"
        )
        return parser

    def validate_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> None:
        # Validation is already done in the argument parser via validate_grep_keyword
        pass

    def stringify_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> str:
        """Stringify grep command."""
        parts = ["grep"]

        if command.ignore_case:
            parts.append("-i")

        parts.append(command.keyword)
        return " ".join(escape_shell_args(parts))


# Keep old functions for backward compatibility temporarily
def create_grep_parser(main_parser: Any):
    grep_command = GrepCommand()
    return grep_command.add_parser(main_parser)


def stringify_grep_command(cmd: Any) -> str:
    grep_command = GrepCommand()
    return grep_command.stringify_command(cmd, "", None)
