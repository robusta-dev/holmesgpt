import argparse
from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_kubectl_events_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "events",
        help="List events",
        exit_on_error=False,  # Important for library use
        add_help=False,
        prefix_chars="\x00",  # Use null character as prefix to disable option parsing
    )

    parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,  # Now REMAINDER works because it comes after a positional
        default=[],
    )


def stringify_events_command(cmd: Any) -> str:
    parts = ["kubectl", "events"]

    parts += cmd.options

    return " ".join(escape_shell_args(parts))
