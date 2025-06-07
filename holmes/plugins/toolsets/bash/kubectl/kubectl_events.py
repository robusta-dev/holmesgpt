import argparse
import re
from typing import Any

from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.common.validators import regex_validator

MAX_FOR_OBJ_SIZE = 253
for_object_pattern = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_./:]*$")
VALID_EVENT_TYPES = {"Normal", "Warning"}


def create_kubectl_events_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "events",
        help="List events",
        exit_on_error=False,  # Important for library use
    )
    parser.add_argument(
        "-n",
        "--namespace",
        type=regex_validator("namespace", re.compile(r"^[a-z0-9][a-z0-9\-]*$")),
    )
    parser.add_argument("-A", "--all-namespaces", action="store_true")
    parser.add_argument(
        "-l",
        "--selector",
        type=regex_validator("selector", re.compile(r"^[a-zA-Z0-9\-_.=,!()]+$")),
    )
    parser.add_argument(
        "--field-selector",
        type=regex_validator("field selector", re.compile(r"^[a-zA-Z0-9\-_.=,!()]+$")),
    )
    parser.add_argument("--for", dest="for_object", type=_validate_for_object)
    parser.add_argument("--types", type=_validate_event_types)
    parser.add_argument("-w", "--watch", action="store_true")
    parser.add_argument("--no-headers", action="store_true")


def _validate_for_object(value: str) -> str:
    """Validate the --for object parameter."""

    if not for_object_pattern.match(value):
        raise argparse.ArgumentTypeError(f"Invalid for_object: {value}")
    if len(value) > MAX_FOR_OBJ_SIZE:
        raise argparse.ArgumentTypeError(
            f"for_object too long. Max allowed size is {MAX_FOR_OBJ_SIZE} but received {len(value)}"
        )
    return value


def _validate_event_types(value: str) -> str:
    """Validate the --types parameter."""
    type_list = [t.strip() for t in value.split(",")]

    for event_type in type_list:
        if event_type not in VALID_EVENT_TYPES:
            raise argparse.ArgumentTypeError(f"Invalid event type: {event_type}")
    return value


def stringify_events_command(cmd: Any) -> str:
    parts = ["kubectl", "events"]

    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    elif cmd.namespace:
        parts.extend(["--namespace", cmd.namespace])

    if cmd.selector:
        parts.extend(["--selector", cmd.selector])

    if cmd.field_selector:
        parts.extend(["--field-selector", cmd.field_selector])

    if cmd.for_object:
        parts.extend(["--for", cmd.for_object])

    if cmd.types:
        parts.extend(["--types", cmd.types])

    if cmd.watch:
        parts.append("--watch")

    if cmd.no_headers:
        parts.append("--no-headers")

    return " ".join(escape_shell_args(parts))
