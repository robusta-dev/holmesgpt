import argparse
import logging
import os
from typing import Dict, Any, Optional


from holmes.common.env_vars import BASH_TOOL_UNSAFE_ALLOW_ALL
from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.bash.common.bash import execute_bash_command
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


class BaseBashExecutorToolset(Toolset):
    config: Optional[BashExecutorConfig] = None

    def get_example_config(self):
        example_config = BashExecutorConfig()
        return example_config.model_dump()


class BaseBashTool(Tool):
    toolset: BaseBashExecutorToolset


class RunBashCommand(BaseBashTool):
    def __init__(self, toolset: BaseBashExecutorToolset):
        super().__init__(
            name="run_bash_command",
            description=(
                "Executes a given bash command and returns its standard output, "
                "standard error, and exit code."
                "The command is executed via 'bash -c \"<command>\"'."
                "Only some commands are allowed."
            ),
            parameters={
                "command": ToolParameter(
                    description="The bash command string to execute.",
                    type="string",
                    required=True,
                ),
                "timeout": ToolParameter(
                    description=(
                        "Optional timeout in seconds for the command execution. "
                        "Defaults to 60s."
                    ),
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        command_str = params.get("command")
        timeout = params.get("timeout", 60)

        if not command_str:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="The 'command' parameter is required and was not provided.",
                params=params,
            )

        if not isinstance(command_str, str):
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"The 'command' parameter must be a string, got {type(command_str).__name__}.",
                params=params,
            )

        command_to_execute = command_str
        try:
            command_to_execute = make_command_safe(command_str, self.toolset.config)
        
        except (argparse.ArgumentError, ValueError) as e:
            if not BASH_TOOL_UNSAFE_ALLOW_ALL:
                logging.info(f"Refusing LLM tool call {command_str}")
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Refusing to execute bash command. Only some commands are supported and this is likely because requested command is unsupported. Error: {str(e)}",
                    params=params,
                )

        return execute_bash_command(
            cmd=command_to_execute, timeout=timeout, params=params
        )

    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        command = params.get("command", "N/A")
        display_command = command[:200] + "..." if len(command) > 200 else command
        return display_command


class BashExecutorToolset(BaseBashExecutorToolset):
    def __init__(self):
        super().__init__(
            name="bash",
            enabled=False,
            description=(
                "Toolset for executing arbitrary bash commands on the system where Holmes is running. "
                "WARNING: This toolset provides powerful capabilities and should be "
                "enabled and used with extreme caution due to significant security risks. "
                "Ensure that only trusted users have access to this tool."
            ),
            docs_url="",  # TODO: Add relevant documentation URL
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Bash_Logo_Colored.svg/120px-Bash_Logo_Colored.svg.png",  # Example Bash icon
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[RunBashCommand(self)],
            tags=[ToolsetTag.CORE],
            is_default=False,
        )

        self._reload_llm_instructions()

    def _reload_llm_instructions(self):
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "bash_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")

    def prerequisites_callable(self, config: dict[str, Any]) -> tuple[bool, str]:
        if config:
            self.config = BashExecutorConfig(**config)
        else:
            self.config = BashExecutorConfig()
        return True, ""
