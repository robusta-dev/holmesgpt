import argparse
from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


def create_kubectl_logs_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "logs",
        exit_on_error=False,
    )
    parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,  # Captures all remaining arguments
        default=[],  # Default to an empty list
    )


def stringify_logs_command(cmd: Any) -> str:
    parts = ["kubectl", "logs"]

    parts += cmd.options

    return " ".join(escape_shell_args(parts))
