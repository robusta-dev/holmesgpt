from holmes.plugins.toolsets.bash.common.bash_command import (
    SimpleBashCommand,
    StandardValidation,
)


class CutCommand(SimpleBashCommand):
    def __init__(self):
        super().__init__(
            name="cut",
            allowed_options=[],  # Allow all options except file operations
            denied_options=[StandardValidation.NO_FILE_OPTION],
        )
