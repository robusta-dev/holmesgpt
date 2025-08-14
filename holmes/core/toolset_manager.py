import copy
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from holmes.config import Config

from benedict import benedict

from holmes.core.config import config_path_dir
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import Toolset, ToolsetStatusEnum, ToolsetTag, ToolsetType
from holmes.plugins.toolsets import load_builtin_toolsets, load_toolsets_from_config
from holmes.utils.definitions import CUSTOM_TOOLSET_LOCATION

DEFAULT_TOOLSET_STATUS_LOCATION = os.path.join(config_path_dir, "toolsets_status.json")

CLI_TOOL_TAGS = [ToolsetTag.CORE, ToolsetTag.CLI]
SERVER_TOOL_TAGS = [ToolsetTag.CORE, ToolsetTag.CLUSTER]


def cache_exists() -> bool:
    """Check if the toolset cache file exists."""
    return os.path.exists(DEFAULT_TOOLSET_STATUS_LOCATION)


class ToolsetCache:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path

    def _read(self) -> Dict:
        """Read entire cache including metadata"""
        if not self.cache_path.exists():
            return {}
        try:
            with open(self.cache_path) as f:
                data = json.load(f)
                # Check if it's old format (array or plain dict without metadata)
                if (
                    isinstance(data, list)
                    or not isinstance(data, dict)
                    or "_content_hash" not in data
                ):
                    logging.info("Old cache format detected, will refresh")
                    return {}
                return data
        except (json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Corrupted cache file, returning empty: {e}")
            return {}

    def read_toolsets(self) -> Dict[str, Dict]:
        """Read just the toolset data from cache"""
        data = self._read()
        return data.get("toolsets", {})

    def write(self, toolsets: List[Toolset], content_hash: str):
        """Write cache with content hash"""
        cache_data = {
            "_content_hash": content_hash,
            "_timestamp": time.time(),
            "toolsets": {
                t.name: {
                    "status": t.status.value if t.status else "unknown",
                    "error": t.error,
                    "enabled": t.enabled,
                    "type": t.type.value if t.type else None,
                    "path": str(t.path) if t.path else None,
                }
                for t in toolsets
            },
        }

        # Ensure directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)

    def get_content_hash(self, config: Dict, custom_paths: List[Path]) -> str:
        """Calculate hash of all file contents that contribute to toolsets"""
        content_parts = []

        # Include config in hash (for overrides)
        if config:
            content_parts.append(json.dumps(config, sort_keys=True))

        # Include custom file contents
        for path in custom_paths:
            if path.exists():
                try:
                    content_parts.append(f"{path}:{path.read_text()}")
                except (OSError, IOError):
                    # If we can't read, include path only
                    content_parts.append(str(path))

        # Hash all content together
        combined = "\n".join(content_parts)
        return hashlib.md5(combined.encode()).hexdigest()

    def is_stale_for_content(
        self, content_hash: str, max_age_seconds: int = 3600
    ) -> bool:
        """Check if cache is stale based on content hash"""
        if not self.cache_path.exists():
            return True

        data = self._read()
        if not data:
            return True

        # Different content = stale
        if data.get("_content_hash") != content_hash:
            return True

        # Too old = stale (for non-file toolsets)
        age = time.time() - data.get("_timestamp", 0)
        if age > max_age_seconds:
            return True

        # Check if any toolset has invalid/unknown status
        toolsets = data.get("toolsets", {})
        for name, toolset_data in toolsets.items():
            if toolset_data.get("status") == "unknown":
                return True

        return False


class ToolsetRegistry:
    """Registry that handles toolset loading, merging, and filtering"""

    def __init__(self):
        self.toolsets: Dict[str, Toolset] = {}

    def add(self, toolsets: List[Toolset]):
        """Add or replace toolsets"""
        for t in toolsets:
            self.toolsets[t.name] = t

    def update_from_config(self, config: Dict[str, Dict]):
        """Update toolsets from configuration dictionary"""
        for name, toolset_config in config.items():
            if name in self.toolsets:
                # Override existing toolset
                override_toolsets = load_toolsets_from_config(
                    {name: toolset_config}, strict_check=False
                )
                if not override_toolsets:
                    logging.warning(
                        f"Skipping invalid override config for toolset '{name}'"
                    )
                    continue
                self.toolsets[name].override_with(override_toolsets[0])
            else:
                # Create new toolset
                new_toolsets = load_toolsets_from_config(
                    {name: toolset_config}, strict_check=True
                )
                if not new_toolsets:
                    logging.warning(f"Skipping invalid config for new toolset '{name}'")
                    continue
                self.toolsets[name] = new_toolsets[0]

    def load_from_yaml_file(self, file_path: Path) -> set:
        """Load toolsets from a YAML file and return the names that were configured"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"toolset file {file_path} does not exist")

        try:
            parsed_yaml = benedict(str(file_path))
        except Exception as e:
            raise ValueError(
                f"Failed to load toolsets from {file_path}, error: {e}"
            ) from e

        toolsets_config = parsed_yaml.get("toolsets", {})
        mcp_config = parsed_yaml.get("mcp_servers", {})

        # Mark MCP servers with their type
        for server_config in mcp_config.values():
            server_config["type"] = ToolsetType.MCP.value

        # Add path info to toolset configs
        for toolset_config in toolsets_config.values():
            toolset_config["path"] = str(file_path)

        # Merge both configs
        toolsets_config.update(mcp_config)

        if not toolsets_config:
            raise ValueError(
                f"No 'toolsets' or 'mcp_servers' key found in: {file_path}"
            )

        # Split into builtin overrides and new custom toolsets
        builtin_names = set(self.toolsets.keys())
        builtin_overrides = {
            k: v for k, v in toolsets_config.items() if k in builtin_names
        }
        custom_toolsets = {
            k: v for k, v in toolsets_config.items() if k not in builtin_names
        }

        # Apply builtin overrides (partial updates allowed)
        if builtin_overrides:
            self.update_from_config(builtin_overrides)

        # Add new custom toolsets (all fields required)
        if custom_toolsets:
            new_toolsets = load_toolsets_from_config(custom_toolsets, strict_check=True)
            self.add(new_toolsets)

        return set(toolsets_config.keys())

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
        self.custom_paths = custom_toolset_paths or []
        self.default_enabled = default_enabled
        self.suppress_logging = suppress_logging

        if os.path.isfile(CUSTOM_TOOLSET_LOCATION):
            self.custom_paths.append(Path(CUSTOM_TOOLSET_LOCATION))

        self.cache = ToolsetCache(cache_path)
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
        """
        result = {}

        if "toolsets" in config or "mcp_servers" in config:
            # New style - split config
            result.update(config.get("toolsets", {}))

            # Add type to MCP servers
            mcp_servers = config.get("mcp_servers", {})
            if mcp_servers:
                # Deep copy to avoid mutating original config
                mcp_config = copy.deepcopy(mcp_servers)
                for server_config in mcp_config.values():
                    server_config["type"] = ToolsetType.MCP.value
                result.update(mcp_config)
        else:
            # Old style - all in one dict
            result = config

        return result

    def _load_definitions(self):
        """Load all toolset definitions"""
        # 1. Load built-in toolsets
        self.registry.add(load_builtin_toolsets(self.dal))

        # 2. Apply config overrides
        configured_names = set()
        if self.config:
            normalized = self._normalize_config(self.config)
            self.registry.update_from_config(normalized)
            configured_names.update(normalized.keys())

        # 3. Load custom toolsets from files
        for path in self.custom_paths:
            names = self.registry.load_from_yaml_file(path)
            configured_names.update(names)

        # 4. Apply default_enabled to non-configured toolsets
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
        content_hash = self.cache.get_content_hash(self.config, self.custom_paths)

        # Either use cache or check prerequisites
        if use_cache and not self.cache.is_stale_for_content(content_hash):
            cached_data = self.cache.read_toolsets()
            checked = self._apply_cached_data(relevant, cached_data)
        else:
            checked = self.checker.check_all(
                relevant, progress_callback, quiet=self.suppress_logging
            )
            self.cache.write(checked, content_hash)
            if not self.suppress_logging:
                logging.info(f"Toolset statuses are cached to {self.cache.cache_path}")

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
                updated.enabled = data.get("enabled", True)
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
        config: "Config",
        tags: List[ToolsetTag],
        dal: Optional[SupabaseDal] = None,
        default_enabled: bool = False,
    ):
        """Common factory method logic"""
        # Build combined config dict if needed
        toolset_config = {}
        if config.toolsets:
            toolset_config["toolsets"] = config.toolsets
        if config.mcp_servers:
            toolset_config["mcp_servers"] = config.mcp_servers

        return cls(
            tags=tags,
            config=toolset_config or None,
            dal=dal,
            custom_toolset_paths=[Path(p) for p in config.custom_toolset_paths]
            if config.custom_toolset_paths
            else None,
            default_enabled=default_enabled,
            suppress_logging=False,
        )

    @classmethod
    def for_cli(cls, config: "Config"):
        """Create CLI-configured manager from Config object"""
        return cls._create_from_config(config, CLI_TOOL_TAGS, default_enabled=True)

    @classmethod
    def for_server(cls, config: "Config", dal: SupabaseDal):
        """Create server-configured manager from Config object"""
        return cls._create_from_config(
            config, SERVER_TOOL_TAGS, dal=dal, default_enabled=False
        )
