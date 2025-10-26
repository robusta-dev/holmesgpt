import os
from pydantic import FilePath, ValidationError
from holmes.core.tools import Toolset, ToolsetSettings, ToolsetType, YAMLToolset
from typing import Any, List, Optional, Union
import logging
import yaml
import holmes.utils.env as env_utils

from holmes.plugins.toolsets.mcp.toolset_mcp import RemoteMCPToolset


def is_old_toolset_config(
    toolsets: Union[dict[str, dict[str, Any]], List[dict[str, Any]]],
) -> bool:
    # old config is a list of toolsets
    if isinstance(toolsets, list):
        return True
    return False


def load_toolsets_from_file(toolsets_path: str) -> List[Toolset]:
    loaded_toolsets: List[Toolset] = []
    with open(toolsets_path) as file:
        parsed_yaml = yaml.safe_load(file)
        if parsed_yaml is None:
            raise ValueError(
                f"Failed to load toolsets from {toolsets_path}: file is empty or invalid YAML."
            )
        toolsets_dict = parsed_yaml.get("toolsets", {})
        loaded_toolsets.extend(load_toolsets_from_config(toolsets_dict, toolsets_path))

        if not toolsets_dict:
            raise ValueError(f"No 'toolsets' key found in {toolsets_path}")

    return loaded_toolsets


def load_toolsets_from_config(
    toolsets: dict[str, dict[str, Any]],
    toolsets_path: str,
) -> List[Toolset]:
    """
    Load toolsets from a dictionary.
    :param toolsets: Dictionary of toolset configurations.
    :return: List of validated Toolset objects.
    """

    if not toolsets:
        return []

    loaded_toolsets: list[Toolset] = []
    if is_old_toolset_config(toolsets):
        message = "Old toolset config format detected, please update to the new format: https://holmesgpt.dev/data-sources/custom-toolsets/"
        logging.warning(message)
        raise ValueError(message)

    for name, config in toolsets.items():
        config["path"] = toolsets_path
        config["type"] = ToolsetType.CUSTOMIZED.value
        validated_toolset = load_toolset_from_definition(name, config)
        if validated_toolset is not None:
            loaded_toolsets.append(validated_toolset)

    return loaded_toolsets


# TODO: pass path to the toolset object
def load_toolset_from_definition(
    name: str, toolset_definition: dict[str, Any]
) -> Optional[Toolset]:
    try:
        # Resolve env var placeholders before creating the Toolset.
        # If done after, .override_with() will overwrite resolved values with placeholders
        # because model_dump() returns the original, unprocessed config from YAML.
        if toolset_definition:
            toolset_definition = env_utils.replace_env_vars_values(toolset_definition)

        validated_toolset: Toolset
        if toolset_definition.get("type") == ToolsetType.MCP.value:
            validated_toolset = RemoteMCPToolset(**toolset_definition, name=name)
        else:
            validated_toolset = YAMLToolset(**toolset_definition, name=name)
        return validated_toolset
    except ValidationError as e:
        logging.warning(f"Toolset '{name}' is invalid: {e}")
    except Exception:
        logging.warning("Failed to load toolset: %s", name, exc_info=True)

    return None


def load_toolset_settings_from_file(
    toolset_settings_path: str,
) -> dict[str, ToolsetSettings]:
    if not os.path.exists(toolset_settings_path):
        logging.warning(f"Toolset settings file {toolset_settings_path} does not exist")
        return {}

    with open(toolset_settings_path) as file:
        parsed_yaml = yaml.safe_load(file)
        if parsed_yaml is None:
            raise ValueError(
                f"Failed to load toolset settings from {toolset_settings_path}: file is empty or invalid YAML."
            )

    toolset_settings_dict = parsed_yaml.get("toolsets", {})
    toolset_settings: dict[str, ToolsetSettings] = {}
    for name, config in toolset_settings_dict.items():
        toolset_settings[name] = ToolsetSettings.model_validate(config)
    return toolset_settings


# def _load_toolsets_from_config(
#     toolsets: dict[str, dict[str, Any]],
# ) -> List[Toolset]:

#     custom_toolsets_dict: dict[str, dict[str, Any]] = {}
#     for toolset_name, toolset_config in toolsets.items():
#         if toolset_config.get("type") is None:
#             toolset_config["type"] = ToolsetType.CUSTOMIZED.value
#         # custom toolsets defaults to enabled when not explicitly disabled
#         if toolset_config.get("enabled", True) is False:
#             toolset_config["enabled"] = False
#         else:
#             toolset_config["enabled"] = True
#         custom_toolsets_dict[toolset_name] = toolset_config

#     # built-in toolsets and built-in MCP servers in the config can override the existing fields of built-in toolsets

#     # custom toolsets or MCP servers are expected to defined required fields
#     custom_toolsets = load_toolsets_from_config(toolsets=custom_toolsets_dict)

#     return custom_toolsets


# def _load_toolsets_from_file(
#     toolset_file_path: FilePath,
# ) -> List[Toolset]:

#     if not os.path.isfile(toolset_file_path):
#         raise FileNotFoundError(f"toolset file: {toolset_file_path} could not be found")

#     try:
#         parsed_yaml = benedict(toolset_file_path)
#     except Exception as e:
#         raise ValueError(
#             f"Failed to load toolsets from {toolset_file_path}, error: {e}"
#         ) from e

#     toolsets = parsed_yaml.get("toolsets", {})
#     if not toolsets:
#         logging.warning(f"No toolsets section found in {toolset_file_path}")
#         return []

#     # mcp_config: dict[str, dict[str, Any]] = parsed_yaml.get("mcp_servers", {}) # TODO: should this be here or moved to other place?

#     # for server_config in mcp_config.values():
#         # server_config["type"] = ToolsetType.MCP.value

#     for toolset_config in toolsets_config.values():
#         toolset_config["path"] = toolset_path

#     toolsets_config.update(mcp_config)

#     if not toolsets_config:
#         raise ValueError(
#             f"No 'toolsets' or 'mcp_servers' key found in: {toolset_path}"
#         )

#     toolsets_from_config = self._load_toolsets_from_config(
#         toolsets_config, builtin_toolsets_names
#     )


#     loaded_custom_toolsets.extend(toolsets_from_config)

#     return loaded_custom_toolsets


# TODO: Add docs
# TODO: Whats about mcp_servers?
def load_custom_toolsets_from_files(toolset_paths: List[FilePath]) -> List[Toolset]:
    """
    Loads toolsets config from custom toolset path with YAMLToolset class.

    Example configuration:
    # override the built-in toolsets with custom toolsets
    kubernetes/logs:
        enabled: false

    # define a custom toolset with strictly defined fields
    test/configurations:
        enabled: true
        icon_url: "example.com"
        description: "test_description"
        docs_url: "https://docs.docker.com/"
        prerequisites:
            - env:
                - API_ENDPOINT
            - command: "curl ${API_ENDPOINT}"
        additional_instructions: "jq -r '.result.results[].userData | fromjson | .text | fromjson | .log'"
        tools:
            - name: "curl_example"
                description: "Perform a curl request to example.com using variables"
                command: "curl -X GET '{{api_endpoint}}?query={{ query_param }}' "
    """
    loaded_custom_toolsets: List[Toolset] = []
    for toolset_path in toolset_paths:
        toolsets = load_toolsets_from_file(str(toolset_path))
        loaded_custom_toolsets.extend(toolsets)

    return loaded_custom_toolsets
