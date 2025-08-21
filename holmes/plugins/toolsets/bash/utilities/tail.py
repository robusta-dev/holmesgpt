from holmes.plugins.toolsets.bash.common.bash_command import (
    SimpleBashCommand,
)


class TailCommand(SimpleBashCommand):
    def __init__(self):
        super().__init__(
            name="tail",
            allowed_options=[],  # Allow all options except file operations
            denied_options=[],
        )
