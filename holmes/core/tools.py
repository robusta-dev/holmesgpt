from abc import ABC, abstractmethod
import logging
import os
import re
import shlex
import subprocess
import tempfile
from typing import Callable, Dict, List, Literal, Optional, Union, Any
from enum import Enum
from datetime import datetime

from jinja2 import Template
from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    Field,
    model_validator,
)


ToolsetPattern = Union[Literal["*"], List[str]]


def sanitize(param):
    # allow empty strings to be unquoted - useful for optional params
    # it is up to the user to ensure that the command they are using is ok with empty strings
    # and if not to take that into account via an appropriate jinja template
    if param == "":
        return ""

    return shlex.quote(str(param))


def sanitize_params(params):
    return {k: sanitize(str(v)) for k, v in params.items()}


def get_matching_toolsets(
    all_toolsets: List["Toolset"], pattern: ToolsetPattern
) -> List["Toolset"]:
    """
    Get toolsets matching a given pattern.
    """
    if pattern == "*":
        return all_toolsets

    matching_toolsets = []
    for pat in pattern:
        regex = re.compile(pat.replace("*", ".*"))
        matching_toolsets.extend([ts for ts in all_toolsets if regex.match(ts.name)])
    return matching_toolsets


class ToolsetStatusEnum(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    FAILED = "failed"


class ToolsetTag(str, Enum):
    CORE = "core"
    CLUSTER = "cluster"
    CLI = "cli"


class ToolParameter(BaseModel):
    description: Optional[str] = None
    type: str = "string"
    required: bool = True


class Tool(ABC, BaseModel):
    name: str
    description: str
    parameters: Dict[str, ToolParameter] = {}
    user_description: Optional[str] = (
        None  # templated string to show to the user describing this tool invocation (not seen by llm)
    )
    additional_instructions: Optional[str] = None

    def get_openai_format(self):
        tool_properties = {}
        for param_name, param_attributes in self.parameters.items():
            tool_properties[param_name] = {"type": param_attributes.type}
            if param_attributes.description is not None:
                tool_properties[param_name][
                    "description"
                ] = param_attributes.description

        result = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "properties": tool_properties,
                    "required": [
                        param_name
                        for param_name, param_attributes in self.parameters.items()
                        if param_attributes.required
                    ],
                    "type": "object",
                },
            },
        }

        # gemini doesnt have parameters object if it is without params
        if tool_properties is None:
            result["function"].pop("parameters")

        return result

    @abstractmethod
    def invoke(self, params: Dict) -> str:
        return ""

    @abstractmethod
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return ""


class YAMLTool(Tool, BaseModel):
    command: Optional[str] = None
    script: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.__infer_parameters()

    def __infer_parameters(self):
        # Find parameters that appear inside self.command or self.script but weren't declared in parameters
        template = self.command or self.script
        inferred_params = re.findall(r"\{\{\s*(\w+)\s*\}\}", template)
        # TODO: if filters were used in template, take only the variable name
        # Regular expression to match Jinja2 placeholders with or without filters
        # inferred_params = re.findall(r'\{\{\s*(\w+)(\s*\|\s*[^}]+)?\s*\}\}', self.command)
        # for param_tuple in inferred_params:
        #    param = param_tuple[0]  # Extract the parameter name
        #    if param not in self.parameters:
        #        self.parameters[param] = ToolParameter()
        for param in inferred_params:
            if param not in self.parameters:
                self.parameters[param] = ToolParameter()

    def get_parameterized_one_liner(self, params) -> str:
        params = sanitize_params(params)
        if self.user_description:
            template = Template(self.user_description)
        else:
            cmd_or_script = self.command or self.script
            template = Template(cmd_or_script)
        return template.render(params)

    def _build_context(self, params):
        params = sanitize_params(params)
        context = {**params}
        return context

    def invoke(self, params) -> str:
        context = self._build_context(params)
        logging.info(f"Running tool: {self.get_parameterized_one_liner(context)}")
        if self.command is not None:
            raw_output = self.__invoke_command(params)
        else:
            raw_output = self.__invoke_script(params)

        if self.additional_instructions:
            logging.info(
                f"Applying additional instructions: {self.additional_instructions}"
            )
            return self.__apply_additional_instructions(raw_output)
        return raw_output

    def __apply_additional_instructions(self, raw_output: str) -> str:
        try:
            result = subprocess.run(
                self.additional_instructions,
                input=raw_output,
                shell=True,
                text=True,
                capture_output=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(
                f"Failed to apply additional instructions: {self.additional_instructions}. "
                f"Error: {e.stderr}"
            )
            return f"Error applying additional instructions: {e.stderr}"

    def __invoke_command(self, params) -> str:
        context = self._build_context(params)
        command = os.path.expandvars(self.command)
        template = Template(command)
        rendered_command = template.render(context)
        return self.__execute_subprocess(rendered_command)

    def __invoke_script(self, params) -> str:
        context = self._build_context(params)
        script = os.path.expandvars(self.script)
        template = Template(script)
        rendered_script = template.render(context)

        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".sh"
        ) as temp_script:
            temp_script.write(rendered_script)
            temp_script_path = temp_script.name
        subprocess.run(["chmod", "+x", temp_script_path], check=True)

        try:
            return self.__execute_subprocess(temp_script_path)
        finally:
            subprocess.run(["rm", temp_script_path])

    def __execute_subprocess(self, cmd) -> str:
        try:
            logging.debug(f"Running `{cmd}`")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
                stdin=subprocess.DEVNULL,
            )
            return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        except subprocess.CalledProcessError as e:
            return f"Command `{cmd}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"


class StaticPrerequisite(BaseModel):
    enabled: bool
    disabled_reason: str


class CallablePrerequisite(BaseModel):
    callable: Callable[[dict[str, Any]], bool]


class ToolsetCommandPrerequisite(BaseModel):
    command: str  # must complete successfully (error code 0) for prereq to be satisfied
    expected_output: str = None  # optional


class ToolsetEnvironmentPrerequisite(BaseModel):
    env: List[str] = []  # optional


class Toolset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    name: str
    description: str
    docs_url: Optional[str] = None
    icon_url: Optional[str] = None
    installation_instructions: Optional[str] = None
    additional_instructions: Optional[str] = ""
    prerequisites: List[
        Union[
            StaticPrerequisite,
            ToolsetCommandPrerequisite,
            ToolsetEnvironmentPrerequisite,
            CallablePrerequisite,
        ]
    ] = []
    tools: List[Tool]
    tags: List[ToolsetTag] = Field(
        default_factory=lambda: [ToolsetTag.CORE],
    )
    config: Optional[Any] = None
    is_default: bool = False

    _path: Optional[str] = PrivateAttr(None)
    _status: ToolsetStatusEnum = PrivateAttr(ToolsetStatusEnum.DISABLED)
    _error: Optional[str] = PrivateAttr(None)

    def override_with(self, override: "ToolsetYamlFromConfig") -> None:
        """
        Overrides the current attributes with values from the ToolsetYamlFromConfig loaded from custom config
        if they are not None.
        """
        for field, value in override.model_dump(
            exclude_unset=True, exclude=("name")
        ).items():
            if field in self.model_fields and value not in (None, [], {}, ""):
                setattr(self, field, value)

    @model_validator(mode="before")
    def preprocess_tools(cls, values):
        additional_instructions = values.get("additional_instructions", "")
        tools_data = values.get("tools", [])
        tools = []
        for tool in tools_data:
            if isinstance(tool, dict):
                tool["additional_instructions"] = additional_instructions
            if isinstance(tool, Tool):
                tool.additional_instructions = additional_instructions
            tools.append(tool)
        values["tools"] = tools

        return values

    def set_path(self, path: Optional[str]):
        self._path = path

    def get_path(self):
        return self._path

    def get_status(self):
        return self._status

    def get_error(self):
        return self._error

    def get_environment_variables(self) -> List[str]:
        env_vars = set()

        for prereq in self.prerequisites:
            if isinstance(prereq, ToolsetEnvironmentPrerequisite):
                env_vars.update(prereq.env)
        return list(env_vars)

    def interpolate_command(self, command: str) -> str:
        interpolated_command = os.path.expandvars(command)

        return interpolated_command

    def check_prerequisites(self):
        for prereq in self.prerequisites:
            if isinstance(prereq, ToolsetCommandPrerequisite):
                try:
                    command = self.interpolate_command(prereq.command)
                    result = subprocess.run(
                        command,
                        shell=True,
                        check=True,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if (
                        prereq.expected_output
                        and prereq.expected_output not in result.stdout
                    ):
                        self._status = ToolsetStatusEnum.FAILED
                        self._error = f"Prerequisites check gave wrong output"
                        return
                except subprocess.CalledProcessError as e:
                    self._status = ToolsetStatusEnum.FAILED
                    logging.debug(
                        f"Toolset {self.name} : Failed to run prereq command {prereq}; {str(e)}"
                    )
                    self._error = f"Prerequisites check failed with errorcode {e.returncode}: {str(e)}"
                    return

            elif isinstance(prereq, ToolsetEnvironmentPrerequisite):
                for env_var in prereq.env:
                    if env_var not in os.environ:
                        self._status = ToolsetStatusEnum.FAILED
                        self._error = f"Prerequisites check failed because environment variable {env_var} was not set"
                        return

            elif isinstance(prereq, StaticPrerequisite):
                if not prereq.enabled:
                    self._status = ToolsetStatusEnum.DISABLED
                    return

            elif isinstance(prereq, CallablePrerequisite):
                res = prereq.callable(self.config)
                if not res:
                    self._status = ToolsetStatusEnum.DISABLED
                    return

        self._status = ToolsetStatusEnum.ENABLED

    def get_example_config(self) -> Dict[str, Any]:
        return {}


class YAMLToolset(Toolset):
    tools: List[YAMLTool]


class ToolExecutor:
    def __init__(self, toolsets: List[Toolset]):
        self.toolsets = toolsets

        self.enabled_toolsets: list[Toolset] = list(
            filter(
                lambda toolset: toolset.get_status() == ToolsetStatusEnum.ENABLED,
                toolsets,
            )
        )

        toolsets_by_name: dict[str, Toolset] = {}
        for ts in self.enabled_toolsets:
            if ts.name in toolsets_by_name:
                logging.warning(f"Overriding toolset '{ts.name}'!")
            toolsets_by_name[ts.name] = ts

        self.tools_by_name: dict[str, Tool] = {}
        for ts in toolsets_by_name.values():
            for tool in ts.tools:
                if tool.name in self.tools_by_name:
                    logging.warning(
                        f"Overriding existing tool '{tool.name} with new tool from {ts.name} at {ts._path}'!"
                    )
                self.tools_by_name[tool.name] = tool

    def invoke(self, tool_name: str, params: Dict) -> str:
        tool = self.get_tool_by_name(tool_name)
        return tool.invoke(params) if tool else ""

    def get_tool_by_name(self, name: str) -> Optional[YAMLTool]:
        if name in self.tools_by_name:
            return self.tools_by_name[name]
        logging.warning(f"could not find tool {name}. skipping")
        return None

    def get_all_tools_openai_format(self):
        return [tool.get_openai_format() for tool in self.tools_by_name.values()]


class ToolsetYamlFromConfig(Toolset):
    name: str
    enabled: bool = True
    additional_instructions: Optional[str] = None
    prerequisites: List[
        Union[
            StaticPrerequisite,
            ToolsetCommandPrerequisite,
            ToolsetEnvironmentPrerequisite,
        ]
    ] = []
    tools: Optional[List[YAMLTool]] = []
    description: Optional[str] = None
    docs_url: Optional[str] = None
    icon_url: Optional[str] = None
    installation_instructions: Optional[str] = None
    config: Optional[Any] = None


class ToolsetDBModel(BaseModel):
    account_id: str
    cluster_id: str
    toolset_name: str
    icon_url: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    description: Optional[str] = None
    docs_url: Optional[str] = None
    installation_instructions: Optional[str] = None
    updated_at: str = Field(default_factory=datetime.now().isoformat)
