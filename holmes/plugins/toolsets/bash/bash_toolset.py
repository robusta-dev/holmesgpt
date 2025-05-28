import argparse
import logging
import os
import random
import string
import subprocess
from typing import Dict, Any, Optional


from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.kubectl.kubectl_run import validate_image_and_commands
from holmes.plugins.toolsets.bash.parse_command import make_command_safe
from holmes.plugins.toolsets.utils import get_param_or_raise


class BaseBashExecutorToolset(Toolset):
    config: Optional[BashExecutorConfig] = None

    def get_example_config(self):
        example_config = BashExecutorConfig()
        return example_config.model_dump()


class BaseBashTool(Tool):
    toolset: BaseBashExecutorToolset


class KubectlRunImageCommand(BaseBashTool):
    def __init__(self, toolset: BaseBashExecutorToolset):
        super().__init__(
            name="kubectl_run_image",
            description=(
                "Executes `kubectl run <name> --image=<image> ... -- <command>` return the result"
            ),
            parameters={
                "image": ToolParameter(
                    description="The image to run",
                    type="string",
                    required=True,
                ),
                "command": ToolParameter(
                    description="The command to execute on the deployed pod",
                    type="string",
                    required=True,
                ),
                "namespace": ToolParameter(
                    description="The namespace in which to deploy the temporary pod",
                    type="string",
                    required=False,
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

    def _build_kubectl_command(self, params: dict, pod_name: str) -> str:
        namespace = params.get("namespace", "default")
        image = get_param_or_raise(params, "image")
        command_str = get_param_or_raise(params, "command")
        return f"kubectl run {pod_name} --image={image} --namespace={namespace} --rm --attach --restart=Never -i --tty -- {command_str}"

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        timeout = params.get("timeout", 60)

        image = get_param_or_raise(params, "image")
        command_str = get_param_or_raise(params, "command")
        validate_image_and_commands(
            image=image, container_command=command_str, config=self.toolset.config
        )

        pod_name = (
            "holmesgpt-debug-pod-"
            + "".join(random.choices(string.ascii_letters, k=8)).lower()
        )
        full_kubectl_command = self._build_kubectl_command(params, pod_name)
        try:
            process = subprocess.run(
                full_kubectl_command,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )

            result_data = (
                f"{full_kubectl_command}\n"
                f"{process.stdout.strip() if process.stdout else ''}"
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
                invocation=full_kubectl_command,
                return_code=process.returncode,
            )
        except subprocess.TimeoutExpired:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                data=f"Error: Command '{full_kubectl_command}' timed out after {timeout} seconds.",
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
                data=f"Error executing command '{full_kubectl_command}': {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        return self._build_kubectl_command(params, "<pod_name>")


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
            name="bash",
            enabled=True,  # Default state; can be overridden by global config.
            description=(
                "Toolset for executing arbitrary bash commands on the system where Holmes is running. "
                "WARNING: This toolset provides powerful capabilities and should be "
                "enabled and used with extreme caution due to significant security risks. "
                "Ensure that only trusted users have access to this tool."
            ),
            docs_url="",  # TODO: Add relevant documentation URL if available
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Bash_Logo_Colored.svg/120px-Bash_Logo_Colored.svg.png",  # Example Bash icon
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[RunBashCommand(self), KubectlRunImageCommand(self)],
            # Using CORE as per the provided example's structure.
            # In a real system, a more specific tag like 'SYSTEM_COMMANDS' or 'DANGEROUS' might be appropriate
            # if the ToolsetTag system supports custom tags or has more granular options.
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
