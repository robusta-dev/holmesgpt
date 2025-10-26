from io import TextIOWrapper
import json
import os
import tempfile
from typing import Any, Generator
from unittest.mock import MagicMock, patch

from pydantic import FilePath
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
from holmes.plugins.toolsets import load_builtin_toolsets


@pytest.fixture
def toolset_manager() -> ToolsetManager:
    return ToolsetManager()


def test_cli_tool_tags(toolset_manager):
    tags = toolset_manager.cli_tool_tags
    assert ToolsetTag.CORE in tags
    assert ToolsetTag.CLI in tags


def test_server_tool_tags(toolset_manager):
    tags = toolset_manager.server_tool_tags
    assert ToolsetTag.CORE in tags
    assert ToolsetTag.CLUSTER in tags


def test_toolset_manager_loading_builtin_toolsets_only(toolset_manager: ToolsetManager):
    toolset_manager._load_toolsets_definitions()
    assert len(toolset_manager._toolset_definitions_by_name) > 0

    for toolset in toolset_manager._toolset_definitions_by_name.values():
        assert toolset.type == ToolsetType.BUILTIN


# @patch("holmes.core.toolset_manager.load_builtin_toolsets")
# @patch("holmes.core.toolset_manager.load_toolsets_from_config")
# def test__list_all_toolsets_merges_configs(
#     mock_load_toolsets_from_config, mock_load_builtin_toolsets, toolset_manager
# ):
#     builtin_toolset = MagicMock(spec=Toolset)
#     builtin_toolset.name = "builtin"
#     builtin_toolset.tags = [ToolsetTag.CORE]
#     builtin_toolset.check_prerequisites = MagicMock()
#     mock_load_builtin_toolsets.return_value = [builtin_toolset]
#     config_toolset = MagicMock(spec=Toolset)
#     config_toolset.name = "config"
#     config_toolset.tags = [ToolsetTag.CLI]
#     config_toolset.check_prerequisites = MagicMock()
#     mock_load_toolsets_from_config.return_value = [config_toolset]

#     toolset_manager.toolsets = {"config": {"description": "test config toolset"}}
#     toolsets = toolset_manager._list_all_toolsets(initialize_toolsets=False)
#     names = [t.name for t in toolsets]
#     assert "builtin" in names
#     assert "config" in names


# @patch("holmes.core.toolset_manager.load_builtin_toolsets")
# def test__list_all_toolsets_custom_toolset(mock_load_builtin_toolsets, toolset_manager):
#     builtin_toolset = YAMLToolset(
#         name="builtin",
#         tags=[ToolsetTag.CORE],
#         description="Builtin toolset",
#         experimental=False,
#     )
#     mock_load_builtin_toolsets.return_value = [builtin_toolset]
#     with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmpfile:
#         data = {"toolsets": {"builtin": {"enabled": False}}}
#         json.dump(data, tmpfile, indent=2)
#         tmpfile_path = tmpfile.name
#     toolset_manager.custom_toolsets = [tmpfile_path]
#     toolsets = toolset_manager._list_all_toolsets(initialize_toolsets=False)
#     assert len(toolsets) == 1
#     assert toolsets[0].enabled is False
#     os.remove(tmpfile_path)


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
        toolset_manager._toolset_status_location = cache_path
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


# class TestToolsetManagerMCPServers:
#     @pytest.fixture(autouse=True, scope="class")
#     def toolset_file(self):
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
#             yield temp_file

#     @pytest.fixture(autouse=True, scope="class")
#     def toolset_manager(self, toolset_file) -> Generator[ToolsetManager, Any, None]:
#         toolset_manager = ToolsetManager(
#             custom_toolset_file_paths=[FilePath(toolset_file.name)]
#         )
#         yield toolset_manager


def test_mcp_servers_from_custom_toolset_config(
    tmp_path, toolset_manager: ToolsetManager
):
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

    toolset_manager._custom_toolset_file_paths = [custom_file]
    result = toolset_manager._load_custom_toolsets()
    assert len(result) == 1
    assert result[0].name == "mcp1"
    assert result[0].type == ToolsetType.MCP


def test_mcp_servers_from_config(toolset_manager):
    mcp_servers = {
        "mcp1": {
            "url": "http://example.com:8000/sse",
            "description": "Test MCP server",
            "config": {"key": "value"},
        }
    }

    toolset_manager = ToolsetManager(
        toolset_settings=None,
        mcp_servers=mcp_servers,
        custom_toolset_file_paths=None,
        custom_toolsets_from_cli=None,
    )
    assert len(toolset_manager.toolsets_settings) == 1
    assert "mcp1" in toolset_manager.toolsets_settings
    assert toolset_manager.toolsets_settings["mcp1"]["type"] == ToolsetType.MCP.value


# Tests for transformer config merging functionality


def test_inject_fast_model_with_existing_transformers():
    """Test that global fast model is injected into existing transformer configs."""
    from holmes.core.transformers import Transformer

    global_fast_model = "gpt-4o-mini"

    # Create toolset with existing transformers (should get injection)
    toolset = YAMLToolset(
        name="test_toolset",
        tags=[ToolsetTag.CORE],
        description="Test toolset",
        transformers=[
            Transformer(
                name="llm_summarize",
                config={"input_threshold": 1000, "prompt": "Custom"},
            )
        ],
    )

    manager = ToolsetManager(global_fast_model=global_fast_model)
    manager._inject_fast_model_into_transformers([toolset])

    # Verify injection occurred
    assert toolset.transformers is not None
    config_dict = {t.name: t.config for t in toolset.transformers}

    # Should have global_fast_model injected, original config preserved
    assert config_dict["llm_summarize"]["global_fast_model"] == "gpt-4o-mini"
    assert config_dict["llm_summarize"]["input_threshold"] == 1000  # Original
    assert config_dict["llm_summarize"]["prompt"] == "Custom"  # Original


def test_no_injection_when_no_transformers():
    """Test that no injection occurs when toolset has no transformers (new behavior)."""

    global_fast_model = "gpt-4o-mini"

    # Create toolset without transformers
    toolset = YAMLToolset(
        name="test_toolset", tags=[ToolsetTag.CORE], description="Test toolset"
    )

    manager = ToolsetManager(global_fast_model=global_fast_model)
    manager._inject_fast_model_into_transformers([toolset])

    # No injection should occur when toolset has no transformers
    assert toolset.transformers is None


def test_no_injection_when_no_global_fast_model():
    """Test that nothing happens when no global fast model is provided."""
    from holmes.core.transformers import Transformer

    toolset = YAMLToolset(
        name="test_toolset",
        tags=[ToolsetTag.CORE],
        description="Test toolset",
        transformers=[
            Transformer(name="llm_summarize", config={"input_threshold": 1000})
        ],
    )
    original_transformers = toolset.transformers

    manager = ToolsetManager()  # No global fast model
    manager._inject_fast_model_into_transformers([toolset])

    # Toolset configs should remain unchanged (no injection)
    assert toolset.transformers == original_transformers
    assert "global_fast_model" not in toolset.transformers[0].config


def test_injection_only_affects_llm_summarize_transformers():
    """Test that injection only affects llm_summarize transformers, not others."""
    from holmes.core.transformers import Transformer

    global_fast_model = "gpt-4o-mini"

    toolset = YAMLToolset(
        name="test_toolset",
        tags=[ToolsetTag.CORE],
        description="Test toolset",
        transformers=[
            Transformer(name="llm_summarize", config={"input_threshold": 1000}),
            Transformer(name="custom_transformer", config={"param": "value"}),
        ],
    )

    manager = ToolsetManager(global_fast_model=global_fast_model)
    manager._inject_fast_model_into_transformers([toolset])

    # Check that only llm_summarize got injection
    config_dict = {t.name: t.config for t in toolset.transformers}

    assert "llm_summarize" in config_dict
    assert "custom_transformer" in config_dict
    assert config_dict["llm_summarize"]["global_fast_model"] == "gpt-4o-mini"
    assert "global_fast_model" not in config_dict["custom_transformer"]
    assert config_dict["custom_transformer"]["param"] == "value"  # Unchanged


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test_list_all_toolsets_applies_fast_model_injection(mock_load_builtin_toolsets):
    """Integration test that global fast model is injected during toolset loading."""
    from holmes.core.transformers import Transformer

    # Create toolset with transformers
    toolset = YAMLToolset(
        name="kubernetes",
        tags=[ToolsetTag.CORE],
        description="Kubernetes toolset",
        transformers=[
            Transformer(
                name="llm_summarize",
                config={"input_threshold": 1000, "prompt": "K8s prompt"},
            )
        ],
    )
    mock_load_builtin_toolsets.return_value = [toolset]

    # Create manager with CLI fast_model
    global_fast_model = "azure/gpt-4.1"
    manager: ToolsetManager = ToolsetManager(global_fast_model=global_fast_model)

    # Load toolsets (this triggers injection)
    toolsets = manager._load_toolsets_definitions()

    # Verify the toolset received the global_fast_model injection
    kubernetes_toolset = next(t for t in toolsets if t.name == "kubernetes")
    config_dict = {t.name: t.config for t in kubernetes_toolset.transformers}

    assert config_dict["llm_summarize"]["global_fast_model"] == "azure/gpt-4.1"
    assert config_dict["llm_summarize"]["input_threshold"] == 1000  # Original
    assert config_dict["llm_summarize"]["prompt"] == "K8s prompt"  # Original


class TestToolsetManagerCustomToolsets:
    @pytest.fixture(autouse=True, scope="class")
    def custom_toolset_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            yield temp_file

    @pytest.fixture(autouse=True, scope="class")
    def custom_toolset_manager(
        self, custom_toolset_file
    ) -> Generator[ToolsetManager, Any, None]:
        toolset_manager = ToolsetManager(
            custom_toolset_file_paths=[FilePath(custom_toolset_file.name)]
        )
        yield toolset_manager

    def test_load_custom_toolsets_success(
        self, custom_toolset_manager: ToolsetManager, custom_toolset_file
    ):
        data = {
            "toolsets": {
                "test_toolset": {
                    "tools": [],
                    "description": "test description",
                }
            }
        }
        yaml.safe_dump(data, custom_toolset_file)
        custom_toolset_manager._load_toolsets_definitions()

        custom_toolset = custom_toolset_manager._toolset_definitions_by_name[
            "test_toolset"
        ]
        assert custom_toolset.description == "test description"
        assert len(custom_toolset.tools) == 0
        assert custom_toolset.path == FilePath(custom_toolset_file.name)
        assert custom_toolset.type == ToolsetType.CUSTOMIZED

    def test_load_custom_toolsets_override_builtin_toolset(
        self, custom_toolset_manager: ToolsetManager, custom_toolset_file
    ):
        builtin_toolsets = load_builtin_toolsets()
        builtin_toolset = builtin_toolsets[0]
        assert len(builtin_toolset.tools) > 0

        data = {
            "toolsets": {
                builtin_toolset.name: {
                    "tools": [],
                    "description": "test description",
                }
            }
        }
        yaml.safe_dump(data, custom_toolset_file)
        custom_toolset_manager._load_toolsets_definitions()

        overridden_toolset = custom_toolset_manager._toolset_definitions_by_name[
            builtin_toolset.name
        ]
        assert overridden_toolset.description == "test description"
        assert len(overridden_toolset.tools) == 0

    def test_load_custom_toolsets_no_file(self, custom_toolset_manager: ToolsetManager):
        custom_toolset_manager._custom_toolset_file_paths = [
            FilePath("/nonexistent/path.yaml")
        ]
        with pytest.raises(FileNotFoundError):
            custom_toolset_manager._load_toolsets_definitions()

    def test_load_custom_toolsets_missing_field_invalid(
        self, custom_toolset_manager: ToolsetManager, custom_toolset_file
    ):
        data: dict[str, dict[str, dict]] = {"toolsets": {"invalid_toolset": {}}}
        yaml.safe_dump(data, custom_toolset_file)
        custom_toolset_manager._load_toolsets_definitions()

        assert (
            "invalid_toolset" not in custom_toolset_manager._toolset_definitions_by_name
        )

    def test_load_custom_toolsets_invalid_yaml(
        self, custom_toolset_manager: ToolsetManager, custom_toolset_file: TextIOWrapper
    ):
        custom_toolset_file.write("::::")
        with pytest.raises(Exception) as e_info:
            custom_toolset_manager._load_toolsets_definitions()
        assert "file is empty or invalid YAML." in e_info.value.args[0]

    def test_load_custom_toolsets_empty_file(
        self, custom_toolset_manager: ToolsetManager, custom_toolset_file: TextIOWrapper
    ):
        custom_toolset_file.write("")
        with pytest.raises(Exception) as e_info:
            custom_toolset_manager._load_toolsets_definitions()
        assert "file is empty or invalid YAML." in e_info.value.args[0]
