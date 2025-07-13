# type: ignore
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
import urllib

from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolResultStatus,
    Toolset,
    ToolsetStatusEnum,
    YAMLToolset,
)
from holmes.plugins.toolsets import load_builtin_toolsets, load_toolsets_from_file
from tests.llm.utils.constants import AUTO_GENERATED_FILE_SUFFIX
from braintrust import Span, SpanTypeAttribute

ansi_escape = re.compile(r"\x1B\[([0-9]{1,3}(;[0-9]{1,2};?)?)?[mGK]")


def strip_ansi(text):
    return ansi_escape.sub("", text)


class MockMetadata(BaseModel):
    toolset_name: str
    tool_name: str
    match_params: Optional[Dict] = None  # None will match all params


class ToolMock(MockMetadata):
    source_file: str
    return_value: StructuredToolResult


def ensure_non_error_returned(
    original_tool_result: Optional[StructuredToolResult],
) -> StructuredToolResult:
    if original_tool_result and original_tool_result.status in [
        ToolResultStatus.SUCCESS,
        ToolResultStatus.NO_DATA,
    ]:
        return original_tool_result
    elif original_tool_result:
        logging.warning(
            f"Overriding tool call result with a NO_DATA mock value: {original_tool_result.status}"
        )
        return StructuredToolResult(
            status=ToolResultStatus.NO_DATA, params=original_tool_result.params
        )
    else:
        logging.warning("Overriding empty tool call result with NO_DATA status")
        return StructuredToolResult(status=ToolResultStatus.NO_DATA)


class FallbackToolWrapper(Tool):
    """
    Tool that saves the result of the tool call to file if invoked.
    """

    _toolset_name: str
    _unmocked_tool: Tool
    _test_case_folder: str
    _add_params_to_mock_file: bool = True

    def __init__(
        self,
        unmocked_tool: Tool,
        test_case_folder: str,
        parent_span: Optional[Span] = None,
        toolset_name: str = "Unknown",
        add_params_to_mock_file: bool = True,
        generate_mocks: bool = True,
    ):
        super().__init__(
            name=unmocked_tool.name,
            description=unmocked_tool.description,
            parameters=unmocked_tool.parameters,
            user_description=unmocked_tool.user_description,
            add_params_to_mock_file=add_params_to_mock_file,
        )
        self._toolset_name = toolset_name
        self._unmocked_tool = unmocked_tool
        self._test_case_folder = test_case_folder
        self._parent_span = parent_span
        self._add_params_to_mock_file = add_params_to_mock_file
        self._generate_mocks = generate_mocks

    def _get_mock_file_path(self, tool_params: Dict):
        if self._add_params_to_mock_file:
            params_data = "_".join(str(tool_params[k]) for k in sorted(tool_params))
            params_data = f"_{params_data}"
        else:
            params_data = ""

        params_data = sanitize_filename(params_data)
        return f"{self._test_case_folder}/{self.name}{params_data}.txt{AUTO_GENERATED_FILE_SUFFIX}"

    def _auto_generate_mock_file(self, tool_result: StructuredToolResult, params: Dict):
        mock_metadata_json = MockMetadata(
            toolset_name=self._toolset_name, tool_name=self.name, match_params=params
        ).model_dump_json()

        content = tool_result.data
        structured_output_without_data = tool_result.model_dump()
        structured_output_without_data["data"] = None

        mock_file_path = self._get_mock_file_path(params)
        logging.warning(f"Writing mock file for your convenience at {mock_file_path}")
        with open(mock_file_path, "w") as f:
            f.write(mock_metadata_json + "\n")
            f.write(json.dumps(structured_output_without_data) + "\n")
            if content:
                f.write(content)

    def _invoke(self, params) -> StructuredToolResult:
        span = None
        if self._parent_span:
            span = self._parent_span.start_span(
                name=self.name, type=SpanTypeAttribute.TOOL
            )
        try:
            logging.info(f"Invoking tool {self._unmocked_tool}")
            tool_result = self._unmocked_tool.invoke(params)
            metadata = tool_result.model_dump()
            del metadata["data"]

            if self._generate_mocks:
                self._auto_generate_mock_file(tool_result, params)
            else:
                tool_result = ensure_non_error_returned(tool_result)

            if span:
                span.log(
                    input=params,
                    output=tool_result.data,
                    metadata=metadata,
                )
            return tool_result
        except Exception as e:
            if span:
                span.log(
                    input=params,
                    output=str(e),
                )
            raise
        finally:
            if span:
                span.end()

    def get_parameterized_one_liner(self, params) -> str:
        return self._unmocked_tool.get_parameterized_one_liner(params)


class MockToolWrapper(Tool, BaseModel):
    mocks: List[ToolMock] = []

    def __init__(self, unmocked_tool: Tool, parent_span: Optional[Span]):
        super().__init__(
            name=unmocked_tool.name,
            description=unmocked_tool.description,
            parameters=unmocked_tool.parameters,
            user_description=unmocked_tool.user_description,
        )
        self._unmocked_tool: Tool = unmocked_tool
        self._parent_span: Optional[Span] = parent_span

    def find_matching_mock(self, params: Dict) -> Optional[ToolMock]:
        for mock in self.mocks:
            if not mock.match_params:  # wildcard
                return mock

            match = all(
                key in params and params[key] == mock_val or mock_val == "*"
                for key, mock_val in mock.match_params.items()
            )
            if match:
                return mock

    def _invoke(self, params) -> StructuredToolResult:
        span = None
        if self._parent_span:
            span = self._parent_span.start_span(
                name=self.name, type=SpanTypeAttribute.TOOL
            )

        try:
            mock = self.find_matching_mock(params)
            result = None
            if mock:
                result = mock.return_value
            else:
                result = self._unmocked_tool.invoke(params)

            if span:
                metadata = result.model_dump()
                tool_output = result.data
                del metadata["data"]
                span.log(
                    input=params,
                    output=tool_output,
                    metadata=metadata,
                )
        except Exception as e:
            if span:
                span.log(
                    input=params,
                    output=str(e),
                )
            raise
        finally:
            if span:
                span.end()
        return result

    def get_parameterized_one_liner(self, params) -> str:
        return self._unmocked_tool.get_parameterized_one_liner(params)


class MockToolset(Toolset):
    def get_status(self):
        return ToolsetStatusEnum.ENABLED

    def get_example_config(self) -> Dict[str, Any]:
        return {}

    def fetch_pod_logs(self):
        # Temporary placeholder to ensure the mocked version of logging toolset is considered a 'new' version
        # Which will ensure the correct logs prompt is present
        # it is safe to remove once all logs toolsets have been migrated
        pass


class MockToolsets:
    unmocked_toolsets: List[Toolset]
    enabled_toolsets: List[Toolset]
    configured_toolsets: List[Toolset]
    _mocks: List[ToolMock]
    generate_mocks: bool
    test_case_folder: str
    add_params_to_mock_file: bool = True

    def __init__(
        self,
        test_case_folder: str,
        generate_mocks: bool = True,
        run_live: bool = False,
        parent_span: Optional[Span] = None,
        add_params_to_mock_file: bool = True,
    ) -> None:
        self.generate_mocks = generate_mocks
        self.test_case_folder = test_case_folder
        self._parent_span = parent_span
        self._mocks = []
        self.enabled_toolsets = []
        self.configured_toolsets = []
        self.add_params_to_mock_file = add_params_to_mock_file
        self._enable_builtin_toolsets(run_live)
        self._update()
        self.run_live = run_live

    def _load_toolsets_definitions(self, run_live) -> List[Toolset]:
        config_path = os.path.join(self.test_case_folder, "toolsets.yaml")
        toolsets_definitions = None
        if os.path.isfile(config_path):
            toolsets_definitions = load_toolsets_from_file(
                toolsets_path=config_path, strict_check=False
            )

        return toolsets_definitions or []

    def _enable_builtin_toolsets(self, run_live: bool):
        self.unmocked_toolsets = load_builtin_toolsets()

        toolset_definitions = self._load_toolsets_definitions(run_live)

        for toolset in self.unmocked_toolsets:
            if toolset.is_default or isinstance(toolset, YAMLToolset):
                toolset.enabled = True

            definition = next(
                (d for d in toolset_definitions if d.name == toolset.name), None
            )
            if definition:
                toolset.config = definition.config
                toolset.enabled = definition.enabled
                self.configured_toolsets.append(toolset)

            if toolset.enabled:
                try:
                    toolset.check_prerequisites()
                except Exception:
                    logging.error(
                        f"check_prerequisites failed for toolset {toolset.name}.",
                        exc_info=True,
                    )

    def mock_tool(self, tool_mock: ToolMock):
        self._mocks.append(tool_mock)
        self._update()

    def _find_mocks_for_tool(self, toolset_name: str, tool_name: str) -> List[ToolMock]:
        found_mocks = []
        for tool_mock in self._mocks:
            if (
                tool_mock.toolset_name == toolset_name
                and tool_mock.tool_name == tool_name
            ):
                found_mocks.append(tool_mock)
        return found_mocks

    def _wrap_tool(self, tool: Tool, toolset_name: str) -> Tool:
        return FallbackToolWrapper(
            unmocked_tool=tool,
            toolset_name=toolset_name,
            test_case_folder=self.test_case_folder,
            parent_span=self._parent_span,
            add_params_to_mock_file=self.add_params_to_mock_file,
            generate_mocks=self.generate_mocks,
        )

    def _update(self):
        mocked_toolsets = []
        for toolset in self.unmocked_toolsets:
            mocked_tools = []
            has_mocks = False
            for i in range(len(toolset.tools)):
                tool = toolset.tools[i]
                mocks = self._find_mocks_for_tool(
                    toolset_name=toolset.name, tool_name=tool.name
                )
                wrapped_tool = self._wrap_tool(tool=tool, toolset_name=toolset.name)

                if len(mocks) > 0 and not self.run_live:
                    has_mocks = True
                    mock_tool = MockToolWrapper(
                        unmocked_tool=wrapped_tool, parent_span=self._parent_span
                    )
                    mock_tool.mocks = mocks
                    mocked_tools.append(mock_tool)
                else:
                    mocked_tools.append(wrapped_tool)

            if has_mocks or toolset.status == ToolsetStatusEnum.ENABLED:
                mocked_toolset = MockToolset(
                    name=toolset.name,
                    prerequisites=toolset.prerequisites,
                    tools=toolset.tools,
                    description=toolset.description,
                    llm_instructions=toolset.llm_instructions,
                )
                mocked_toolset.tools = mocked_tools
                mocked_toolset.status = ToolsetStatusEnum.ENABLED
                mocked_toolsets.append(mocked_toolset)

        enabled_toolsets = mocked_toolsets
        for toolset in self.configured_toolsets:
            mocked = None
            try:
                mocked = next(
                    toolset
                    for mocked_toolset in enabled_toolsets
                    if mocked_toolset.name == toolset.name
                )
            except StopIteration:
                pass
            if not mocked:
                enabled_toolsets.append(toolset)
        self.enabled_toolsets = enabled_toolsets


def sanitize_filename(original_file_name: str) -> str:
    """
    Sanitizes a potential filename to create a valid filename.
    http(s)://... -> scheme is removed.
    Characters not suitable for filenames are replaced with underscores.
    """

    # Remove scheme (http, https) if present
    filename = re.sub(r"^https?://", "", original_file_name, flags=re.IGNORECASE)

    # URL decode percent-encoded characters
    # (e.g., %20 becomes space, %2F becomes /)
    filename = urllib.parse.unquote(filename)

    # Replace characters not allowed in filenames.
    # Allowed characters are:
    #   - Alphanumeric (a-z, A-Z, 0-9)
    #   - Underscore (_)
    #   - Hyphen (-)
    #   - Dot (.)
    # The regex \w matches [a-zA-Z0-9_] in Python.
    # So, [^\w.-] matches any character that is NOT alphanumeric, underscore, dot, or hyphen.
    # These non-allowed characters are replaced with a single underscore.
    filename = re.sub(r"[^\w.-]", "_", filename)

    # Consolidate multiple consecutive underscores into one.
    filename = re.sub(r"__+", "_", filename)

    # Remove leading/trailing underscores and trailing dots.
    # Trailing dots can be problematic on some OS (e.g., Windows treats "file." as "file").
    filename = filename.strip("_")
    filename = filename.strip(".")

    return filename
