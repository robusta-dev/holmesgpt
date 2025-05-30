import json
import logging
import os
from typing import Any, List, Optional

from benedict import benedict
from pydantic import FilePath

from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import Toolset, ToolsetStatusEnum, ToolsetTag, ToolsetType
from holmes.plugins.toolsets import load_builtin_toolsets, load_toolsets_from_config

DEFAULT_TOOLSET_STATUS_LOCATION = os.path.expanduser("~/.holmes/toolsets_status.json")


class ToolsetManager:
    """
    ToolsetManager is responsible for managing toolset locally.
    It can refresh the status of all toolsets and cache the status to a file.
    It also provides methods to get toolsets by name and to get the list of all toolsets.
    """

    toolsets: Optional[dict[str, dict[str, Any]]]
    custom_toolsets: Optional[List[FilePath]]
    custom_toolsets_from_cli: Optional[List[FilePath]]

    toolset_status_location: FilePath

    def __init__(
        self,
        toolsets: Optional[dict[str, dict[str, Any]]] = None,
        custom_toolsets: Optional[List[FilePath]] = None,
        custom_toolsets_from_cli: Optional[List[FilePath]] = None,
        toolset_status_location: FilePath = DEFAULT_TOOLSET_STATUS_LOCATION,
    ):
        self.toolsets = toolsets
        self.custom_toolsets = custom_toolsets
        self.custom_toolsets_from_cli = custom_toolsets_from_cli
        self.toolset_status_location = toolset_status_location

    @property
    def cli_tool_tags(self) -> List[str]:
        """
        Returns the list of toolset tags that are relevant for CLI tools.
        A toolset is considered a CLI tool if it has any of cli tool tags:
        """
        return [ToolsetTag.CORE, ToolsetTag.CLI]

    @property
    def server_tool_tags(self) -> List[str]:
        """
        Returns the list of toolset tags that are relevant for CLI tools.
        A toolset is considered a CLI tool if it has any of UI tool tags:
        """
        return [ToolsetTag.CORE, ToolsetTag.CLUSTER]

    @staticmethod
    def get_toolset_definition_enabled(toolset_config: dict[str, Any]) -> bool:
        """
        Get the enabled status of the toolset from the config.
        Return False only when the toolset is explicitly defined as disabled in the config.
        This is helpful to enable the toolset specified in the config or custom toolset file without manually specifying
        'enabled: true'. Also, this avoid setting enabled to true by default, which can lead to unexpected behavior if
        the toolset is not ready to be used.
        """
        if "enabled" in toolset_config:
            if (
                isinstance(toolset_config["enabled"], bool)
                and not toolset_config["enabled"]
            ):
                return False
            # Normally benedict should translate the value of enabled to bool when well assigned,
            # but in case it doesn't, and to avoid unexpected behavior, we check if the value is a
            # string and if it is 'false' (case insensitive).
            elif (
                isinstance(toolset_config["enabled"], str)
                and toolset_config["enabled"].lower() == "false"
            ):
                return False
            # TODO(mainred): add validation for the enabled field to be bool or str other than a valid 'bool' string
        return True

    def _list_all_toolsets(
        self, dal: Optional[SupabaseDal] = None, check_prerequisites=True
    ) -> List[Toolset]:
        """
        List all built-in and custom toolsets.

        The method loads toolsets in this order, with later sources overriding earlier ones:
        1. Built-in toolsets
        2. Toolsets defined in self.toolsets can override both built-in and add new custom toolsets
        3. Custom toolsets from config files can override built-in toolsets conditionally:
          3.1 custom toolset from config can override both built-in and add new custom toolsets # for backward compatibility
          3.2 custom toolset from CLI can only add new custom toolsets
        """
        # Load built-in toolsets
        builtin_toolsets = load_builtin_toolsets(dal)
        toolsets_by_name: dict[str, Toolset] = {
            toolset.name: toolset for toolset in builtin_toolsets
        }
        builtin_toolsets_names = list(toolsets_by_name.keys())

        # build-in toolset is enabled when it's explicitly enabled in the toolset or custom toolset config
        if self.toolsets is not None:
            toolsets_from_config = self._load_toolsets_from_config(
                self.toolsets, builtin_toolsets_names, dal
            )

            if toolsets_from_config:
                self.add_or_merge_onto_toolsets(
                    toolsets_from_config,
                    toolsets_by_name,
                )

        # custom toolset should not override built-in toolsets
        # to test the new change of built-in toolset, we should make code change and re-compile the program
        custom_toolsets = self.load_custom_toolsets(builtin_toolsets_names)
        self.add_or_merge_onto_toolsets(
            custom_toolsets,
            toolsets_by_name,
        )

        # check_prerequisites against each enabled toolset
        if not check_prerequisites:
            return list(toolsets_by_name.values())
        for _, toolset in toolsets_by_name.items():
            if toolset.enabled:
                toolset.check_prerequisites()
            else:
                toolset.status = ToolsetStatusEnum.DISABLED

        return list(toolsets_by_name.values())

    def _load_toolsets_from_config(
        self,
        toolsets: dict[str, dict[str, Any]],
        builtin_toolset_names: list[str],
        dal: Optional[SupabaseDal] = None,
    ) -> List[Toolset]:
        if toolsets is None:
            logging.debug("No toolsets configured, skipping loading toolsets")
            return []

        builtin_toolsets_dict: dict[str, dict[str, Any]] = {}
        custom_toolsets_dict: dict[str, dict[str, Any]] = {}
        for toolset_name, toolset_config in toolsets.items():
            toolset_config["enabled"] = self.get_toolset_definition_enabled(
                toolset_config
            )
            if toolset_name in builtin_toolset_names:
                # build-in types was assigned when loaded
                builtin_toolsets_dict[toolset_name] = toolset_config
            else:
                toolset_config["type"] = ToolsetType.CUSTOMIZED.value
                custom_toolsets_dict[toolset_name] = toolset_config

        # built-in toolsets and built-in MCP servers in the config can override the existing fields of built-in toolsets
        builtin_toolsets = load_toolsets_from_config(
            builtin_toolsets_dict, strict_check=False
        )
        # custom toolsets or MCP servers are expected to defined required fields
        custom_toolsets = load_toolsets_from_config(
            toolsets=custom_toolsets_dict, strict_check=True
        )

        return builtin_toolsets + custom_toolsets

    def refresh_toolset_status(self, dal: Optional[SupabaseDal] = None):
        """
        Refresh the status of all toolsets and cache the status to a file.
        Loading cached toolsets status saves the time for runtime tool executor checking the status of each toolset

        enabled toolset when:
        - build-in toolset specified in the config and not explicitly disabled
        - custom toolset not explicitly disabled
        """

        all_toolsets = self._list_all_toolsets(dal=dal, check_prerequisites=True)

        if self.toolset_status_location and not os.path.exists(
            os.path.dirname(self.toolset_status_location)
        ):
            os.makedirs(os.path.dirname(self.toolset_status_location))
        with open(self.toolset_status_location, "w") as f:
            toolset_status = [
                json.loads(
                    toolset.model_dump_json(
                        include={"name", "status", "enabled", "type", "path", "error"}
                    )
                )
                for toolset in all_toolsets
            ]
            json.dump(toolset_status, f, indent=2)
        logging.info(f"Toolset statuses are cached to {self.toolset_status_location}")

    def load_toolset_with_status(
        self, dal: Optional[SupabaseDal] = None, refresh_status: bool = False
    ) -> List[Toolset]:
        """
        Load the toolset status from the cache file.
        If the file does not exist, return an empty list.
        """

        if not os.path.exists(self.toolset_status_location) or refresh_status:
            logging.info("refreshing toolset status")
            self.refresh_toolset_status(dal)

        cached_toolsets: List[dict[str, Any]] = []
        with open(self.toolset_status_location, "r") as f:
            cached_toolsets = json.load(f)

        toolsets_status_by_name: dict[str, dict[str, Any]] = {
            cached_toolset["name"]: cached_toolset for cached_toolset in cached_toolsets
        }

        all_toolsets_with_status = self._list_all_toolsets(
            dal=dal, check_prerequisites=False
        )
        for toolset in all_toolsets_with_status:
            if toolset.name in toolsets_status_by_name:
                # Update the status and error from the cached status
                cached_status = toolsets_status_by_name[toolset.name]
                toolset.status = ToolsetStatusEnum(cached_status["status"])
                toolset.error = cached_status.get("error", None)
                toolset.enabled = cached_status.get("enabled", True)
                toolset.type = ToolsetType(
                    cached_status.get("type", ToolsetType.BUILTIN)
                )
                toolset.path = cached_status.get("path", None)

        return all_toolsets_with_status

    def list_enabled_console_toolsets(
        self, dal: Optional[SupabaseDal] = None
    ) -> List[Toolset]:
        """
        List all enabled toolsets that cli tools can use.
        """
        toolsets_with_status = self.load_toolset_with_status(dal)
        return [
            ts
            for ts in toolsets_with_status
            if any(tag in self.cli_tool_tags for tag in ts.tags)
        ]

    def list_enabled_server_toolsets(
        self, dal: Optional[SupabaseDal] = None
    ) -> List[Toolset]:
        """
        List all toolsets that are enabled and have the server tool tags.
        """
        toolsets_with_status = self.load_toolset_with_status(dal)
        return [
            ts
            for ts in toolsets_with_status
            if any(tag in self.server_tool_tags for tag in ts.tags)
        ]

    def _load_toolsets_from_paths(
        self,
        toolset_paths: Optional[List[FilePath]],
        builtin_toolsets_names: list[str],
        check_conflict_default: bool = False,
    ) -> List[Toolset]:
        if not toolset_paths:
            logging.debug("No toolsets configured, skipping loading toolsets")
            return []

        loaded_custom_toolsets: List[Toolset] = []
        for toolset_path in toolset_paths:
            if not os.path.isfile(toolset_path):
                raise FileNotFoundError(f"toolset file {toolset_path} does not exist")

            try:
                parsed_yaml = benedict(toolset_path)
            except Exception as e:
                raise ValueError(
                    f"Failed to load toolsets from {toolset_path}, error: {e}"
                )
            toolsets_config: dict[str, dict[str, Any]] = parsed_yaml.get("toolsets", {})
            mcp_config: dict[str, dict[str, Any]] = parsed_yaml.get("mcp_servers", {})

            for server_config in mcp_config.values():
                server_config["type"] = ToolsetType.MCP

            for toolset_config in toolsets_config.values():
                toolset_config["path"] = toolset_path

            toolsets_config.update(mcp_config)

            if not toolsets_config:
                raise ValueError(
                    f"No 'toolsets' or 'mcp_servers' key found in: {toolset_path}"
                )

            toolsets_from_config = self._load_toolsets_from_config(
                toolsets_config, builtin_toolsets_names
            )
            if check_conflict_default:
                for toolset in toolsets_from_config:
                    if toolset.name in builtin_toolsets_names:
                        raise Exception(
                            f"Toolset {toolset.name} is already defined in the built-in toolsets. "
                            "Please rename the custom toolset or remove it from the custom toolsets configuration."
                        )

            loaded_custom_toolsets.extend(toolsets_from_config)

        return loaded_custom_toolsets

    def load_custom_toolsets(self, builtin_toolsets_names: list[str]) -> list[Toolset]:
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
        if not self.custom_toolsets and not self.custom_toolsets_from_cli:
            logging.debug(
                "No custom toolsets configured, skipping loading custom toolsets"
            )
            return []

        loaded_custom_toolsets: List[Toolset] = []
        custom_toolsets = self._load_toolsets_from_paths(
            self.custom_toolsets, builtin_toolsets_names
        )
        loaded_custom_toolsets.extend(custom_toolsets)

        custom_toolsets_from_cli = self._load_toolsets_from_paths(
            self.custom_toolsets_from_cli,
            builtin_toolsets_names,
            check_conflict_default=True,
        )
        custom_toolsets_by_name = [toolset.name for toolset in custom_toolsets]
        # custom toolsets from cli as experimental toolset should not override custom toolsets from config
        for custom_toolset_from_cli in custom_toolsets_from_cli:
            if custom_toolset_from_cli in custom_toolsets_by_name:
                raise Exception(
                    f"Toolset {custom_toolset_from_cli.name} passed from cli is already defined in the custom toolsets. "
                    "Please rename the custom toolset or remove it from the custom toolsets configuration."
                )
        loaded_custom_toolsets.extend(custom_toolsets_from_cli)

        return loaded_custom_toolsets

    def add_or_merge_onto_toolsets(
        self,
        new_toolsets: list[Toolset],
        existing_toolsets_by_name: dict[str, Toolset],
    ) -> None:
        """
        Add new or merge toolsets onto existing toolsets.
        """

        for new_toolset in new_toolsets:
            if new_toolset.name in existing_toolsets_by_name.keys():
                existing_toolsets_by_name[new_toolset.name].override_with(new_toolset)
            else:
                existing_toolsets_by_name[new_toolset.name] = new_toolset
