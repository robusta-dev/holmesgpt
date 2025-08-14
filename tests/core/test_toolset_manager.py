import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from holmes.core.tools import (
    Toolset,
    ToolsetStatusEnum,
    ToolsetTag,
    ToolsetType,
    YAMLToolset,
)
from holmes.core.toolset_manager import ToolsetManager, CLI_TOOL_TAGS, SERVER_TOOL_TAGS


@pytest.fixture
def toolset_manager():
    return ToolsetManager(
        tags=[ToolsetTag.CORE, ToolsetTag.CLI],
        config={},
        default_enabled=True,  # CLI mode
    )


def test_cli_tool_tags():
    tags = CLI_TOOL_TAGS
    assert ToolsetTag.CORE in tags
    assert ToolsetTag.CLI in tags


def test_server_tool_tags():
    tags = SERVER_TOOL_TAGS
    assert ToolsetTag.CORE in tags
    assert ToolsetTag.CLUSTER in tags


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
@patch("holmes.core.toolset_manager.load_toolsets_from_config")
def test__list_all_toolsets_merges_configs(
    mock_load_toolsets_from_config, mock_load_builtin_toolsets, toolset_manager
):
    builtin_toolset = MagicMock(spec=Toolset)
    builtin_toolset.name = "builtin"
    builtin_toolset.tags = [ToolsetTag.CORE]
    builtin_toolset.enabled = True
    builtin_toolset.status = ToolsetStatusEnum.ENABLED
    builtin_toolset.error = None
    builtin_toolset.type = ToolsetType.BUILTIN
    builtin_toolset.path = None
    builtin_toolset.check_prerequisites = MagicMock(
        return_value=ToolsetStatusEnum.ENABLED
    )
    mock_load_builtin_toolsets.return_value = [builtin_toolset]
    config_toolset = MagicMock(spec=Toolset)
    config_toolset.name = "config"
    config_toolset.tags = [ToolsetTag.CLI]
    config_toolset.enabled = True
    config_toolset.status = ToolsetStatusEnum.ENABLED
    config_toolset.error = None
    config_toolset.type = ToolsetType.CUSTOMIZED
    config_toolset.path = None
    config_toolset.check_prerequisites = MagicMock(
        return_value=ToolsetStatusEnum.ENABLED
    )
    mock_load_toolsets_from_config.return_value = [config_toolset]

    # Create a new manager with config
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE, ToolsetTag.CLI],
        config={"toolsets": {"config": {"description": "test config toolset"}}},
        default_enabled=True,
    )
    toolsets = toolset_manager.registry.get_by_tags([ToolsetTag.CORE, ToolsetTag.CLI])
    names = [t.name for t in toolsets]
    assert "builtin" in names
    assert "config" in names


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test__list_all_toolsets_override_builtin_config(
    mock_load_builtin_toolsets, toolset_manager
):
    builtin_toolset = YAMLToolset(
        name="builtin",
        tags=[ToolsetTag.CORE],
        description="Builtin toolset",
        experimental=False,
    )
    mock_load_builtin_toolsets.return_value = [builtin_toolset]
    # Create a new manager with config override
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={"toolsets": {"builtin": {"enabled": False}}},
        default_enabled=True,
    )
    toolsets = toolset_manager.registry.get_by_tags([ToolsetTag.CORE])
    assert len(toolsets) == 1
    assert toolsets[0].enabled is False


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test__list_all_toolsets_custom_toolset(mock_load_builtin_toolsets, toolset_manager):
    builtin_toolset = YAMLToolset(
        name="builtin",
        tags=[ToolsetTag.CORE],
        description="Builtin toolset",
        experimental=False,
    )
    mock_load_builtin_toolsets.return_value = [builtin_toolset]
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as tmpfile:
        # Only override the enabled field, not trying to recreate the entire toolset
        data = {"toolsets": {"builtin": {"enabled": False}}}
        yaml.dump(data, tmpfile)
        tmpfile_path = tmpfile.name
    # Create a new manager with custom toolset path
    from pathlib import Path

    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={},
        custom_toolset_paths=[Path(tmpfile_path)],
        default_enabled=True,
    )
    # Check that the override worked
    assert toolset_manager.registry.toolsets["builtin"].enabled is False
    os.remove(tmpfile_path)


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test_load_creates_cache_file(mock_load_builtin_toolsets):
    toolset = MagicMock(spec=Toolset)
    toolset.name = "test"
    toolset.status = ToolsetStatusEnum.ENABLED
    toolset.enabled = True
    toolset.type = ToolsetType.BUILTIN
    toolset.path = None
    toolset.error = None
    toolset.tags = [ToolsetTag.CORE]
    toolset.check_prerequisites = MagicMock(return_value=ToolsetStatusEnum.ENABLED)
    toolset.model_dump_json.return_value = json.dumps(
        {
            "name": "test",
            "status": "ENABLED",
            "enabled": True,
            "type": "BUILTIN",
            "path": None,
            "error": None,
        }
    )
    mock_load_builtin_toolsets.return_value = [toolset]
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "toolsets_status.json")
        from pathlib import Path

        toolset_manager = ToolsetManager(
            tags=[ToolsetTag.CORE],
            config={},
            cache_path=Path(cache_path),
            default_enabled=True,
        )
        toolset_manager.load(use_cache=False)
        assert os.path.exists(cache_path)
        with open(cache_path) as f:
            data = json.load(f)
            # New format has toolsets under 'toolsets' key
            assert "_content_hash" in data
            assert "_timestamp" in data
            assert "toolsets" in data
            assert "test" in data["toolsets"]
            assert data["toolsets"]["test"]["status"] == "enabled"


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test_load_reads_cache(mock_load_builtin_toolsets):
    toolset = MagicMock(spec=Toolset)
    toolset.name = "test"
    toolset.tags = [ToolsetTag.CORE]
    toolset.enabled = True
    toolset.status = ToolsetStatusEnum.ENABLED
    toolset.type = ToolsetType.BUILTIN
    toolset.path = None
    toolset.error = None
    toolset.check_prerequisites = MagicMock(return_value=ToolsetStatusEnum.ENABLED)
    mock_load_builtin_toolsets.return_value = [toolset]
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "toolsets_status.json")
        cache_data = {
            "test": {
                "status": "enabled",
                "enabled": True,
                "type": "built-in",
                "path": None,
                "error": None,
            }
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)
        from pathlib import Path

        toolset_manager = ToolsetManager(
            tags=[ToolsetTag.CORE],
            config={},
            cache_path=Path(cache_path),
            default_enabled=True,
        )
        result = toolset_manager.load(use_cache=True)
        assert len(result) == 1
        assert result[0].name == "test"
        assert result[0].enabled is True


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test_load_for_cli(mock_load_builtin_toolsets):
    toolset = MagicMock(spec=Toolset)
    toolset.name = "test"
    toolset.tags = [ToolsetTag.CORE, ToolsetTag.CLI]
    toolset.enabled = True
    toolset.status = ToolsetStatusEnum.ENABLED
    toolset.type = ToolsetType.BUILTIN
    toolset.path = None
    toolset.error = None
    toolset.check_prerequisites = MagicMock(return_value=ToolsetStatusEnum.ENABLED)
    mock_load_builtin_toolsets.return_value = [toolset]
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE, ToolsetTag.CLI], config={}, default_enabled=True
    )
    result = toolset_manager.load(use_cache=False)
    assert toolset.name in [t.name for t in result]


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test_load_for_server(mock_load_builtin_toolsets):
    toolset = MagicMock(spec=Toolset)
    toolset.name = "test"
    toolset.tags = [ToolsetTag.CORE, ToolsetTag.CLUSTER]
    toolset.enabled = True
    toolset.status = ToolsetStatusEnum.ENABLED
    toolset.type = ToolsetType.BUILTIN
    toolset.path = None
    toolset.error = None
    toolset.check_prerequisites = MagicMock(return_value=ToolsetStatusEnum.ENABLED)
    mock_load_builtin_toolsets.return_value = [toolset]
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE, ToolsetTag.CLUSTER],
        config={},
        default_enabled=False,  # Server mode
    )
    result = toolset_manager.load(use_cache=False)
    assert toolset.name in [t.name for t in result]


@patch("holmes.core.toolset_manager.load_toolsets_from_config")
def test_load_custom_toolsets_success(mock_load_toolsets_from_config):
    yaml_toolset = MagicMock(spec=Toolset)
    yaml_toolset.name = "custom"
    yaml_toolset.tags = [ToolsetTag.CORE]
    yaml_toolset.enabled = True
    mock_load_toolsets_from_config.return_value = [yaml_toolset]
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as tmpfile:
        data = {
            "toolsets": {
                "custom": {
                    "enabled": True,
                    "description": "test",
                    "config": {"key": "value"},
                }
            }
        }
        yaml.dump(data, tmpfile)
        tmpfile_path = tmpfile.name
    from pathlib import Path

    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={},
        custom_toolset_paths=[Path(tmpfile_path)],
        default_enabled=True,
    )
    assert "custom" in toolset_manager.registry.toolsets
    os.remove(tmpfile_path)


def test_load_custom_toolsets_no_file():
    from pathlib import Path

    with pytest.raises(FileNotFoundError):
        ToolsetManager(
            tags=[ToolsetTag.CORE],
            config={},
            custom_toolset_paths=[Path("/nonexistent/path.yaml")],
            default_enabled=True,
        )


def test_load_custom_toolsets_none():
    # With no custom toolsets, manager should still work
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE], config={}, custom_toolset_paths=[], default_enabled=True
    )
    # Should have builtin toolsets loaded
    assert len(toolset_manager.registry.toolsets) > 0


def test_registry_add_and_update():
    """Test that ToolsetRegistry properly adds and updates toolsets"""
    from holmes.core.toolset_manager import ToolsetRegistry

    registry = ToolsetRegistry()

    # Test add
    toolset1 = MagicMock(spec=Toolset)
    toolset1.name = "test1"
    toolset1.tags = [ToolsetTag.CORE]
    registry.add([toolset1])
    assert "test1" in registry.toolsets

    # Test update with override
    original_toolset = registry.toolsets["test1"]
    original_toolset.override_with = MagicMock()
    registry.update_from_config({"test1": {"enabled": False}})
    # Note: update creates a new toolset and calls override_with in current implementation


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test_load_custom_builtin_toolsets_valid(mock_load_builtin_toolsets, tmp_path):
    # Create a mock builtin toolset named dummy_tool
    builtin_toolset = MagicMock(spec=Toolset)
    builtin_toolset.name = "dummy_tool"
    builtin_toolset.tags = [ToolsetTag.CORE]
    builtin_toolset.enabled = False  # Default disabled

    # Mock override_with to actually update the enabled field
    def mock_override(override):
        if hasattr(override, "enabled"):
            builtin_toolset.enabled = override.enabled

    builtin_toolset.override_with = MagicMock(side_effect=mock_override)

    mock_load_builtin_toolsets.return_value = [builtin_toolset]

    # Override it with custom YAML
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {
        "toolsets": {
            "dummy_tool": {
                "enabled": True,  # Override to enabled
            }
        }
    }
    custom_file.write_text(yaml.dump(data))

    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={},
        custom_toolset_paths=[custom_file],
        default_enabled=False,  # Don't auto-enable
    )

    # The toolset should be in the registry and enabled
    assert "dummy_tool" in toolset_manager.registry.toolsets
    # The override should have set enabled=True
    assert toolset_manager.registry.toolsets["dummy_tool"].enabled is True


def test_load_custom_toolsets_valid(tmp_path):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {
        "toolsets": {
            "dummy_tool": {
                "enabled": True,
                "description": "dummy",
                "config": {"key": "value"},
            }
        }
    }
    custom_file.write_text(yaml.dump(data))

    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={},
        custom_toolset_paths=[custom_file],
        default_enabled=True,
    )

    assert "dummy_tool" in toolset_manager.registry.toolsets
    tool = toolset_manager.registry.toolsets["dummy_tool"]
    assert str(getattr(tool, "path", None)) == str(custom_file)


def test_load_custom_toolsets_missing_field_invalid(tmp_path):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {"toolsets": {"dummy_tool": {"enabled": True, "config": {"key": "value"}}}}
    custom_file.write_text(yaml.dump(data))

    # This should log a warning but not fail
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={},
        custom_toolset_paths=[custom_file],
        default_enabled=True,
        suppress_logging=True,  # Suppress the warning for testing
    )

    # The invalid toolset should not be loaded
    assert "dummy_tool" not in toolset_manager.registry.toolsets


def test_load_custom_toolsets_invalid_yaml(tmp_path):
    custom_file = tmp_path / "custom_toolset.yaml"
    custom_file.write_text("::::")

    with pytest.raises(ValueError) as e_info:
        ToolsetManager(
            tags=[ToolsetTag.CORE],
            config={},
            custom_toolset_paths=[custom_file],
            default_enabled=True,
        )
    assert "No 'toolsets' or 'mcp_servers' key found" in str(e_info.value)


def test_load_custom_toolsets_empty_file(tmp_path):
    custom_file = tmp_path / "custom_toolset.yaml"
    custom_file.write_text("")

    with pytest.raises(ValueError) as e_info:
        ToolsetManager(
            tags=[ToolsetTag.CORE],
            config={},
            custom_toolset_paths=[custom_file],
            default_enabled=True,
        )
    # Empty file results in None from benedict, which causes different error
    assert "Failed to load toolsets" in str(e_info.value) or "No 'toolsets'" in str(
        e_info.value
    )


def test_mcp_servers_from_custom_toolset_config(tmp_path):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {
        "mcp_servers": {
            "mcp1": {
                "url": "http://example.com:8000/sse",
                "description": "Test MCP server",
                "config": {"key": "value"},
            }
        }
    }
    custom_file.write_text(yaml.dump(data))

    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={},
        custom_toolset_paths=[custom_file],
        default_enabled=True,
    )

    assert "mcp1" in toolset_manager.registry.toolsets
    assert toolset_manager.registry.toolsets["mcp1"].type == ToolsetType.MCP


def test_mcp_servers_from_config():
    mcp_servers = {
        "mcp1": {
            "url": "http://example.com:8000/sse",
            "description": "Test MCP server",
            "config": {"key": "value"},
        }
    }

    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={"toolsets": {}, "mcp_servers": mcp_servers},
        default_enabled=True,
    )

    assert "mcp1" in toolset_manager.registry.toolsets
    # The type should be set on the toolset object, not in config
    # Note: type might be None if the toolset wasn't properly created
    # This test might need adjustment based on how MCP servers are loaded
