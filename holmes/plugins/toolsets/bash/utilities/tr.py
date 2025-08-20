import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args


class TrCommand(BashCommand):
    def __init__(self):
        super().__init__("tr")

    def add_parser(self, parent_parser: Any):
        parser = parent_parser.add_parser(
            "tr",
            help="Translate or delete characters",
            exit_on_error=False,
            add_help=False,  # Disable help to avoid conflicts
            prefix_chars="\x00",  # Use null character as prefix to disable option parsing
        )

        # Capture all arguments for validation
        parser.add_argument(
            "options",
            nargs=argparse.REMAINDER,
            default=[],
            help="tr options and character sets",
        )
        return parser

    def validate_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> None:
        # tr is allowed to have character set arguments, but not file paths
        # We only block absolute file paths and common file extensions
        for option in command.options:
            if not option.startswith("-"):
                # Allow character sets but block obvious file paths
                if (
                    option.startswith("/")
                    or option.endswith(".txt")
                    or option.endswith(".log")
                    or option.endswith(".py")
                    or option.endswith(".js")
                    or option.endswith(".json")
                ):
                    raise ValueError(
                        "File arguments are not allowed - tr can only process piped input"
                    )

    def stringify_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> str:
        parts = ["tr"]
        parts.extend(command.options)
        return " ".join(escape_shell_args(parts))
