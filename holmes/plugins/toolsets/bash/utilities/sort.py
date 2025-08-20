from holmes.plugins.toolsets.bash.common.bash_command import (
    SimpleBashCommand,
    StandardValidation,
)


class SortCommand(SimpleBashCommand):
    def __init__(self):
        super().__init__(
            name="sort",
            allowed_options=[],  # Allow all options except dangerous ones
            denied_options=[
                "-T",
                "--temporary-directory",
                StandardValidation.NO_FILE_OPTION,
            ],
        )
