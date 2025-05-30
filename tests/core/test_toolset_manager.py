import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from holmes.core.tools import ToolsetStatusEnum, ToolsetTag, ToolsetType
from holmes.core.toolset_manager import ToolsetManager


@pytest.fixture
def toolset_manager():
    return ToolsetManager()


def test_get_toolset_definition_enabled_true_bool():
    config = {"enabled": True}
    assert ToolsetManager.get_toolset_definition_enabled(config) is True


def test_get_toolset_definition_enabled_false_bool():
    config = {"enabled": False}
    assert ToolsetManager.get_toolset_definition_enabled(config) is False


def test_get_toolset_definition_enabled_false_str():
    config = {"enabled": "false"}
    assert ToolsetManager.get_toolset_definition_enabled(config) is False


def test_get_toolset_definition_enabled_true_str():
    config = {"enabled": "true"}
    assert ToolsetManager.get_toolset_definition_enabled(config) is True


def test_get_toolset_definition_enabled_default():
    config = {}
    assert ToolsetManager.get_toolset_definition_enabled(config) is True


def test_cli_tool_tags(toolset_manager):
    tags = toolset_manager.cli_tool_tags
    assert ToolsetTag.CORE in tags
    assert ToolsetTag.CLI in tags


def test_server_tool_tags(toolset_manager):
    tags = toolset_manager.server_tool_tags
    assert ToolsetTag.CORE in tags
    assert ToolsetTag.CLUSTER in tags


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
@patch("holmes.core.toolset_manager.load_toolsets_config")
def test__list_all_toolsets_merges_configs(
    mock_load_toolsets_config, mock_load_builtin_toolsets, toolset_manager
):
    builtin_toolset = MagicMock()
    builtin_toolset.name = "builtin"
    builtin_toolset.enabled = True
    builtin_toolset.tags = [ToolsetTag.CORE]
    builtin_toolset.check_prerequisites = MagicMock()
    mock_load_builtin_toolsets.return_value = [builtin_toolset]
    config_toolset = MagicMock()
    config_toolset.name = "config"
    config_toolset.enabled = True
    config_toolset.tags = [ToolsetTag.CLI]
    config_toolset.check_prerequisites = MagicMock()
    mock_load_toolsets_config.return_value = [config_toolset]

    toolset_manager.toolsets = {"config": {"enabled": True}}
    toolsets = toolset_manager._list_all_toolsets(check_prerequisites=False)
    names = [t.name for t in toolsets]
    assert "builtin" in names
    assert "config" in names


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
@patch("holmes.core.toolset_manager.ToolsetManager.load_custom_toolsets")
def test__list_all_toolsets_custom_override_error(
    mock_load_custom_toolsets, mock_load_builtin_toolsets, toolset_manager
):
    builtin_toolset = MagicMock()
    builtin_toolset.name = "duplicate"
    mock_load_builtin_toolsets.return_value = [builtin_toolset]
    custom_toolset = MagicMock()
    custom_toolset.name = "duplicate"
    mock_load_custom_toolsets.return_value = [custom_toolset]
    with pytest.raises(Exception):
        toolset_manager._list_all_toolsets(check_prerequisites=False)


@patch("holmes.core.toolset_manager.ToolsetManager._list_all_toolsets")
def test_refresh_toolset_status_creates_file(mock_list_all_toolsets, toolset_manager):
    toolset = MagicMock()
    toolset.name = "test"
    toolset.status = ToolsetStatusEnum.ENABLED
    toolset.enabled = True
    toolset.type = ToolsetType.BUILTIN
    toolset.path = None
    toolset.error = None
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
    mock_list_all_toolsets.return_value = [toolset]
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "toolsets_status.json")
        toolset_manager.toolset_status_location = cache_path
        toolset_manager.refresh_toolset_status()
        assert os.path.exists(cache_path)
        with open(cache_path) as f:
            data = json.load(f)
            assert data[0]["name"] == "test"


@patch("holmes.core.toolset_manager.ToolsetManager._list_all_toolsets")
def test_load_toolset_with_status_reads_cache(mock_list_all_toolsets, toolset_manager):
    toolset = MagicMock()
    toolset.name = "test"
    toolset.tags = [ToolsetTag.CORE]
    toolset.enabled = True
    toolset.status = ToolsetStatusEnum.ENABLED
    toolset.type = ToolsetType.BUILTIN
    toolset.path = None
    toolset.error = None
    mock_list_all_toolsets.return_value = [toolset]
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "toolsets_status.json")
        cache_data = [
            {
                "name": "test",
                "status": "ENABLED",
                "enabled": True,
                "type": "BUILTIN",
                "path": None,
                "error": None,
            }
        ]
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)
        toolset_manager.toolset_status_location = cache_path
        result = toolset_manager.load_toolset_with_status()
        assert result[0].name == "test"
        assert result[0].enabled is True


@patch("holmes.core.toolset_manager.ToolsetManager.load_toolset_with_status")
def test_list_enabled_console_toolsets(mock_load_toolset_with_status, toolset_manager):
    toolset = MagicMock()
    toolset.tags = [ToolsetTag.CORE, ToolsetTag.CLI]
    toolset.enabled = True
    mock_load_toolset_with_status.return_value = [toolset]
    result = toolset_manager.list_enabled_console_toolsets()
    assert toolset in result


@patch("holmes.core.toolset_manager.ToolsetManager.load_toolset_with_status")
def test_list_enabled_server_toolsets(mock_load_toolset_with_status, toolset_manager):
    toolset = MagicMock()
    toolset.tags = [ToolsetTag.CORE, ToolsetTag.CLUSTER]
    toolset.enabled = True
    mock_load_toolset_with_status.return_value = [toolset]
    result = toolset_manager.list_enabled_server_toolsets()
    assert toolset in result


@patch("holmes.core.toolset_manager.benedict")
@patch("holmes.core.toolset_manager.load_toolsets_config")
def test_load_custom_toolsets_success(
    mock_load_toolsets_config, mock_benedict, toolset_manager
):
    yaml_toolset = MagicMock()
    yaml_toolset.name = "custom"
    mock_load_toolsets_config.return_value = [yaml_toolset]
    with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
        tmpfile.write(b"toolsets:\n  custom:\n    enabled: true\n")
        tmpfile.flush()
        tmpfile_path = tmpfile.name
    toolset_manager.custom_toolsets = [tmpfile_path]
    mock_benedict.return_value.get.side_effect = lambda k, **kwargs: {
        "toolsets": {"custom": {"enabled": True}},
        "mcp_servers": {},
    }[k]
    result = toolset_manager.load_custom_toolsets()
    assert yaml_toolset in result
    os.remove(tmpfile_path)


@patch("holmes.core.toolset_manager.load_toolsets_config")
@patch("holmes.core.toolset_manager.benedict")
def test_load_custom_toolsets_no_file(
    mock_benedict, mock_load_toolsets_config, toolset_manager
):
    toolset_manager.custom_toolsets = ["/nonexistent/path.yaml"]
    with pytest.raises(FileNotFoundError):
        toolset_manager.load_custom_toolsets()


def test_load_custom_toolsets_none(toolset_manager):
    toolset_manager.custom_toolsets = None
    assert toolset_manager.load_custom_toolsets() == []


def test_add_or_merge_yaml_toolsets_merges():
    existing = {}
    new_toolset = MagicMock()
    new_toolset.name = "merge"
    existing_toolset = MagicMock()
    existing_toolset.name = "merge"
    existing["merge"] = existing_toolset
    new_toolset.override_with = MagicMock()
    ToolsetManager.add_or_merge_yaml_toolsets(ToolsetManager, [new_toolset], existing)
    new_toolset.override_with.assert_called_once_with(new_toolset)


def test_add_or_merge_yaml_toolsets_adds():
    existing = {}
    new_toolset = MagicMock()
    new_toolset.name = "add"
    ToolsetManager.add_or_merge_yaml_toolsets(ToolsetManager, [new_toolset], existing)
    assert existing["add"] == new_toolset
