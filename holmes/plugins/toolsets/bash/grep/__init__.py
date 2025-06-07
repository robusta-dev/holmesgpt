import argparse
import re
from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args

MAX_GREP_SIZE = 100
SAFE_GREP_PATTERN = re.compile(r"^[a-zA-Z0-9\-_. :*()]+$")


def create_grep_parser(main_parser: Any):
    parser = main_parser.add_parser(
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


def validate_grep_keyword(value: str) -> str:
    """Validate the grep keyword parameter."""

    if not value:
        raise argparse.ArgumentTypeError("Grep keyword cannot be empty")

    if not SAFE_GREP_PATTERN.match(value):
        raise argparse.ArgumentTypeError(f"Unsafe grep keyword: {value}")

    if len(value) > MAX_GREP_SIZE:
        raise argparse.ArgumentTypeError(
            f"Grep keyword too long. Max allowed size is {MAX_GREP_SIZE} but received {len(value)}"
        )

    return value


def stringify_grep_command(cmd: Any) -> str:
    """Stringify grep command."""
    parts = ["grep"]

    if cmd.ignore_case:
        parts.append("-i")

    parts.append(cmd.keyword)
    return " ".join(escape_shell_args(parts))
