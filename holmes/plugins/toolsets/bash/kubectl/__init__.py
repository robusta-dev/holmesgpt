from typing import Any, Optional
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.kubectl.constants import (
    SAFE_NAME_PATTERN,
    SAFE_NAMESPACE_PATTERN,
    SAFE_SELECTOR_PATTERN,
    VALID_RESOURCE_TYPES,
)
from holmes.plugins.toolsets.bash.kubectl.kubectl_describe import (
    create_kubectl_describe_parser,
    stringify_describe_command,
)
from holmes.plugins.toolsets.bash.kubectl.kubectl_events import (
    create_kubectl_events_parser,
    stringify_events_command,
)
from holmes.plugins.toolsets.bash.kubectl.kubectl_top import (
    create_kubectl_top_parser,
    stringify_top_command,
)
from holmes.plugins.toolsets.bash.kubectl.kubectl_get import (
    create_kubectl_get_parser,
    stringify_get_command,
)
from holmes.plugins.toolsets.bash.kubectl.kubectl_run import (
    create_kubectl_run_parser,
    stringify_run_command,
)


def create_kubectl_parser(parent_parser: Any):
    kubectl_parser = parent_parser.add_parser(
        "kubectl", help="Kubernetes command-line tool", exit_on_error=False
    )
    action_subparsers = kubectl_parser.add_subparsers(
        dest="action",
        required=True,
        help="Action to perform (e.g., get, apply, delete)",
    )
    create_kubectl_get_parser(action_subparsers)
    create_kubectl_describe_parser(action_subparsers)
    create_kubectl_top_parser(action_subparsers)
    create_kubectl_events_parser(action_subparsers)
    create_kubectl_run_parser(action_subparsers)


def validate_kubectl_command(cmd: Any) -> None:
    """
    Validate common kubectl command fields to prevent injection attacks.
    Raises ValueError if validation fails.
    """

    # Validate resource type
    if cmd.resource_type.lower() not in VALID_RESOURCE_TYPES:
        raise ValueError(f"Invalid resource type: {cmd.resource_type}")

    # Validate resource name if provided
    if cmd.resource_name:
        if not SAFE_NAME_PATTERN.match(cmd.resource_name):
            raise ValueError(f"Invalid resource name: {cmd.resource_name}")
        if len(cmd.resource_name) > 253:
            raise ValueError("Resource name too long")

    # Validate namespace if provided
    if cmd.namespace:
        if not SAFE_NAMESPACE_PATTERN.match(cmd.namespace):
            raise ValueError(f"Invalid namespace: {cmd.namespace}")
        if len(cmd.namespace) > 63:
            raise ValueError("Namespace name too long")

    # Validate selectors if provided
    if cmd.selector:
        if not SAFE_SELECTOR_PATTERN.match(cmd.selector):
            raise ValueError(f"Invalid label selector: {cmd.selector}")
        if len(cmd.selector) > 1000:
            raise ValueError("Label selector too long")


def stringify_kubectl_command(command: Any, config: Optional[BashExecutorConfig]):
    if command.cmd == "kubectl":
        if command.action == "get":
            return stringify_get_command(command)
        elif command.action == "describe":
            return stringify_describe_command(command)
        elif command.action == "top":
            return stringify_top_command(command)
        elif command.action == "events":
            return stringify_events_command(command)
        elif command.action == "run":
            return stringify_run_command(command, config)
        else:
            raise ValueError(
                f"Unsupported {command.tool_name} action {command.action}. Supported actions are: get, describe, events, top, run"
            )
    else:
        raise ValueError(f"Unsupported command {command.tool_name}")
