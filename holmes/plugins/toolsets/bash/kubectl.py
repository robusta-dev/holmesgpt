import subprocess
from typing import Dict, Any

from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)


class RunBashCommand(Tool):
    def __init__(self):
        super().__init__(
            name="run_kubectl_command",
            description=(
                "Executes a given kubectl command and returns its standard output, "
                "standard error, and exit code."
                "The command is executed via 'bash -c \"<command>\"'."
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
        )

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        command_str = params.get("command")
        timeout = params.get("timeout", 60)

        if not command_str:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data="Error: 'command' parameter is required and was not provided.",
                params=params,
            )

        if not isinstance(command_str, str):
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Error: 'command' parameter must be a string, got {type(command_str).__name__}.",
                params=params,
            )

        try:
            # Using shell=True with the command passed to 'bash -c' for explicit shell execution.
            # This is generally safer than passing command_str directly to shell=True if command_str
            # might contain shell metacharacters that are not intended to be part of the command itself.
            # However, the user is providing a "bash command", so they expect shell interpretation.
            # `subprocess.run([ "bash", "-c", command_str], ...)` is a common pattern.
            # Or `subprocess.run(command_str, shell=True, executable='/bin/bash', ...)`
            # For simplicity and directness matching "run any bash command":
            process = subprocess.run(
                command_str,
                shell=True,  # Allows shell features like pipes, wildcards, etc.
                executable="/bin/bash",  # Explicitly use bash
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,  # We handle the return code manually
            )

            result_data = (
                f"Command: {command_str}\n"
                f"Return Code: {process.returncode}\n"
                f"Stdout:\n{process.stdout.strip()}\n"
                f"Stderr:\n{process.stderr.strip()}"
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


class KubectlExecutorToolset(Toolset):
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
            tools=[RunBashCommand()],
            # Using CORE as per the provided example's structure.
            # In a real system, a more specific tag like 'SYSTEM_COMMANDS' or 'DANGEROUS' might be appropriate
            # if the ToolsetTag system supports custom tags or has more granular options.
            tags=[ToolsetTag.CORE],
            is_default=True,  # CRITICAL: This toolset should NOT be enabled by default for security reasons.
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {"enabled": False}
