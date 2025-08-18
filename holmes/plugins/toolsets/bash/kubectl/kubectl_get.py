from typing import Any
import argparse
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.common.validators import (
    whitelist_validator,
)
from holmes.plugins.toolsets.bash.kubectl.constants import (
    VALID_RESOURCE_TYPES,
)


def create_kubectl_get_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "get",
        help="Display one or many resources",
        exit_on_error=False,  # Important for library use
    )
    parser.add_argument(
        "resource_type", type=whitelist_validator("resource type", VALID_RESOURCE_TYPES)
    )
    parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,  # Captures all remaining arguments
        default=[],  # Default to an empty list
    )


def stringify_get_command(cmd: Any) -> str:
    parts = ["kubectl", "get", cmd.resource_type]

    parts += cmd.options

    return " ".join(escape_shell_args(parts))
