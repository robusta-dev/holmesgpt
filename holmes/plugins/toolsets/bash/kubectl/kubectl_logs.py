import argparse
from typing import Any

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


class KubectlLogsCommand(BashCommand):
    def __init__(self):
        super().__init__("logs")

    def add_parser(self, parent_parser: Any):
        parser = parent_parser.add_parser(
            "logs",
            exit_on_error=False,
            add_help=False,  # Disable help to avoid conflicts
            prefix_chars="\x00",  # Use null character as prefix to disable option parsing
        )

        parser.add_argument(
            "options",
            nargs=argparse.REMAINDER,
            default=[],
        )

    def validate_command(self, command: Any, original_command: str) -> None:
        pass

    def stringify_command(self, command: Any, original_command: str) -> str:
        parts = ["kubectl", "logs"]

        parts += command.options

        return " ".join(escape_shell_args(parts))
