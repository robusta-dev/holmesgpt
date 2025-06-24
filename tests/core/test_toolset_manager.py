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
from holmes.core.toolset_manager import ToolsetManager


@pytest.fixture
def toolset_manager():
    return ToolsetManager()


def test_cli_tool_tags(toolset_manager):
    tags = toolset_manager.cli_tool_tags
    assert ToolsetTag.CORE in tags
    assert ToolsetTag.CLI in tags


def test_server_tool_tags(toolset_manager):
    tags = toolset_manager.server_tool_tags
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
    builtin_toolset.check_prerequisites = MagicMock()
    mock_load_builtin_toolsets.return_value = [builtin_toolset]
    config_toolset = MagicMock(spec=Toolset)
    config_toolset.name = "config"
    config_toolset.tags = [ToolsetTag.CLI]
    config_toolset.check_prerequisites = MagicMock()
    mock_load_toolsets_from_config.return_value = [config_toolset]

    toolset_manager.toolsets = {"config": {"description": "test config toolset"}}
    toolsets = toolset_manager._list_all_toolsets(check_prerequisites=False)
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
    toolset_manager.toolsets = {"builtin": {"enabled": False}}
    toolsets = toolset_manager._list_all_toolsets(check_prerequisites=False)
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
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmpfile:
        data = {"toolsets": {"builtin": {"enabled": False}}}
        json.dump(data, tmpfile, indent=2)
        tmpfile_path = tmpfile.name
    toolset_manager.custom_toolsets = [tmpfile_path]
    toolsets = toolset_manager._list_all_toolsets(check_prerequisites=False)
    assert len(toolsets) == 1
    assert toolsets[0].enabled is False
    os.remove(tmpfile_path)


@patch("holmes.core.toolset_manager.ToolsetManager._list_all_toolsets")
def test_refresh_toolset_status_creates_file(mock_list_all_toolsets, toolset_manager):
    toolset = MagicMock(spec=Toolset)
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
    toolset = MagicMock(spec=Toolset)
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
                "status": "enabled",
                "enabled": True,
                "type": "built-in",
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
def test_list_console_toolsets(mock_load_toolset_with_status, toolset_manager):
    toolset = MagicMock(spec=Toolset)
    toolset.tags = [ToolsetTag.CORE, ToolsetTag.CLI]
    toolset.enabled = True
    mock_load_toolset_with_status.return_value = [toolset]
    result = toolset_manager.list_console_toolsets()
    assert toolset in result


@patch("holmes.core.toolset_manager.ToolsetManager._list_all_toolsets")
def test_list_server_toolsets(mock_list_all_toolsets, toolset_manager):
    toolset = MagicMock(spec=Toolset)
    toolset.tags = [ToolsetTag.CORE, ToolsetTag.CLUSTER]
    toolset.enabled = True
    mock_list_all_toolsets.return_value = [toolset]
    result = toolset_manager.list_server_toolsets()
    assert toolset in result


@patch("holmes.core.toolset_manager.load_toolsets_from_config")
def test_load_custom_toolsets_success(mock_load_toolsets_from_config, toolset_manager):
    yaml_toolset = MagicMock(spec=Toolset)
    yaml_toolset.name = "custom"
    mock_load_toolsets_from_config.return_value = [yaml_toolset]
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmpfile:
        data = {"toolsets": {"custom": {"enabled": True, "config": {"key": "value"}}}}
        json.dump(data, tmpfile, indent=2)
        tmpfile_path = tmpfile.name
    toolset_manager.custom_toolsets = [tmpfile_path]
    result = toolset_manager.load_custom_toolsets(["builtin"])
    assert yaml_toolset in result
    os.remove(tmpfile_path)


@patch("holmes.core.toolset_manager.load_toolsets_from_config")
@patch("holmes.core.toolset_manager.benedict")
def test_load_custom_toolsets_no_file(
    mock_benedict, mock_load_toolsets_from_config, toolset_manager
):
    toolset_manager.custom_toolsets = ["/nonexistent/path.yaml"]
    with pytest.raises(FileNotFoundError):
        toolset_manager.load_custom_toolsets(["builtin"])


def test_load_custom_toolsets_none(toolset_manager):
    toolset_manager.custom_toolsets = None
    toolset_manager.custom_toolsets_from_cli = None
    assert toolset_manager.load_custom_toolsets(["builtin"]) == []


def test_add_or_merge_onto_toolsets_merges():
    existing = {}
    new_toolset = MagicMock(spec=Toolset)
    new_toolset.name = "merge"
    new_toolset.description = "This is a new toolset"
    existing_toolset = MagicMock(spec=Toolset)
    existing_toolset.name = "merge"
    existing_toolset.enabled = "enabled"
    existing["merge"] = existing_toolset
    new_toolset.override_with = MagicMock()
    ToolsetManager.add_or_merge_onto_toolsets(ToolsetManager, [new_toolset], existing)
    existing_toolset.override_with.assert_called_once_with(new_toolset)


def test_add_or_merge_onto_toolsets_adds():
    existing = {}
    new_toolset = MagicMock(spec=Toolset)
    new_toolset.name = "add"
    ToolsetManager.add_or_merge_onto_toolsets(ToolsetManager, [new_toolset], existing)
    assert existing["add"] == new_toolset


def test_load_custom_builtin_toolsets_valid(tmp_path, toolset_manager):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {
        "toolsets": {
            "dummy_tool": {
                "enabled": True,
            }
        }
    }
    custom_file.write_text(yaml.dump(data))

    toolset_manager.custom_toolsets = [custom_file]
    result = toolset_manager.load_custom_toolsets(builtin_toolsets_names=["dummy_tool"])

    assert isinstance(result, list)
    assert len(result) == 1
    tool = result[0]
    assert tool.name == "dummy_tool"
    assert str(getattr(tool, "path", None)) == str(custom_file)


def test_load_custom_toolsets_valid(tmp_path, toolset_manager):
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

    toolset_manager.custom_toolsets = [custom_file]
    result = toolset_manager.load_custom_toolsets(builtin_toolsets_names=[])

    assert isinstance(result, list)
    assert len(result) == 1
    tool = result[0]
    assert tool.name == "dummy_tool"
    assert str(getattr(tool, "path", None)) == str(custom_file)


def test_load_custom_toolsets_missing_field_invalid(tmp_path, toolset_manager):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {"toolsets": {"dummy_tool": {"enabled": True, "config": {"key": "value"}}}}
    custom_file.write_text(yaml.dump(data))

    toolset_manager.custom_toolsets = [custom_file]
    result = toolset_manager.load_custom_toolsets(builtin_toolsets_names=[])

    assert isinstance(result, list)
    assert len(result) == 0


def test_load_custom_toolsets_invalid_yaml(tmp_path, toolset_manager):
    custom_file = tmp_path / "custom_toolset.yaml"
    custom_file.write_text("::::")

    toolset_manager.custom_toolsets = [custom_file]
    with pytest.raises(Exception) as e_info:
        toolset_manager.load_custom_toolsets(builtin_toolsets_names=[])
    assert "No 'toolsets' or 'mcp_servers' key found" in e_info.value.args[0]


def test_load_custom_toolsets_empty_file(tmp_path, toolset_manager):
    custom_file = tmp_path / "custom_toolset.yaml"
    custom_file.write_text("")

    toolset_manager.custom_toolsets = [custom_file]

    with pytest.raises(Exception) as e_info:
        toolset_manager.load_custom_toolsets(builtin_toolsets_names=[])
    assert "Invalid data type:" in e_info.value.args[0]
