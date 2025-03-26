import os
import json
import logging
import hashlib
from typing import Any, Dict, Optional
import subprocess

from pydantic import BaseModel
from holmes.core.tools import (
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
)

TOKEN_FILE = "used_tokens.json"


def load_used_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return {}


def save_used_token(token_hash):
    used_tokens = load_used_tokens()
    used_tokens[token_hash] = True
    with open(TOKEN_FILE, "w") as f:
        json.dump(used_tokens, f)


def validate_token(config_token: str, supplied_token: str) -> bool:
    if not supplied_token.startswith(config_token):
        return False
    token_hash = hashlib.sha256(supplied_token.encode()).hexdigest()
    used_tokens = load_used_tokens()
    if token_hash in used_tokens:
        return False
    save_used_token(token_hash)
    return True


class BashToolConfig(BaseModel):
    bash_execution_token: str


class BaseBashTool(Tool):
    toolset: "BashToolset"


class ExecuteBashCommand(BaseBashTool):
    def __init__(self, toolset: "BashToolset"):
        super().__init__(
            name="execute_bash_command",
            description="Execute a bash command locally",
            parameters={
                "command": ToolParameter(
                    description="The bash command to execute",
                    type="string",
                    required=True,
                ),
                "token": ToolParameter(
                    description="A one-time token to authorize execution",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        command = params.get("command")
        token = params.get("token")

        if not validate_token(self.toolset.config.bash_execution_token, token):
            return "Invalid or already used token."
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode != 0:
                return f"Command failed with error: {stderr or 'Unknown error'}"

            if not stdout and not stderr:
                return "Command executed successfully but returned no output."

            return f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}" if stderr else stdout

        except subprocess.TimeoutExpired:
            return "Command execution timed out."
        except Exception as e:
            return f"Execution error: {str(e)}"

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"execute_bash_command({params.get('command')})"


class BashToolset(Toolset):
    config: Optional[BashToolConfig] = None

    def __init__(self):
        super().__init__(
            name="bash",
            enabled=False,
            description="Provides the ability to execute bash commands locally with a one-time token system.",
            docs_url="",
            icon_url="https://img.icons8.com/color/512/bash.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[ExecuteBashCommand(self)],
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config:
            logging.error("Missing execution token in configuration.")
            return False, ""
        try:
            self.config = BashToolConfig(**config)
            return True, ""
        except Exception:
            logging.exception("Error loading execution token configuration.")
            return False, ""

    def get_example_config(self) -> Dict[str, Any]:
        return {}
