from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.common.validators import (
    regex_validator,
    whitelist_validator,
)
from holmes.plugins.toolsets.bash.kubectl.constants import (
    SAFE_NAME_PATTERN,
    SAFE_NAMESPACE_PATTERN,
    SAFE_SELECTOR_PATTERN,
    VALID_RESOURCE_TYPES,
)


def create_kubectl_describe_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "describe",
        help="Show details of a specific resource or group of resources",
        exit_on_error=False,  # Important for library use
    )
    parser.add_argument(
        "resource_type", type=whitelist_validator("resource type", VALID_RESOURCE_TYPES)
    )
    parser.add_argument(
        "resource_name",
        nargs="?",
        default=None,
        type=regex_validator("resource name", SAFE_NAME_PATTERN),
    )
    parser.add_argument(
        "-n", "--namespace", type=regex_validator("namespace", SAFE_NAMESPACE_PATTERN)
    )
    parser.add_argument("-A", "--all-namespaces", action="store_true")
    parser.add_argument(
        "-l", "--selector", type=regex_validator("selector", SAFE_SELECTOR_PATTERN)
    )
    parser.add_argument(
        "--field-selector",
        type=regex_validator("field selector", SAFE_SELECTOR_PATTERN),
    )
    parser.add_argument("--include-uninitialized", action="store_true")


def stringify_describe_command(cmd: Any) -> str:
    parts = ["kubectl", "describe", cmd.resource_type]

    # Add resource name if specified
    if cmd.resource_name:
        parts.append(cmd.resource_name)

    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    elif cmd.namespace:
        parts.extend(["--namespace", cmd.namespace])

    if cmd.selector:
        parts.extend(["--selector", cmd.selector])

    if cmd.field_selector:
        parts.extend(["--field-selector", cmd.field_selector])

    if cmd.include_uninitialized:
        parts.append("--include-uninitialized")

    return " ".join(escape_shell_args(parts))
