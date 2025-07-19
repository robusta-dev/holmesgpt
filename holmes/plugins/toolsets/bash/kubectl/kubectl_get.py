from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.common.validators import (
    regex_validator,
    whitelist_validator,
)
from holmes.plugins.toolsets.bash.kubectl.constants import (
    SAFE_JQ_PATTERN,
    SAFE_NAME_PATTERN,
    SAFE_NAMESPACE_PATTERN,
    SAFE_SELECTOR_PATTERN,
    VALID_OUTPUT_FORMATS,
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
        "resource_name",
        nargs="?",
        default=None,
        type=regex_validator("resource_name", SAFE_NAME_PATTERN),
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
        type=regex_validator("field-selector", SAFE_SELECTOR_PATTERN),
    )
    parser.add_argument(
        "-o", "--output", type=whitelist_validator("output", VALID_OUTPUT_FORMATS)
    )
    parser.add_argument("--sort-by", type=regex_validator("sort-by", SAFE_JQ_PATTERN))
    parser.add_argument(
        "--show-labels",
        action="store_true",
    )
    parser.add_argument(
        "--show-managed-fields",
        action="store_true",
    )
    parser.add_argument(
        "--no-headers",
        action="store_false",
    )
    parser.add_argument(
        "--include-uninitialized",
        action="store_true",
    )
    parser.add_argument(
        "--ignore-not-found",
        action="store_true",
    )


def stringify_get_command(cmd: Any) -> str:
    parts = ["kubectl", "get", cmd.resource_type]

    # Add resource name if specified
    if cmd.resource_name:
        parts.append(cmd.resource_name)

    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    if cmd.namespace:
        parts.extend(["--namespace", cmd.namespace])

    if cmd.selector:
        parts.extend(["--selector", cmd.selector])

    if cmd.field_selector:
        parts.extend(["--field-selector", cmd.field_selector])

    if cmd.output:
        parts.extend(["--output", cmd.output])
    if cmd.sort_by:
        parts.extend(["--sort-by", cmd.sort_by])

    if cmd.show_labels:
        parts.append("--show-labels")

    if cmd.show_managed_fields:
        parts.append("--show-managed-fields")

    if cmd.no_headers is not None and not cmd.no_headers:
        parts.append("--no-headers")

    if cmd.include_uninitialized:
        parts.append("--include-uninitialized")

    if cmd.ignore_not_found:
        parts.append("--ignore-not-found")

    return " ".join(escape_shell_args(parts))
