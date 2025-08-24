"""Test toolset cache invalidation improvements."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


from holmes.core.toolset_cache import ToolsetStatusCache
from holmes.core.tools import Toolset, ToolsetStatusEnum


def test_cache_hash_includes_version():
    """Test that Holmes version is included in cache hash."""
    cache = ToolsetStatusCache(Path("/tmp/test.json"))

    with patch("holmes.core.toolset_cache.get_version", return_value="v1.0.0"):
        hash1 = cache.get_content_hash({}, [])

    with patch("holmes.core.toolset_cache.get_version", return_value="v2.0.0"):
        hash2 = cache.get_content_hash({}, [])

    assert hash1 != hash2, "Different versions should produce different hashes"


def test_cache_hash_includes_builtin_toolsets():
    """Test that builtin toolset file changes are detected."""
    cache = ToolsetStatusCache(Path("/tmp/test.json"))

    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir)

        # No files initially
        hash1 = cache.get_content_hash({}, [], builtin_dir)

        # Add a toolset file
        toolset_file = builtin_dir / "test.yaml"
        toolset_file.write_text("name: test\ntools: []")
        hash2 = cache.get_content_hash({}, [], builtin_dir)

        assert hash1 != hash2, "Adding builtin toolset should change hash"

        # Modify the file
        time.sleep(0.01)  # Ensure different mtime
        toolset_file.write_text("name: test\ntools: []\ndescription: modified")
        hash3 = cache.get_content_hash({}, [], builtin_dir)

        assert hash2 != hash3, "Modifying builtin toolset should change hash"


def test_cache_hash_includes_subdirectory_toolsets():
    """Test that toolsets in subdirectories are included in hash."""
    cache = ToolsetStatusCache(Path("/tmp/test.json"))

    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir)

        # Create a subdirectory with toolset
        subdir = builtin_dir / "kubernetes"
        subdir.mkdir()

        hash1 = cache.get_content_hash({}, [], builtin_dir)

        # Add toolset in subdirectory
        (subdir / "core.yaml").write_text("name: k8s-core")
        hash2 = cache.get_content_hash({}, [], builtin_dir)

        assert hash1 != hash2, "Toolsets in subdirectories should affect hash"


def test_cache_hash_with_config_changes():
    """Test that config changes affect the hash."""
    cache = ToolsetStatusCache(Path("/tmp/test.json"))

    config1 = {"toolsets": {"kubernetes/core": {"enabled": True}}}
    config2 = {"toolsets": {"kubernetes/core": {"enabled": False}}}

    hash1 = cache.get_content_hash(config1, [])
    hash2 = cache.get_content_hash(config2, [])

    assert hash1 != hash2, "Different configs should produce different hashes"


def test_cache_hash_with_custom_toolsets():
    """Test that custom toolset files are included in hash."""
    cache = ToolsetStatusCache(Path("/tmp/test.json"))

    with tempfile.TemporaryDirectory() as tmpdir:
        custom1 = Path(tmpdir) / "custom1.yaml"
        custom2 = Path(tmpdir) / "custom2.yaml"

        # No custom files
        hash1 = cache.get_content_hash({}, [])

        # One custom file
        custom1.write_text("toolsets:\n  test1:\n    name: test1")
        hash2 = cache.get_content_hash({}, [custom1])
        assert hash1 != hash2

        # Two custom files
        custom2.write_text("toolsets:\n  test2:\n    name: test2")
        hash3 = cache.get_content_hash({}, [custom1, custom2])
        assert hash2 != hash3

        # Modified custom file
        time.sleep(0.01)
        custom1.write_text(
            "toolsets:\n  test1:\n    name: test1\n    description: modified"
        )
        hash4 = cache.get_content_hash({}, [custom1, custom2])
        assert hash3 != hash4


def test_cache_staleness_check():
    """Test cache staleness detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = ToolsetStatusCache(cache_path)

        # Non-existent cache is stale
        assert cache.is_stale_for_content("any_hash") is True

        # Write a cache
        mock_toolset = MagicMock(spec=Toolset)
        mock_toolset.name = "test"
        mock_toolset.status = ToolsetStatusEnum.ENABLED
        mock_toolset.error = None
        mock_toolset.enabled = True
        mock_toolset.type = None
        mock_toolset.path = None
        toolsets = [mock_toolset]
        cache.write(toolsets, "hash123")

        # Same hash = not stale
        assert cache.is_stale_for_content("hash123", max_age_seconds=3600) is False

        # Different hash = stale
        assert cache.is_stale_for_content("different_hash") is True

        # Old cache = stale
        assert cache.is_stale_for_content("hash123", max_age_seconds=0) is True


def test_cache_with_unknown_status():
    """Test that cache with unknown status is considered stale."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = ToolsetStatusCache(cache_path)

        # Write cache with unknown status
        cache_data = {
            "_content_hash": "test_hash",
            "_timestamp": time.time(),
            "toolsets": {
                "test1": {"status": "enabled", "error": None, "enabled": True},
                "test2": {"status": "unknown", "error": None, "enabled": True},
            },
        }

        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        # Cache with unknown status should be stale
        assert cache.is_stale_for_content("test_hash") is True
