import concurrent.futures
import json
import logging
import os
from typing import Any, List, Optional, TYPE_CHECKING
from pydantic import FilePath, ValidationError
import yaml

from holmes.core.config import config_path_dir
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import (
    Toolset,
    ToolsetSettings,
    ToolsetTag,
    ToolsetType,
    ToolsetCache,
)
from holmes.plugins.toolsets.loaders import load_custom_toolsets_from_files
from holmes.plugins.toolsets import load_builtin_toolsets
from holmes.plugins.toolsets.loaders import load_toolset_from_definition
from holmes.utils.definitions import CUSTOM_TOOLSET_LOCATION, HOLMES_CONFIG_LOCATION_

if TYPE_CHECKING:
    pass

DEFAULT_TOOLSET_STATUS_LOCATION = os.path.join(config_path_dir, "toolsets_status.json")


class ToolsetManager:
    """
    ToolsetManager is responsible for managing toolset locally.
    It can refresh the status of all toolsets and cache the status to a file.
    It also provides methods to get toolsets by name and to get the list of all toolsets.
    """

    def __init__(
        self,
        dal: Optional[SupabaseDal] = None,
        toolset_settings: Optional[
            dict[str, dict[str, Any]]
        ] = None,  # TODO: change to ToolsetSettings
        mcp_servers: Optional[dict[str, dict[str, Any]]] = None,
        custom_toolset_file_paths: Optional[List[FilePath]] = None,
        custom_toolsets_from_cli: Optional[List[FilePath]] = None,
        toolset_status_location: Optional[FilePath] = None,
        global_fast_model: Optional[str] = None,
    ) -> None:
        self._toolset_definitions_by_name: dict[str, Toolset] = dict()
        self._toolset_settings: dict[str, ToolsetSettings] = dict()
        self._dal = dal
        self.use_cache = False

        # TODO: move this to the config loading and make sure it is work the same both in server and cli
        self._toolsets_settings: dict[str, dict] = toolset_settings or {}
        self._mcp_servers: dict[str, dict] = mcp_servers or {}
        if os.path.isfile(HOLMES_CONFIG_LOCATION_):
            with open(HOLMES_CONFIG_LOCATION_, "r") as f:
                holmes_config = yaml.safe_load(f)
                self._toolsets_settings.update(holmes_config.get("toolsets", {}))
                self._mcp_servers.update(holmes_config.get("mcp_servers", {}))

        self._custom_toolset_file_paths = custom_toolset_file_paths or []
        self._global_fast_model = global_fast_model

        #  uses holmes containerCUSTOM_TOOLSET_LOCATION to load custom toolsets
        # TODO: add depection message and load from custom toolset directory if CUSTOM_TOOLSET_LOCATION is not set
        if os.path.isfile(CUSTOM_TOOLSET_LOCATION):
            self._custom_toolset_file_paths.append(FilePath(CUSTOM_TOOLSET_LOCATION))

        self._custom_toolsets_from_cli = custom_toolsets_from_cli
        self._toolset_status_location = toolset_status_location or FilePath(
            DEFAULT_TOOLSET_STATUS_LOCATION
        )

    @property
    def cli_tool_tags(self) -> List[ToolsetTag]:
        """
        Returns the list of toolset tags that are relevant for CLI tools.
        """
        return [ToolsetTag.CORE, ToolsetTag.CLI]

    @property
    def server_tool_tags(self) -> List[ToolsetTag]:
        """
        Returns the list of toolset tags that are relevant for server tools.
        """
        return [ToolsetTag.CORE, ToolsetTag.CLUSTER]

    def _load_toolsets_definitions(
        self, toolset_tags: Optional[List[ToolsetTag]] = None
    ) -> List[Toolset]:
        """
        Loads built-in and custom toolsets.
        """
        if self._toolset_definitions_by_name:
            logging.info(
                "Toolsets definitions already loaded, skipping loading toolsets definitions"
            )
            return list(self._toolset_definitions_by_name.values())

        logging.info("Loading toolsets definitions")
        builtin_toolsets: List[Toolset] = load_builtin_toolsets(self._dal)
        self._toolset_definitions_by_name = {
            toolset.name: toolset for toolset in builtin_toolsets
        }

        custom_toolsets: List[Toolset] = self._load_custom_toolsets()
        for toolset in custom_toolsets:
            if toolset.name in self._toolset_definitions_by_name:
                logging.info(
                    f"Overriding built-in toolset {toolset.name} with custom toolset"
                )
            self._toolset_definitions_by_name[toolset.name] = toolset

        for name, mcp_server_definition in self._mcp_servers.items():
            # TODO: check if mcp server override exists toolset by name? is that valid?
            # TODO: consider to split the config and move it to toolsets_settings
            mcp_server_definition["type"] = ToolsetType.MCP.value
            mcp_server: Optional[Toolset] = load_toolset_from_definition(
                name, mcp_server_definition
            )
            if mcp_server:
                self._toolset_definitions_by_name[name] = mcp_server

        if toolset_tags is not None:
            self._toolset_definitions_by_name = {
                name: toolset
                for name, toolset in self._toolset_definitions_by_name.items()
                if any(tag in toolset_tags for tag in toolset.tags)
            }

        self._inject_fast_model_into_transformers()
        return list(self._toolset_definitions_by_name.values())

    def _load_custom_toolsets(self) -> List[Toolset]:
        if not self._custom_toolset_file_paths and not self._custom_toolsets_from_cli:
            logging.debug(
                "No custom toolsets configured, skipping loading custom toolsets"
            )
            return []

        loaded_custom_toolsets: List[Toolset] = []
        custom_toolsets = load_custom_toolsets_from_files(
            self._custom_toolset_file_paths or []
        )
        # TODO: what about custom toolsets from CLI?
        loaded_custom_toolsets.extend(custom_toolsets)
        return loaded_custom_toolsets

    def _load_toolset_settings(
        self, enable_all_toolsets: bool = False
    ) -> dict[str, ToolsetSettings]:
        if self._toolset_settings:
            logging.info(
                "Toolset settings already loaded, skipping loading toolset settings"
            )
            return self._toolset_settings

        for toolset_name, toolset_settings in self._toolsets_settings.items():
            if toolset_name not in self._toolset_definitions_by_name:
                # TODO: think about the ux we want here.
                logging.error(
                    f"Toolset {toolset_name} is not defined in the toolset definitions"
                )
                continue

            try:
                toolset_settings_obj = ToolsetSettings.model_validate(toolset_settings)
            except Exception as e:
                logging.error(
                    f"Failed to validate toolset settings for {toolset_name}: {e}"
                )
                continue

            self._toolset_settings[toolset_name] = toolset_settings_obj

        for toolset_name, toolset in self._toolset_definitions_by_name.items():
            if toolset_name in self._toolset_settings:
                # TODO if setting provided should we override enable by is_default?
                continue

            should_be_enabled = enable_all_toolsets or toolset.is_default
            self._toolset_settings[toolset_name] = ToolsetSettings(
                enabled=should_be_enabled
            )

        return self._toolset_settings

    def _load_toolset_status_from_cache(self) -> ToolsetCache:
        if not os.path.exists(self._toolset_status_location):
            logging.info(
                "Toolset status cache file not found, creating empty toolset cache"
            )
            return ToolsetCache(toolsets={})

        try:
            with open(self._toolset_status_location, "r") as f:
                toolset_cache = ToolsetCache.model_validate_json(f.read())
                return toolset_cache
        except ValidationError as e:
            logging.info(
                f"Toolset status cache file is invalid, creating empty toolset cache: {e}"
            )
            return ToolsetCache(toolsets={})
        except Exception as e:
            logging.error(f"Failed to load toolset status from cache: {e}")
            return ToolsetCache(toolsets={})

    def _save_toolset_status_to_cache(self, toolsets: List[Toolset]) -> None:
        toolset_cache = ToolsetCache.from_toolsets(toolsets)
        with open(self._toolset_status_location, "w+") as f:
            json.dump(toolset_cache, f, indent=2)

    def _list_all_toolsets(
        self,
        initialize_toolsets=True,
        enable_all_toolsets=False,
        toolset_tags: Optional[List[ToolsetTag]] = None,
        refresh_cache: bool = False,
    ) -> List[Toolset]:
        """
        List all built-in and custom toolsets.

        The method loads toolsets in this order, with later sources overriding earlier ones:
        1. Built-in toolsets
        2. Toolsets defined in self.toolsets can override both built-in and add new custom toolsets
        3. custom toolset from config can override both built-in and add new custom toolsets # for backward compatibility
        """
        self._load_toolsets_definitions(toolset_tags=toolset_tags)
        if not initialize_toolsets:
            return list(self._toolset_definitions_by_name.values())

        enabled_toolsets = self.initilize_toolsets(
            enable_all_toolsets, refresh_cache=refresh_cache
        )
        return enabled_toolsets

    def initilize_toolsets(
        self,
        enable_all_toolsets: bool = False,
        toolset_tags: Optional[List[ToolsetTag]] = None,
        refresh_cache: bool = False,
    ) -> List[Toolset]:
        self._load_toolsets_definitions(toolset_tags=toolset_tags)

        toolset_settings = self._load_toolset_settings(enable_all_toolsets)

        if self.use_cache and not refresh_cache:
            toolset_cache = self._load_toolset_status_from_cache()
        else:
            toolset_cache = ToolsetCache(toolsets={})

        enabled_toolsets: List[Toolset] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for toolset in self._toolset_definitions_by_name.values():
                toolset_cache_entry = toolset_cache.get(toolset.name)
                futures.append(
                    executor.submit(
                        toolset.init_toolset,
                        toolset_settings[toolset.name],
                        toolset_cache_entry,
                    )
                )

            for future in concurrent.futures.as_completed(futures):
                toolset = future.result()
                if toolset.enabled:
                    enabled_toolsets.append(toolset)

        if self.use_cache:
            self._save_toolset_status_to_cache(enabled_toolsets)

        return enabled_toolsets

    def list_console_toolsets(self, refresh_status: bool = False) -> List[Toolset]:
        """
        List all enabled toolsets that cli tools can use.

        listing console toolset does not refresh toolset status by default, and expects the status to be
        refreshed specifically and cached locally.
        """
        self.use_cache = True
        toolsets_with_status = self._list_all_toolsets(
            refresh_cache=refresh_status,
            enable_all_toolsets=True,
            toolset_tags=self.cli_tool_tags,
        )
        return toolsets_with_status

    # TODO(mainred): cache and refresh periodically toolset status for server if necessary
    def list_server_toolsets(
        self, dal: Optional[SupabaseDal] = None, refresh_status=True
    ) -> List[Toolset]:
        """
        List all toolsets that are enabled and have the server tool tags.

        server will sync the status of toolsets to DB during startup instead of local cache.
        Refreshing the status by default for server to keep the toolsets up-to-date instead of relying on local cache.
        """
        toolsets_with_status = self._list_all_toolsets(
            initialize_toolsets=True,
            enable_all_toolsets=False,
            toolset_tags=self.server_tool_tags,
        )
        return toolsets_with_status

    def _inject_fast_model_into_transformers(self) -> None:
        """
        Inject global fast_model setting into all llm_summarize transformers that don't already have fast_model.
        This ensures --fast-model reaches all tools regardless of toolset-level transformer configuration.

        IMPORTANT: This also forces recreation of transformer instances since they may already be created.
        """
        import logging
        from holmes.core.transformers import registry

        logger = logging.getLogger(__name__)

        logger.debug(
            f"Starting fast_model injection. global_fast_model={self._global_fast_model}"
        )

        if not self._global_fast_model:
            logger.debug("No global_fast_model configured, skipping injection")
            return

        injected_count = 0
        toolset_count = 0

        for toolset in self._toolset_definitions_by_name.values():
            toolset_count += 1
            toolset_injected = 0
            logger.debug(
                f"Processing toolset '{toolset.name}', has toolset transformers: {toolset.transformers is not None}"
            )

            # Inject into toolset-level transformers
            if toolset.transformers:
                logger.debug(
                    f"Toolset '{toolset.name}' has {len(toolset.transformers)} toolset-level transformers"
                )
                for transformer in toolset.transformers:
                    logger.debug(
                        f"  Toolset transformer: name='{transformer.name}', config keys={list(transformer.config.keys())}"
                    )
                    if (
                        transformer.name == "llm_summarize"
                        and "fast_model" not in transformer.config
                    ):
                        transformer.config["global_fast_model"] = (
                            self._global_fast_model
                        )
                        injected_count += 1
                        toolset_injected += 1
                        logger.info(
                            f"  ✓ Injected global_fast_model into toolset '{toolset.name}' transformer"
                        )
                    elif transformer.name == "llm_summarize":
                        logger.debug(
                            f"  - Toolset transformer already has fast_model: {transformer.config.get('fast_model')}"
                        )
            else:
                logger.debug(
                    f"Toolset '{toolset.name}' has no toolset-level transformers"
                )

            # Inject into tool-level transformers
            if hasattr(toolset, "tools") and toolset.tools:
                logger.debug(f"Toolset '{toolset.name}' has {len(toolset.tools)} tools")
                for tool in toolset.tools:
                    logger.debug(
                        f"  Processing tool '{tool.name}', has transformers: {tool.transformers is not None}"
                    )
                    if tool.transformers:
                        logger.debug(
                            f"    Tool '{tool.name}' has {len(tool.transformers)} transformers"
                        )
                        tool_updated = False
                        for transformer in tool.transformers:
                            logger.debug(
                                f"      Tool transformer: name='{transformer.name}', config keys={list(transformer.config.keys())}"
                            )
                            if (
                                transformer.name == "llm_summarize"
                                and "fast_model" not in transformer.config
                            ):
                                transformer.config["global_fast_model"] = (
                                    self._global_fast_model
                                )
                                injected_count += 1
                                toolset_injected += 1
                                tool_updated = True
                                logger.info(
                                    f"      ✓ Injected global_fast_model into tool '{tool.name}' transformer"
                                )
                            elif transformer.name == "llm_summarize":
                                logger.debug(
                                    f"      - Tool transformer already has fast_model: {transformer.config.get('fast_model')}"
                                )

                        # CRITICAL: Force recreation of transformer instances if we updated the config
                        if tool_updated:
                            logger.info(
                                f"      🔄 Recreating transformer instances for tool '{tool.name}' after injection"
                            )
                            if tool.transformers:
                                tool._transformer_instances = []
                                for transformer in tool.transformers:
                                    if not transformer:
                                        continue
                                    try:
                                        # Create transformer instance with updated config
                                        transformer_instance = (
                                            registry.create_transformer(
                                                transformer.name, transformer.config
                                            )
                                        )
                                        tool._transformer_instances.append(
                                            transformer_instance
                                        )
                                        logger.debug(
                                            f"        Recreated transformer '{transformer.name}' for tool '{tool.name}' with config: {transformer.config}"
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            f"        Failed to recreate transformer '{transformer.name}' for tool '{tool.name}': {e}"
                                        )
                                        continue
                    else:
                        logger.debug(f"    Tool '{tool.name}' has no transformers")
            else:
                logger.debug(f"Toolset '{toolset.name}' has no tools")

            if toolset_injected > 0:
                logger.info(
                    f"Toolset '{toolset.name}': injected into {toolset_injected} transformers"
                )

        logger.info(
            f"Fast_model injection complete: {injected_count} transformers updated across {toolset_count} toolsets"
        )
