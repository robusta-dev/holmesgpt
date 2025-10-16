import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from holmes.core.tools import Toolset
from holmes.version import get_version


class ToolsetStatusCache:
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

    def get_content_hash(
        self,
        config: Dict,
        custom_paths: List[Path],
        builtin_toolsets_dir: Optional[Path] = None,
    ) -> str:
        """Calculate hash of all file contents that contribute to toolsets"""
        content_parts = []

        # Include Holmes version in hash
        version = get_version()
        content_parts.append(f"holmes_version:{version}")

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

        # Include builtin toolset file checksums
        if builtin_toolsets_dir and builtin_toolsets_dir.exists():
            try:
                # Get all YAML files in builtin toolsets directory
                yaml_files = sorted(builtin_toolsets_dir.glob("*.yaml"))
                # Also check for subdirectories with YAML files
                for subdir in sorted(builtin_toolsets_dir.iterdir()):
                    if subdir.is_dir():
                        yaml_files.extend(sorted(subdir.glob("*.yaml")))

                # Add file modification times and sizes (cheaper than full content hash)
                for yaml_file in yaml_files:
                    stat = yaml_file.stat()
                    content_parts.append(
                        f"builtin:{yaml_file.name}:{stat.st_mtime}:{stat.st_size}"
                    )
            except (OSError, IOError) as e:
                logging.debug(f"Could not check builtin toolsets for cache: {e}")

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
