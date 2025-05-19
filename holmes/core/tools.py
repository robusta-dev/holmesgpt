from abc import ABC, abstractmethod
import logging
import os
import re
import shlex
import subprocess
import tempfile
from typing import Callable, Dict, List, Literal, Optional, Union, Any, Tuple
from enum import Enum
from datetime import datetime
import sentry_sdk
import json
from jinja2 import Template
from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    Field,
    model_validator,
)

from holmes.core.openai_formatting import format_tool_to_open_ai_standard
from holmes.plugins.prompts import load_and_render_prompt


ToolsetPattern = Union[Literal["*"], List[str]]


class ToolResultStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    NO_DATA = "no_data"


class StructuredToolResult(BaseModel):
    schema_version: str = "robusta:v1.0.0"
    status: ToolResultStatus
    error: Optional[str] = None
    return_code: Optional[int] = None
    data: Optional[Any] = None
    url: Optional[str] = None
    invocation: Optional[str] = None
    params: Optional[Dict] = None

    def get_stringified_data(self) -> str:
        if self.data is None:
            return ""

        if isinstance(self.data, str):
            return self.data
        else:
            try:
                if isinstance(self.data, BaseModel):
                    return self.data.model_dump_json(indent=2)
                else:
                    return json.dumps(self.data, indent=2)
            except Exception:
                return str(self.data)


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


def format_tool_output(tool_result: Union[str, StructuredToolResult]) -> str:
    if isinstance(tool_result, StructuredToolResult):
        if tool_result.data and isinstance(tool_result.data, str):
            # Display logs and other string outputs in a way that is readable to humans.
            # To do this, we extract them from the result and print them as-is below.
            # The metadata is printed on a single line to
            data = tool_result.data
            tool_result.data = "The raw tool data is printed below this JSON"
            result_str = tool_result.model_dump_json(indent=2, exclude_none=True)
            result_str += f"\n{data}"
            return result_str
        else:
            return tool_result.model_dump_json(indent=2)
    else:
        return tool_result


class ToolsetStatusEnum(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    FAILED = "failed"


class ToolsetTag(str, Enum):
    CORE = "core"
    CLUSTER = "cluster"
    CLI = "cli"
    MCP = "mcp"


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
        return format_tool_to_open_ai_standard(
            tool_name=self.name,
            tool_description=self.description,
            tool_parameters=self.parameters,
        )

    def invoke(self, params: Dict) -> StructuredToolResult:
        logging.info(
            f"Running tool {self.name}: {self.get_parameterized_one_liner(sanitize_params(params))}"
        )
        result = self._invoke(params)
        # return format_tool_output(result)
        return result

    @abstractmethod
    def _invoke(self, params: Dict) -> StructuredToolResult:
        pass

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
        inferred_params = re.findall(r"\{\{\s*([\w]+)[\.\|]?.*?\s*\}\}", template)
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
            template = Template(cmd_or_script)  # type: ignore
        return template.render(params)

    def _build_context(self, params):
        params = sanitize_params(params)
        context = {**params}
        return context

    def _get_status(self, return_code: int, raw_output: str) -> ToolResultStatus:
        if return_code != 0:
            return ToolResultStatus.ERROR
        if raw_output == "":
            return ToolResultStatus.NO_DATA
        return ToolResultStatus.SUCCESS

    def _invoke(self, params) -> StructuredToolResult:
        if self.command is not None:
            raw_output, return_code, invocation = self.__invoke_command(params)
        else:
            raw_output, return_code, invocation = self.__invoke_script(params)  # type: ignore

        if self.additional_instructions and return_code == 0:
            logging.info(
                f"Applying additional instructions: {self.additional_instructions}"
            )
            output_with_instructions = self.__apply_additional_instructions(raw_output)
        else:
            output_with_instructions = raw_output

        error = (
            None
            if return_code == 0
            else f"Command `{invocation}` failed with return code {return_code}\nOutput:\n{raw_output}"
        )
        status = self._get_status(return_code, raw_output)

        return StructuredToolResult(
            status=status,
            error=error,
            return_code=return_code,
            data=output_with_instructions,
            params=params,
            invocation=invocation,
        )

    def __apply_additional_instructions(self, raw_output: str) -> str:
        try:
            result = subprocess.run(
                self.additional_instructions,  # type: ignore
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

    def __invoke_command(self, params) -> Tuple[str, int, str]:
        context = self._build_context(params)
        command = os.path.expandvars(self.command)  # type: ignore
        template = Template(command)  # type: ignore
        rendered_command = template.render(context)
        output, return_code = self.__execute_subprocess(rendered_command)
        return output, return_code, rendered_command

    def __invoke_script(self, params) -> str:
        context = self._build_context(params)
        script = os.path.expandvars(self.script)  # type: ignore
        template = Template(script)  # type: ignore
        rendered_script = template.render(context)

        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".sh"
        ) as temp_script:
            temp_script.write(rendered_script)
            temp_script_path = temp_script.name
        subprocess.run(["chmod", "+x", temp_script_path], check=True)

        try:
            output, return_code = self.__execute_subprocess(temp_script_path)
        finally:
            subprocess.run(["rm", temp_script_path])
        return output, return_code, rendered_script  # type: ignore

    def __execute_subprocess(self, cmd) -> Tuple[str, int]:
        try:
            logging.debug(f"Running `{cmd}`")
            result = subprocess.run(
                cmd,
                shell=True,
                text=True,
                check=False,  # do not throw error, we just return the error code
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            return result.stdout.strip(), result.returncode
        except Exception as e:
            logging.error(
                f"An unexpected error occurred while running '{cmd}': {e}",
                exc_info=True,
            )
            output = f"Command execution failed with error: {e}"
            return output, 1


class StaticPrerequisite(BaseModel):
    enabled: bool
    disabled_reason: str


class CallablePrerequisite(BaseModel):
    callable: Callable[[dict[str, Any]], Tuple[bool, str]]


class ToolsetCommandPrerequisite(BaseModel):
    command: str  # must complete successfully (error code 0) for prereq to be satisfied
    expected_output: Optional[str] = None  # optional


class ToolsetEnvironmentPrerequisite(BaseModel):
    env: List[str] = []  # optional


class Toolset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experimental: bool = False
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
    llm_instructions: Optional[str] = None

    _path: Optional[str] = PrivateAttr(None)
    _status: ToolsetStatusEnum = PrivateAttr(ToolsetStatusEnum.DISABLED)
    _error: Optional[str] = PrivateAttr(None)

    def override_with(self, override: "ToolsetYamlFromConfig") -> None:
        """
        Overrides the current attributes with values from the ToolsetYamlFromConfig loaded from custom config
        if they are not None.
        """
        for field, value in override.model_dump(
            exclude_unset=True,
            exclude=("name"),  # type: ignore
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
                        self._error = "Prerequisites check gave wrong output"
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
                    self._status = ToolsetStatusEnum.FAILED
                    self._error = prereq.disabled_reason
                    return

            elif isinstance(prereq, CallablePrerequisite):
                (enabled, error_message) = prereq.callable(self.config)
                if not enabled and error_message:
                    logging.warning(
                        f"Failed to enable tool {self.name}: {error_message}"
                    )
                if enabled:
                    self._status = ToolsetStatusEnum.ENABLED
                elif not enabled and error_message:
                    self._status = ToolsetStatusEnum.FAILED
                    self._error = error_message
                else:
                    self._status = ToolsetStatusEnum.DISABLED
                return

        self._status = ToolsetStatusEnum.ENABLED

    @abstractmethod
    def get_example_config(self) -> Dict[str, Any]:
        return {}

    def _load_llm_instructions(self, jinja_template: str):
        tool_names = [t.name for t in self.tools]
        self.llm_instructions = load_and_render_prompt(
            prompt=jinja_template,
            context={"tool_names": tool_names, "config": self.config},
        )


class YAMLToolset(Toolset):
    tools: List[YAMLTool]  # type: ignore

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.llm_instructions:
            self._load_llm_instructions(self.llm_instructions)

    def get_example_config(self) -> Dict[str, Any]:
        return {}


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

    def invoke(self, tool_name: str, params: Dict) -> StructuredToolResult:
        tool = self.get_tool_by_name(tool_name)
        return (
            tool.invoke(params)
            if tool
            else StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Could not find tool named {tool_name}",
            )
        )

    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        if name in self.tools_by_name:
            return self.tools_by_name[name]
        logging.warning(f"could not find tool {name}. skipping")
        return None

    @sentry_sdk.trace
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
    ] = []  # type: ignore
    tools: Optional[List[YAMLTool]] = []  # type: ignore
    description: Optional[str] = None  # type: ignore
    docs_url: Optional[str] = None
    icon_url: Optional[str] = None
    installation_instructions: Optional[str] = None
    config: Optional[Any] = None
    url: Optional[str] = None  # MCP toolset

    def get_example_config(self) -> Dict[str, Any]:
        return {}


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
