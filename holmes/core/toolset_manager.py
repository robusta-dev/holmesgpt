import copy
import logging
import os
from typing import Any, List, Optional, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict

if TYPE_CHECKING:
    from holmes.config import Config

import yaml

from holmes.core.config import config_path_dir
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.toolset_cache import ToolsetStatusCache
from holmes.core.tools import Toolset, ToolsetStatusEnum, ToolsetTag, ToolsetType
from holmes.plugins.toolsets import (
    load_builtin_toolsets,
    load_toolsets_from_config,
    load_mcp_servers,
    THIS_DIR as BUILTIN_TOOLSETS_DIR,
)
from holmes.utils.definitions import CUSTOM_TOOLSET_DIR
from holmes.utils.dict_utils import deep_merge

if TYPE_CHECKING:
    pass

DEFAULT_TOOLSET_STATUS_LOCATION = os.path.join(config_path_dir, "toolsets_status.json")

CLI_TOOL_TAGS = [ToolsetTag.CORE, ToolsetTag.CLI]
SERVER_TOOL_TAGS = [ToolsetTag.CORE, ToolsetTag.CLUSTER]


def cache_exists() -> bool:
    """Check if the toolset cache file exists."""
    return os.path.exists(DEFAULT_TOOLSET_STATUS_LOCATION)


ALLOWED_CONFIG_FIELDS = {"enabled", "config", "additional_instructions"}


class ToolsetRegistry:
    """Registry that handles toolset loading, merging, and filtering"""

    def __init__(self):
        self.toolsets: Dict[str, Toolset] = {}

    def add(self, toolsets: List[Toolset]):
        """Add or replace toolsets"""
        for t in toolsets:
            self.toolsets[t.name] = t

    def update_from_config(self, config: Dict[str, Dict]) -> set:
        """Update builtin toolsets from configuration dictionary - strict validation
        Returns: Set of successfully configured toolset names
        """
        configured = set()
        for name, toolset_config in config.items():
            if name in self.toolsets:
                # Configure existing builtin toolset
                try:
                    self._configure_builtin(name, toolset_config)
                    configured.add(name)  # Only add if successful
                except ValueError as e:
                    logging.error(f"Failed to configure toolset '{name}': {e}")
                    # Continue processing other toolsets
            else:
                # Attempting to add new toolset via config - not allowed
                logging.error(
                    f"Cannot add new toolset '{name}' via 'toolsets' config.\n"
                    f"This functionality has been deprecated to prevent accidental toolset overrides.\n"
                    f"To add custom toolsets, place YAML files in ~/.holmes/custom_toolsets/\n"
                    f"or use the -t flag for temporary toolsets.\n"
                    f"The 'toolsets' section is now only for configuring existing builtin toolsets."
                )
                # Continue processing other toolsets instead of failing completely
        return configured

    def _configure_builtin(self, name: str, config: Dict):
        """Apply limited configuration to a builtin toolset"""
        # Check for invalid fields
        unknown_fields = set(config.keys()) - ALLOWED_CONFIG_FIELDS
        if unknown_fields:
            raise ValueError(
                f"Invalid fields {unknown_fields} for builtin toolset '{name}'.\n"
                f"Only {ALLOWED_CONFIG_FIELDS} can be configured for builtin toolsets.\n"
                f"To extend functionality, create a new toolset with a unique name in a custom YAML file."
            )

        # Apply configuration using the method that preserves defaults
        # This properly handles merging for dict fields like 'config'
        toolset = self.toolsets[name]

        # Simple approach: apply each field
        # For 'config' field specifically, use deep merge if it's a dict
        if "enabled" in config:
            toolset.enabled = config["enabled"]

        if "config" in config and config["config"] is not None:
            if toolset.config is None:
                toolset.config = config["config"]
            elif isinstance(toolset.config, dict) and isinstance(
                config["config"], dict
            ):
                # Deep merge: user config overrides default config at each level
                toolset.config = deep_merge(toolset.config, config["config"])
            else:
                # Non-dict or incompatible types, replace entirely
                toolset.config = config["config"]

        if "additional_instructions" in config:
            toolset.additional_instructions = config["additional_instructions"]

    def load_custom_toolsets_from_yaml(self, file_path: Path) -> set:
        """Load custom toolsets from a YAML file - no overrides allowed"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"toolset file {file_path} does not exist")

        try:
            with open(file_path, "r") as f:
                parsed_yaml = yaml.safe_load(f)
            if not parsed_yaml:
                parsed_yaml = {}
        except Exception as e:
            raise ValueError(
                f"Failed to load toolsets from {file_path}, error: {e}"
            ) from e

        toolsets_config = parsed_yaml.get("toolsets", {})
        mcp_config = parsed_yaml.get("mcp_servers", {})

        # Create copies to avoid mutating original
        mcp_config = copy.deepcopy(mcp_config) if mcp_config else {}
        toolsets_config = copy.deepcopy(toolsets_config) if toolsets_config else {}

        # Add path info to toolset configs
        for toolset_config in toolsets_config.values():
            toolset_config["path"] = str(file_path)

        # Check if we have any configs
        all_names = set(toolsets_config.keys()) | set(mcp_config.keys())
        if not all_names:
            raise ValueError(
                f"No 'toolsets' or 'mcp_servers' key found in: {file_path}"
            )

        # Check for conflicts with builtin toolsets
        builtin_names = set(self.toolsets.keys())
        conflicts = all_names & builtin_names

        if conflicts:
            raise ValueError(
                f"Custom toolsets {conflicts} from '{file_path}' conflict with builtin toolsets.\n"
                f"Custom toolsets must have unique names.\n"
                f"To configure builtin toolsets, use the 'toolsets' section in config.yaml."
            )

        # Load regular custom toolsets
        if toolsets_config:
            new_toolsets = load_toolsets_from_config(toolsets_config)
            self.add(new_toolsets)

        # Load MCP servers separately with proper URL handling
        if mcp_config:
            new_mcp_servers = load_mcp_servers(mcp_config)
            self.add(new_mcp_servers)

        return all_names

    def get_by_tags(self, tags: List[ToolsetTag]) -> List[Toolset]:
        """Filter toolsets by tags"""
        return [t for t in self.toolsets.values() if any(tag in tags for tag in t.tags)]


class PrerequisiteChecker:
    def check_all(
        self,
        toolsets: List[Toolset],
        progress_callback: Optional[Callable] = None,
        quiet: bool = False,
    ) -> List[Toolset]:
        """Check prerequisites for toolsets
        Returns NEW toolset objects with updated statuses"""
        result = []

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {}
            for t in toolsets:
                future = executor.submit(t.check_prerequisites, quiet=quiet)
                futures[future] = t

            completed = 0
            total = len(futures)
            active_checks = [t.name for t in toolsets]

            for future in as_completed(futures):
                completed += 1
                toolset = futures[future]
                active_checks.remove(toolset.name)

                # Create new toolset with updated status (don't modify input)
                updated = copy.copy(toolset)
                try:
                    future.result()  # This runs check_prerequisites which modifies the toolset
                    # Copy the status and error from the modified toolset
                    updated.status = toolset.status
                    updated.error = toolset.error
                except Exception as e:
                    updated.status = ToolsetStatusEnum.DISABLED
                    updated.error = str(e)

                result.append(updated)

                if progress_callback is not None:
                    progress_callback(completed, total, active_checks)

        return result


class ToolsetManager:
    def __init__(
        self,
        tags: List[ToolsetTag],
        config: Optional[dict[str, dict[str, Any]]] = None,
        dal: Optional[SupabaseDal] = None,
        custom_toolset_paths: Optional[List[Path]] = None,
        cache_path: Optional[Path] = None,
        default_enabled: bool = False,
        suppress_logging: bool = False,
    ):
        """
        Args:
            tags: Toolset tags to filter (CLI_TOOL_TAGS or SERVER_TOOL_TAGS)
            config: Combined toolsets and mcp_servers configuration
            dal: Database access layer for server toolsets
            custom_toolset_paths: Paths to custom toolset YAML files
            cache_path: Path for cache file (defaults to DEFAULT_TOOLSET_STATUS_LOCATION)
            default_enabled: Whether to enable all toolsets by default (assuming they pass prequisites check)
            suppress_logging: Whether to suppress logging output
        """
        cache_path = cache_path or Path(DEFAULT_TOOLSET_STATUS_LOCATION)

        self.tags = tags
        self.config = config or {}
        self.dal = dal
        self.custom_paths = []
        self.default_enabled = default_enabled
        self.suppress_logging = suppress_logging

        # Load from directory (all .yaml files)
        if os.path.isdir(CUSTOM_TOOLSET_DIR):
            for yaml_file in Path(CUSTOM_TOOLSET_DIR).glob("*.yaml"):
                self.custom_paths.append(yaml_file)
                if not self.suppress_logging:
                    logging.debug(f"Found custom toolset file: {yaml_file}")

        # Add CLI-provided paths (highest priority)
        if custom_toolset_paths:
            self.custom_paths.extend(custom_toolset_paths)

        self.status_cache = ToolsetStatusCache(cache_path)
        self.checker = PrerequisiteChecker()
        self.registry = ToolsetRegistry()

        # Load all definitions once during initialization
        self._load_definitions()

    def set_suppress_logging(self, suppress: bool) -> None:
        """Temporarily control logging output"""
        self.suppress_logging = suppress

    def _normalize_config(self, config: Dict) -> Dict[str, Dict]:
        """Normalize various config formats into unified structure

        Handles both old-style (single dict) and new-style (split toolsets/mcp_servers)
        configurations, returning a unified dictionary of all toolset configurations.

        Note: This method is kept for backward compatibility but may not be used
        since we now handle toolsets and mcp_servers separately.
        """
        result = {}

        if "toolsets" in config or "mcp_servers" in config:
            # New style - split config
            result.update(config.get("toolsets", {}))
            result.update(config.get("mcp_servers", {}))
        else:
            # Old style - all in one dict
            result = config

        return result

    def _load_definitions(self):
        """Load all toolset definitions"""
        # Load built-in toolsets
        self.registry.add(load_builtin_toolsets(self.dal))

        # Apply config overrides and load MCP servers
        configured_names = set()
        if self.config:
            # Handle toolsets config (only for configuring builtins)
            if "toolsets" in self.config:
                successfully_configured = self.registry.update_from_config(
                    self.config["toolsets"]
                )
                configured_names.update(successfully_configured)

            # Handle MCP servers (allowed to add new ones)
            if "mcp_servers" in self.config:
                new_mcp_servers = load_mcp_servers(self.config["mcp_servers"])
                self.registry.add(new_mcp_servers)
                configured_names.update(self.config["mcp_servers"].keys())

        # Load custom toolsets from files
        for path in self.custom_paths:
            names = self.registry.load_custom_toolsets_from_yaml(path)
            configured_names.update(names)

        # Apply default_enabled to non-configured toolsets
        if self.default_enabled:
            for toolset in self.registry.toolsets.values():
                if toolset.name not in configured_names:
                    toolset.enabled = True

    def load(
        self,
        use_cache: bool = True,
        progress_callback: Optional[Callable] = None,
        include_disabled: bool = False,
    ) -> List[Toolset]:
        """Load toolsets - either from cache or fresh

        Args:
            use_cache: Whether to use cached status if available and fresh
            progress_callback: Callback for prerequisite check progress
            include_disabled: Whether to include disabled toolsets in results

        Returns:
            List of toolsets filtered by tags and status
        """
        relevant = self.registry.get_by_tags(self.tags)

        # Filter out explicitly disabled (unless diagnostics mode)
        if not include_disabled:
            relevant = [t for t in relevant if t.enabled]

        # Calculate content hash for cache validation
        content_hash = self.status_cache.get_content_hash(
            self.config, self.custom_paths, Path(BUILTIN_TOOLSETS_DIR)
        )

        # Either use cache or check prerequisites
        if use_cache and not self.status_cache.is_stale_for_content(content_hash):
            cached_data = self.status_cache.read_toolsets()
            checked = self._apply_cached_data(relevant, cached_data)
        else:
            checked = self.checker.check_all(
                relevant, progress_callback, quiet=self.suppress_logging
            )
            self.status_cache.write(checked, content_hash)
            if not self.suppress_logging:
                logging.info(
                    f"Toolset statuses are cached to {self.status_cache.cache_path}"
                )

        # Return based on caller needs
        if include_disabled:
            return checked
        else:
            return [t for t in checked if t.status == ToolsetStatusEnum.ENABLED]

    def _apply_cached_data(
        self, toolsets: List[Toolset], cached_data: Dict[str, Dict]
    ) -> List[Toolset]:
        """Apply cached data to toolsets"""
        result = []
        for t in toolsets:
            updated = copy.copy(t)
            if t.name in cached_data:
                data = cached_data[t.name]
                updated.status = ToolsetStatusEnum(data.get("status", "disabled"))
                updated.error = data.get("error")
                # Don't override enabled - it comes from config/defaults
                # enabled determines if we should check prerequisites
                # status determines if prerequisites passed
                if data.get("type"):
                    updated.type = ToolsetType(data["type"])
                if data.get("path"):
                    updated.path = Path(data["path"])
            else:
                # No cache data for this toolset
                updated.status = ToolsetStatusEnum.DISABLED
                updated.error = "No cache data available"
            result.append(updated)
        return result

    @classmethod
    def _create_from_config(
        cls,
        config: Optional["Config"],
        tags: List[ToolsetTag],
        dal: Optional[SupabaseDal] = None,
        default_enabled: bool = False,
    ):
        """Common factory method logic"""
        # Build combined config dict if needed
        toolset_config = {}
        if config and config.toolsets:
            toolset_config["toolsets"] = config.toolsets
        if config and config.mcp_servers:
            toolset_config["mcp_servers"] = config.mcp_servers

        # Check for deprecated custom_toolset_paths
        custom_paths = None
        if config and config.custom_toolset_paths:
            logging.warning(
                "The 'custom_toolset_paths' config field is deprecated.\n"
                f"Please move your custom toolset files to: {CUSTOM_TOOLSET_DIR}/\n"
                "Or use the -t flag for temporary toolsets."
            )
            # Still use them for backwards compatibility
            custom_paths = [Path(p) for p in config.custom_toolset_paths]

        return cls(
            tags=tags,
            config=toolset_config or None,
            dal=dal,
            custom_toolset_paths=custom_paths,
            default_enabled=default_enabled,
            suppress_logging=False,
        )

    @classmethod
    def for_cli(cls, config: Optional["Config"]):
        """Create CLI-configured manager from Config object"""
        return cls._create_from_config(config, CLI_TOOL_TAGS, default_enabled=True)

    @classmethod
    def for_server(cls, config: "Config", dal: SupabaseDal):
        """Create server-configured manager from Config object"""
        return cls._create_from_config(
            config, SERVER_TOOL_TAGS, dal=dal, default_enabled=False
        )
