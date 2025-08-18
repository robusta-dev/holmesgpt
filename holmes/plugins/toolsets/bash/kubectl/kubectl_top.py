import argparse
from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.common.validators import regex_validator
from holmes.plugins.toolsets.bash.kubectl.constants import (
    SAFE_NAME_PATTERN,
    SAFE_NAMESPACE_PATTERN,
    SAFE_SELECTOR_PATTERN,
)


def create_kubectl_top_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "top",
        help="Display resource (CPU/memory) usage",
        exit_on_error=False,
    )
    parser.add_argument(
        "resource_type",
        choices=["nodes", "node", "pods", "pod"],
        help="Resource type to get usage for",
    )
    parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,  # Captures all remaining arguments
        default=[],  # Default to an empty list
    )


def stringify_top_command(cmd: Any) -> str:
    parts = ["kubectl", "top", cmd.resource_type]

    parts += cmd.options

    return " ".join(escape_shell_args(parts))

