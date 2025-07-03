import argparse
from typing import Any


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
    raise ValueError(
        "Use the tool `fetch_pod_logs` to fetch logs instead of running `kubectl logs` commands"
    )
