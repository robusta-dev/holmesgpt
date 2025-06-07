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
        "--containers",
        action="store_true",
        help="Display containers along with pods (for pods resource type)",
    )
    parser.add_argument(
        "--use-protocol-buffers",
        action="store_true",
        help="Use protocol buffers for fetching metrics",
    )
    parser.add_argument(
        "--sort-by",
        type=regex_validator("sort field", SAFE_NAME_PATTERN),
        help="Sort by cpu or memory",
    )
    parser.add_argument("--no-headers", action="store_true")


def stringify_top_command(cmd: Any) -> str:
    parts = ["kubectl", "top", cmd.resource_type]

    # Add resource name if specified
    if cmd.resource_name:
        parts.append(cmd.resource_name)

    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    elif cmd.namespace:
        parts.extend(["--namespace", cmd.namespace])

    if cmd.selector:
        parts.extend(["--selector", cmd.selector])

    if cmd.containers:
        parts.append("--containers")

    if cmd.use_protocol_buffers:
        parts.append("--use-protocol-buffers")

    if cmd.sort_by:
        parts.extend(["--sort-by", cmd.sort_by])

    if cmd.no_headers:
        parts.append("--no-headers")

    return " ".join(escape_shell_args(parts))
