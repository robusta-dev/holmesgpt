import argparse
from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_kubectl_events_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "events",
        help="List events",
        exit_on_error=False,  # Important for library use
    )

    parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,  # Captures all remaining arguments
        default=[],  # Default to an empty list
    )


def stringify_events_command(cmd: Any) -> str:
    parts = ["kubectl", "events"]

    parts += cmd.options

    return " ".join(escape_shell_args(parts))