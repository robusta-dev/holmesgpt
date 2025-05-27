import argparse
import logging
import subprocess
from typing import Dict, Any, Optional, Union


from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
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
        try:
            safe_command_str = make_command_safe(command_str, self.toolset.config)
        except (argparse.ArgumentError, ValueError) as e:
            logging.info(f"Refusing LLM tool call {command_str}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Refusing to execute bash command. Only some commands are supported and this is likely because requested command is unsupported. Error: {str(e)}",
                params=params,
            )

        try:
            process = subprocess.run(
                safe_command_str,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )

            result_data = (
                f"{command_str}\n" f"{process.stdout.strip() if process.stdout else ''}"
            )

            status = (
                ToolResultStatus.SUCCESS
                if process.returncode == 0
                else ToolResultStatus.ERROR
            )

            return StructuredToolResult(
                status=status,
                data=result_data,
                params=params,
                invocation=safe_command_str,
                return_code=process.returncode,
            )
        except subprocess.TimeoutExpired:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Error: Command '{command_str}' timed out after {timeout} seconds.",
                params=params,
            )
        except FileNotFoundError:
            # This might occur if /bin/bash is not found, or if shell=False and command is not found
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data="Error: Bash executable or command not found. Ensure bash is installed and the command is valid.",
                params=params,
            )
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Error executing command '{command_str}': {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        command = params.get("command", "N/A")
        display_command = command[:200] + "..." if len(command) > 200 else command
        return display_command


class BashExecutorToolset(BaseBashExecutorToolset):
    def __init__(self):
        super().__init__(
            name="kubectl/bash",
            enabled=True,  # Default state; can be overridden by global config.
            description=(
                "Toolset for executing arbitrary bash commands on the system where Holmes is running. "
                "WARNING: This toolset provides powerful capabilities and should be "
                "enabled and used with extreme caution due to significant security risks. "
                "Ensure that only trusted users have access to this tool."
            ),
            docs_url="",  # TODO: Add relevant documentation URL if available
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Bash_Logo_Colored.svg/120px-Bash_Logo_Colored.svg.png",  # Example Bash icon
            prerequisites=[],
            tools=[RunBashCommand(self)],
            # Using CORE as per the provided example's structure.
            # In a real system, a more specific tag like 'SYSTEM_COMMANDS' or 'DANGEROUS' might be appropriate
            # if the ToolsetTag system supports custom tags or has more granular options.
            tags=[ToolsetTag.CORE],
            is_default=True,  # CRITICAL: This toolset should NOT be enabled by default for security reasons.
        )
