import logging
import re
import shlex
import subprocess
import tempfile
from typing import Dict, List, Literal, Optional, Union, Type, Any

import paramiko
from jinja2 import Template
from pydantic import BaseModel, ConfigDict, PrivateAttr
from langchain_core.tools import tool, BaseTool

ToolsetPattern = Union[Literal['*'], List[str]]

class LCToolParameter(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: str = "string"
    required: bool = True


# TODO: we may want to add an abstract base class for tools, which can be non-yaml too
class LCYAMLTool(BaseModel):
    name: str
    description: str
    title: Optional[str] = None
    command: Optional[str] = None
    script: Optional[str] = None
    parameters: Dict[str, LCToolParameter] = {}

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
                self.parameters[param] = LCToolParameter()

    def get_langchain_tool_args_format(self):
        tool_properties = {}
        for param_name, param_attributes in self.parameters.items():
            tool_properties[param_name] = {"type": param_attributes.type}
            if param_attributes.title is not None:
                tool_properties[param_name]["title"] = param_attributes.title
            if param_attributes.description is not None:
                tool_properties[param_name]["description"] = param_attributes.description
        return tool_properties

    def get_parameterized_one_liner(self, params):
        params = sanitize_params(params)
        cmd_or_script = self.command or self.script
        template = Template(cmd_or_script)
        return template.render(params)
    
    def invoke(self, params) -> str:
        params = sanitize_params(params)
        if self.command is not None:
            return self.__invoke_command(params)
        else:
            return self.__invoke_script(params)

    def _run(self, params):
        params = sanitize_params(params)
        if self.command is not None:
            return self.__invoke_command(params)
        else:
            return self.__invoke_script(params)

    def __invoke_command(self, params) -> str:
        template = Template(self.command)
        rendered_command = template.render(params)
        logging.info(f"Running `{rendered_command}`")
        return self.__execute_subprocess(rendered_command)

    def __invoke_script(self, params) -> str:
        template = Template(self.script)
        rendered_script = template.render(params)

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
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL
            )
            return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        except subprocess.CalledProcessError as e:
            return f"Command `{cmd}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"


class LangchainYamlTool(BaseTool):
    yamltool: LCYAMLTool = None
    name: str = None
    description: str = None

    # def __init__(self, yamltool: LCYAMLTool, **data: Any):
    #     # super().__init__()
    #     self.name = yamltool.name
    #     self.description = yamltool.description
    #     self.yamltool = yamltool
    #     super().__init__(**data)
    #     self.
    """
      "input": "I need to gather information about the affected Kubernetes pod and its status. 
      I will start by using `kubectl_get` to get details of the specific pod experiencing the CrashLoopBackOff state.
      Action: kubectl_get
      Action Input: webapp --show-labels"

    """
    def _run(self, **tool_kwargs):
        # params = sanitize_params(params)
        template = Template(self.yamltool.command)
        rendered_command = template.render(tool_kwargs)
        logging.info(f"Running `{rendered_command}`")
        if self.yamltool.command is not None:
            return self.__execute_ssh(rendered_command)
        else:
            return self.__invoke_script(rendered_command)

    def invoke_command(self, params) -> str:
        template = Template(self.yamltool.command)
        rendered_command = template.render(params)
        logging.info(f"Running `{rendered_command}`")
        return self.execute_subprocess(rendered_command)

    def __execute_ssh(self, cmd) -> str:

        ssh = paramiko.SSHClient()
        try:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # ssh.connect(hostname='192.168.56.101', port=22,
            #             username='root', password='Gien@2022')
            ssh.connect(hostname='10.64.12.84', port=22,
                        username='root', password='Gientech2022!')
            stdin, stdout, stderr = ssh.exec_command(cmd)
            result = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            if error != "":
                return f"Error: \n{error}"
            return result
            # return f"stdout:\n{result}\nstderr:\n{error}"
        except Exception as ex:
            return f"Command `{cmd}` failed with err:\n{ex}"
        finally:
            ssh.close()

    def execute_subprocess(self, cmd) -> str:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL
            )
            return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        except subprocess.CalledProcessError as e:
            return f"Command `{cmd}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"

class LCToolsetPrerequisite(BaseModel):
    command: str                 # must complete successfully (error code 0) for prereq to be satisfied
    expected_output: str = None  # optional

class LCToolset(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str
    prerequisites: List[LCToolsetPrerequisite] = []
    tools: List[LCYAMLTool]

    _path: PrivateAttr = None
    _enabled: PrivateAttr = None
    _disabled_reason: PrivateAttr = None

    def set_path(self, path):
        self._path = path

    def get_path(self):
        return self._path

    def is_enabled(self):
        if self._enabled is None:
            raise Exception("Must call check_prerequisites() before is_enabled()")
        return self._enabled

    def get_disabled_reason(self):
        if self._enabled != False:
            raise Exception("Can only get disabled reason for disabled toolset")
        return self._disabled_reason

    def check_prerequisites(self):
        for prereq in self.prerequisites:
            try:
                result = subprocess.run(prereq.command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if prereq.expected_output and prereq.expected_output not in result.stdout:
                    self._enabled = False
                    self._disabled_reason = f"prereq check gave wrong output"
                    return
            except subprocess.CalledProcessError as e:
                self._enabled = False
                self._disabled_reason = f"prereq check failed w/ errorcode {e.returncode}"
                logging.debug(f"Toolset {self.name} : Failed to run prereq command {prereq}", exc_info=True)
                return
        self._enabled = True

class LCYAMLToolExecutor:
    def __init__(self, toolsets: List[LCToolset]):
        toolsets_by_name = {}
        for ts in toolsets:
            if ts.name in toolsets_by_name:
                logging.warning(f"Overriding toolset '{ts.name}'!")
            toolsets_by_name[ts.name] = ts

        self.tools_by_name = {}
        for ts in toolsets_by_name.values():
            for tool in ts.tools:
                if tool.name in self.tools_by_name:
                    logging.warning(f"Overriding tool '{tool.name}'!")
                self.tools_by_name[tool.name] = tool

    def invoke(self, tool_name: str, params: Dict) -> str:
        tool = self.get_tool_by_name(tool_name)
        return tool.invoke(params)

    def get_tool_by_name(self, name: str):
        return self.tools_by_name[name]
    def get_all_tools_openai_format(self):
        return [tool.get_openai_format() for tool in self.tools_by_name.values()]


def get_matching_toolsets(all_toolsets: List[LCToolset], pattern: ToolsetPattern):
    if pattern == "*":
        return all_toolsets

    matching_toolsets = []
    for pat in pattern:
        pat = re.compile(pat.replace('*', '.*'))
        matching_toolsets.extend([ts for ts in all_toolsets if pat.match(ts.name)])

    return matching_toolsets

def sanitize(param):
    # allow empty strings to be unquoted - useful for optional params
    # it is up to the user to ensure that the command they are using is ok with empty strings
    # and if not to take that into account via an appropriate jinja template
    if param == "":
        return ""

    return shlex.quote(str(param))

def sanitize_params(params):
    return {k: sanitize(str(v)) for k, v in params.items()}
