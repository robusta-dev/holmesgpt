import argparse
import logging
import os
from typing import Dict, Any

import sentry_sdk


from holmes.common.env_vars import (
    BASH_TOOL_UNSAFE_ALLOW_ALL,
)
from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolParameter,
    StructuredToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.bash.common.bash import execute_bash_command
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


class BaseBashExecutorToolset(Toolset):
    def get_example_config(self):
        return {}


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

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        command_str = params.get("command")
        timeout = params.get("timeout", 60)

        if not command_str:
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error="The 'command' parameter is required and was not provided.",
                params=params,
            )

        if not isinstance(command_str, str):
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"The 'command' parameter must be a string, got {type(command_str).__name__}.",
                params=params,
            )

        command_to_execute = command_str

        # Only run the safety check if user has NOT approved the command
        if not user_approved:
            try:
                command_to_execute = make_command_safe(command_str)

            except (argparse.ArgumentError, ValueError) as e:
                with sentry_sdk.configure_scope() as scope:
                    scope.set_extra("command", command_str)
                    scope.set_extra("error", str(e))
                    scope.set_extra("unsafe_allow_all", BASH_TOOL_UNSAFE_ALLOW_ALL)
                    sentry_sdk.capture_exception(e)

                if not BASH_TOOL_UNSAFE_ALLOW_ALL:
                    logging.info(f"Refusing LLM tool call {command_str}")

                    return StructuredToolResult(
                        status=StructuredToolResultStatus.APPROVAL_REQUIRED,
                        error=f"Refusing to execute bash command. {str(e)}",
                        params=params,
                        invocation=command_str,
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
            enabled=True,
            description=(
                "Toolset for executing arbitrary bash commands on the system where Holmes is running. "
                "WARNING: This toolset provides powerful capabilities and should be "
                "enabled and used with extreme caution due to significant security risks. "
                "Ensure that only trusted users have access to this tool."
            ),
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/bash/",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Bash_Logo_Colored.svg/120px-Bash_Logo_Colored.svg.png",  # Example Bash icon
            prerequisites=[],
            tools=[RunBashCommand(self)],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )

        self._reload_llm_instructions()

    def _reload_llm_instructions(self):
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "bash_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
