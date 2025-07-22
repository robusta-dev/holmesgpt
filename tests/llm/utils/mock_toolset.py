# type: ignore
import glob
import json
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional
import urllib

from pydantic import BaseModel
import pytest

from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    Toolset,
    ToolsetStatusEnum,
    YAMLToolset,
)
from holmes.plugins.toolsets import load_builtin_toolsets, load_toolsets_from_file


# Custom exceptions for better error handling
class MockDataError(Exception):
    """Base exception for mock data errors."""

    def __init__(self, message: str, tool_name: Optional[str] = None):
        self.tool_name = tool_name
        if tool_name:
            helpful_message = (
                f"Missing mock data: '{message}'. \n"
                f"To fix this:\n"
                f"1. Run with live tools: RUN_LIVE=true pytest ...\n"
                f"2. Generate missing mocks (keeps existing, may cause inconsistent data): pytest ... --generate-mocks\n"
                f"3. Regenerate ALL mocks (replaces all existing, ensures consistency): pytest ... --regenerate-all-mocks\n\n"
            )
            super().__init__(helpful_message)
        else:
            super().__init__(message)


class MockDataNotFoundError(MockDataError):
    """Raised when mock data file doesn't exist."""

    pass


class MockDataCorruptedError(MockDataError):
    """Raised when mock data file can't be parsed."""

    pass


class MockValidationError(MockDataError):
    """Raised when mock data doesn't match tool signature."""

    pass


class MockMode(Enum):
    """Modes for mock tool execution."""

    MOCK = "mock"  # Use existing mock files
    GENERATE = "generate"  # Generate new mock files
    LIVE = "live"  # Use real tools without mocking


class MockMetadata(BaseModel):
    """Metadata stored in mock files."""

    toolset_name: str
    tool_name: str
    match_params: Optional[Dict] = None  # None will match all params


class ToolMock(MockMetadata):
    """Complete mock data including metadata and result."""

    source_file: str
    return_value: StructuredToolResult


def sanitize_filename(original_file_name: str) -> str:
    """
    Sanitizes a potential filename to create a valid filename.
    http(s)://... -> scheme is removed.
    Characters not suitable for filenames are replaced with underscores.
    """
    # Remove scheme (http, https) if present
    filename = re.sub(r"^https?://", "", original_file_name, flags=re.IGNORECASE)

    # URL decode percent-encoded characters
    filename = urllib.parse.unquote(filename)

    # Replace characters not allowed in filenames
    filename = re.sub(r"[^\w.-]", "_", filename)

    # Consolidate multiple consecutive underscores into one
    filename = re.sub(r"__+", "_", filename)

    # Remove leading/trailing underscores and dots
    filename = filename.strip("_").strip(".")

    return filename


class MockFileManager:
    """Handles reading and writing mock files."""

    def __init__(self, test_case_folder: str, add_params_to_filename: bool = True):
        self.test_case_folder = test_case_folder
        self.add_params_to_filename = add_params_to_filename
        self._mock_cache = None  # Cache for loaded mocks

    def _get_mock_file_path(self, tool_name: str, params: Dict) -> str:
        """Generate the path for a mock file."""
        if self.add_params_to_filename:
            params_data = "_".join(str(params[k]) for k in sorted(params))
            params_data = f"_{params_data}"
        else:
            params_data = ""

        params_data = sanitize_filename(params_data)
        return os.path.join(self.test_case_folder, f"{tool_name}{params_data}.txt")

    def read_mock(self, tool_name: str, params: Dict) -> Optional[ToolMock]:
        """Read mock data for the given tool and parameters by matching parameters."""
        # Load all mocks and find a matching one
        all_mocks = self._load_all_mocks()
        tool_mocks = all_mocks.get(tool_name, [])

        logging.debug(f"Looking for mock for {tool_name} with params {params}")
        logging.debug(f"Found {len(tool_mocks)} mocks for {tool_name}")

        # Find a mock that matches the parameters
        for mock in tool_mocks:
            logging.debug(f"Checking mock from {mock.source_file}")
            logging.debug(f"  Mock params: {mock.match_params}")
            logging.debug(
                f"  Match result: {self._params_match(mock.match_params, params)}"
            )
            if self._params_match(mock.match_params, params):
                logging.debug(f"Found matching mock: {mock.source_file}")
                return mock

        logging.debug(f"No matching mock found for {tool_name}")
        return None

    def _params_match(self, mock_params: Optional[Dict], actual_params: Dict) -> bool:
        """Check if mock parameters match the actual parameters.

        If mock_params is None, it matches any parameters.
        Otherwise, all keys in mock_params must exist in actual_params with matching values.
        """
        if mock_params is None:
            return True

        # Check that all mock params exist in actual params with same values
        for key, value in mock_params.items():
            if key not in actual_params or actual_params[key] != value:
                return False

        return True

    def write_mock(
        self,
        tool_name: str,
        toolset_name: str,
        params: Dict,
        result: StructuredToolResult,
    ) -> str:
        """Write mock data to disk."""
        mock_metadata = MockMetadata(
            toolset_name=toolset_name, tool_name=tool_name, match_params=params
        )

        # Prepare structured output without data field
        structured_output = result.model_dump()
        content = structured_output.pop("data", None)

        mock_file_path = self._get_mock_file_path(tool_name, params)

        with open(mock_file_path, "w") as f:
            f.write(mock_metadata.model_dump_json() + "\n")
            f.write(json.dumps(structured_output) + "\n")
            if content:
                f.write(content)

        logging.info(f"Wrote mock file: {mock_file_path}")

        # Invalidate cache when new mock is written
        self._mock_cache = None

        return mock_file_path

    def clear_mocks(self, request: pytest.FixtureRequest) -> List[str]:
        """Clear all mock files in the test case folder."""
        cleared_files = []
        patterns = [
            os.path.join(self.test_case_folder, "*.txt"),
            os.path.join(self.test_case_folder, "*.json"),
        ]

        for pattern in patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    cleared_files.append(os.path.basename(file_path))
                except Exception as e:
                    logging.warning(f"Could not remove {file_path}: {e}")

        if cleared_files:
            # Track via user_properties for xdist compatibility
            request.node.user_properties.append(
                ("mocks_cleared", f"{self.test_case_folder}:{len(cleared_files)}")
            )
            logging.info(
                f"Cleared {len(cleared_files)} mock files from {self.test_case_folder}"
            )

            # Invalidate the cache since mocks were cleared
            self._mock_cache = None

        return cleared_files

    def has_mock_files(self, tool_name: str) -> bool:
        """Check if any mock files exist for this tool."""
        # First check with glob pattern for efficiency
        pattern = os.path.join(self.test_case_folder, f"{tool_name}*.txt")
        if len(glob.glob(pattern)) > 0:
            return True

        # Also check loaded mocks in case filename doesn't match tool name
        all_mocks = self._load_all_mocks()
        return tool_name in all_mocks and len(all_mocks[tool_name]) > 0

    def _load_all_mocks(self) -> Dict[str, List[ToolMock]]:
        """Load all mock files in the directory and organize by tool name."""
        if self._mock_cache is not None:
            return self._mock_cache

        self._mock_cache = {}

        # Load all .txt files in the directory
        for file_path in glob.glob(os.path.join(self.test_case_folder, "*.txt")):
            try:
                with open(file_path, "r") as f:
                    lines = f.readlines()
                    if len(lines) < 1:
                        continue

                    # Try to parse first line as JSON metadata
                    try:
                        first_line = lines[0].strip()
                        metadata = json.loads(first_line)
                        if "tool_name" not in metadata:
                            continue
                    except json.JSONDecodeError:
                        # Not a mock file, skip
                        continue

                    # This looks like a mock file, parse it
                    if len(lines) < 2:
                        continue

                    structured_output = json.loads(lines[1].strip())
                    content = "".join(lines[2:]) if len(lines) > 2 else None
                    if content is not None:
                        structured_output["data"] = content

                    mock = ToolMock(
                        toolset_name=metadata.get("toolset_name", ""),
                        tool_name=metadata["tool_name"],
                        match_params=metadata.get("match_params"),
                        source_file=file_path,
                        return_value=StructuredToolResult(**structured_output),
                    )

                    # Add to cache organized by tool name
                    tool_name = metadata["tool_name"]
                    if tool_name not in self._mock_cache:
                        self._mock_cache[tool_name] = []
                    self._mock_cache[tool_name].append(mock)
                    logging.debug(
                        f"Loaded mock for {tool_name} from {file_path}: match_params={mock.match_params}"
                    )

            except Exception as e:
                logging.warning(f"Failed to load mock file {file_path}: {e}")
                continue

        return self._mock_cache


class MockableToolWrapper(Tool):
    """Wraps a single tool"""

    def __init__(
        self,
        tool: Tool,
        mode: MockMode,
        file_manager: MockFileManager,
        toolset_name: str,
        request: pytest.FixtureRequest,
    ):
        super().__init__(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            user_description=tool.user_description,
        )
        self._tool = tool
        self._mode = mode
        self._file_manager = file_manager
        self._toolset_name = toolset_name
        self._request = request

    def _invoke(self, params: Dict) -> StructuredToolResult:
        """Execute the tool based on the current mode."""
        if self._mode == MockMode.LIVE:
            # Live mode: just call the real tool
            logging.info(f"Calling live tool {self.name} with params: {params}")
            return self._tool.invoke(params)

        elif self._mode == MockMode.MOCK:
            # Mock mode: read from mock file
            mock = self._file_manager.read_mock(self.name, params)
            if not mock:
                raise MockDataNotFoundError(
                    f"No mock data found for tool '{self.name}' with params: {params}",
                    tool_name=self.name,
                )
            return mock.return_value

        elif self._mode == MockMode.GENERATE:
            # Generate mode: call real tool and save result
            logging.info(f"Generating mock for tool {self.name} with params: {params}")
            result = self._tool.invoke(params)

            # Write mock file
            mock_file_path = self._file_manager.write_mock(
                tool_name=self.name,
                toolset_name=self._toolset_name,
                params=params,
                result=result,
            )

            # Track generated mock via user_properties
            test_case = os.path.basename(self._file_manager.test_case_folder)
            mock_info = f"{test_case}:{self.name}:{os.path.basename(mock_file_path)}"
            self._request.node.user_properties.append(
                ("generated_mock_file", mock_info)
            )

            return result

        else:
            raise ValueError(f"Unknown mock mode: {self._mode}")

    def get_parameterized_one_liner(self, params: Dict) -> str:
        """Get a one-line description of the tool with parameters."""
        return self._tool.get_parameterized_one_liner(params)


class ToolsetConfigurator:
    """Handles toolset loading and configuration."""

    @staticmethod
    def load_builtin_toolsets() -> List[Toolset]:
        """Load all built-in toolsets."""
        return load_builtin_toolsets()

    @staticmethod
    def load_custom_toolsets(config_path: str) -> List[Toolset]:
        """Load custom toolsets from a YAML file."""
        if not os.path.isfile(config_path):
            return []
        return load_toolsets_from_file(toolsets_path=config_path, strict_check=False)

    @staticmethod
    def configure_toolsets(
        builtin_toolsets: List[Toolset], custom_definitions: List[Toolset]
    ) -> List[Toolset]:
        """Configure builtin toolsets with custom definitions."""
        configured = []

        for toolset in builtin_toolsets:
            # Enable default toolsets
            if toolset.is_default or isinstance(toolset, YAMLToolset):
                toolset.enabled = True

            # Apply custom configuration if available
            definition = next(
                (d for d in custom_definitions if d.name == toolset.name), None
            )
            if definition:
                toolset.config = definition.config
                toolset.enabled = definition.enabled
                configured.append(toolset)

            # Check prerequisites for enabled toolsets
            if toolset.enabled:
                try:
                    toolset.check_prerequisites()
                except Exception:
                    logging.error(
                        f"check_prerequisites failed for toolset {toolset.name}.",
                        exc_info=True,
                    )

        return configured


class SimplifiedMockToolset(Toolset):
    """Simplified mock toolset for testing."""

    def get_status(self):
        return ToolsetStatusEnum.ENABLED

    def get_example_config(self) -> Dict[str, Any]:
        return {}


class MockToolsetManager:
    """Manages mock toolsets for testing."""

    def __init__(
        self,
        test_case_folder: str,
        mock_generation_config,
        add_params_to_mock_file: bool = True,
        request: pytest.FixtureRequest = None,
    ):
        self.test_case_folder = test_case_folder
        self.request = request
        self.mode = mock_generation_config.mode

        # Initialize components
        self.file_manager = MockFileManager(test_case_folder, add_params_to_mock_file)
        self.configurator = ToolsetConfigurator()

        # Clear mocks if regenerating
        if mock_generation_config.regenerate_all_mocks:
            if request and test_case_folder not in getattr(
                mock_generation_config, "_cleared_folders", set()
            ):
                self.file_manager.clear_mocks(request)
                if not hasattr(mock_generation_config, "_cleared_folders"):
                    mock_generation_config._cleared_folders = set()
                mock_generation_config._cleared_folders.add(test_case_folder)

        # Load and configure toolsets
        self._initialize_toolsets()

    def _initialize_toolsets(self):
        """Initialize and configure toolsets."""
        # Load builtin toolsets
        builtin_toolsets = self.configurator.load_builtin_toolsets()

        # Load custom toolsets
        config_path = os.path.join(self.test_case_folder, "toolsets.yaml")
        custom_definitions = self.configurator.load_custom_toolsets(config_path)

        # Configure toolsets
        configured_toolsets = self.configurator.configure_toolsets(
            builtin_toolsets, custom_definitions
        )

        # Wrap tools based on mode
        self.enabled_toolsets = self._wrap_toolsets(
            builtin_toolsets, configured_toolsets
        )

    def _wrap_toolsets(
        self, builtin_toolsets: List[Toolset], configured_toolsets: List[Toolset]
    ) -> List[Toolset]:
        """Wrap toolsets with mock-aware tools."""
        if self.mode == MockMode.LIVE:
            # In live mode, just return enabled toolsets without wrapping
            enabled = [
                t for t in builtin_toolsets if t.status == ToolsetStatusEnum.ENABLED
            ]
            # Add configured toolsets that aren't already in enabled
            for toolset in configured_toolsets:
                if toolset not in enabled:
                    enabled.append(toolset)
            return enabled

        # For mock/generate modes, wrap tools
        wrapped_toolsets = []

        for toolset in builtin_toolsets:
            # Check if we have any mocks for this toolset
            has_mocks = any(
                self.file_manager.has_mock_files(tool.name) for tool in toolset.tools
            )

            # Only include toolsets that are enabled or have mocks
            if toolset.status == ToolsetStatusEnum.ENABLED or has_mocks:
                # Create wrapped tools
                wrapped_tools = [
                    MockableToolWrapper(
                        tool=tool,
                        mode=self.mode,
                        file_manager=self.file_manager,
                        toolset_name=toolset.name,
                        request=self.request,
                    )
                    for tool in toolset.tools
                ]

                # Create simplified mock toolset
                mock_toolset = SimplifiedMockToolset(
                    name=toolset.name,
                    prerequisites=toolset.prerequisites,
                    tools=wrapped_tools,
                    description=toolset.description,
                    llm_instructions=toolset.llm_instructions,
                )
                mock_toolset.status = ToolsetStatusEnum.ENABLED
                wrapped_toolsets.append(mock_toolset)

        # Add configured toolsets that aren't already wrapped
        for toolset in configured_toolsets:
            if not any(t.name == toolset.name for t in wrapped_toolsets):
                wrapped_toolsets.append(toolset)

        return wrapped_toolsets


# For backward compatibility
MockToolsets = MockToolsetManager

# Export list
__all__ = [
    "MockMode",
    "MockToolsetManager",
    "MockToolsets",
    "MockDataError",
    "MockDataNotFoundError",
    "MockDataCorruptedError",
    "MockValidationError",
    "MockFileManager",
    "MockableToolWrapper",
    "ToolsetConfigurator",
    "sanitize_filename",
]
