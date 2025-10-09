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
def test__list_all_toolsets_cannot_add_new_via_config(
    mock_load_builtin_toolsets, toolset_manager
):
    """Test that new toolsets cannot be added via 'toolsets' config - only existing can be configured"""
    builtin_toolset = MagicMock(spec=Toolset)
    builtin_toolset.name = "builtin"
    builtin_toolset.tags = [ToolsetTag.CORE]
    builtin_toolset.enabled = True
    builtin_toolset.status = ToolsetStatusEnum.ENABLED
    builtin_toolset.error = None
    builtin_toolset.type = ToolsetType.BUILTIN
    builtin_toolset.path = None
    builtin_toolset.config = None
    builtin_toolset.additional_instructions = None
    builtin_toolset.check_prerequisites = MagicMock(
        return_value=ToolsetStatusEnum.ENABLED
    )
    mock_load_builtin_toolsets.return_value = [builtin_toolset]

    # Create a new manager with config trying to add new toolset
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE, ToolsetTag.CLI],
        config={
            "toolsets": {"new-custom-tool": {"description": "test config toolset"}}
        },
        default_enabled=True,
        suppress_logging=True,  # Suppress the error log in tests
    )
    toolsets = toolset_manager.registry.get_by_tags([ToolsetTag.CORE, ToolsetTag.CLI])
    names = [t.name for t in toolsets]
    assert "builtin" in names
    # New toolset should NOT be added via config
    assert "new-custom-tool" not in names


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test__list_all_toolsets_override_builtin_config(
    mock_load_builtin_toolsets, toolset_manager
):
    builtin_toolset = YAMLToolset(
        name="builtin",
        tags=[ToolsetTag.CORE],
        description="Builtin toolset",
        experimental=False,
        tools=[],  # Required field after validator fix
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
    toolset1.enabled = True
    toolset1.config = {"existing": "value"}
    toolset1.additional_instructions = None
    registry.add([toolset1])
    assert "test1" in registry.toolsets

    # Test update config for existing toolset
    registry.update_from_config(
        {"test1": {"enabled": False, "config": {"new": "data"}}}
    )
    # Should have updated the existing toolset
    assert registry.toolsets["test1"].enabled is False
    # Config should be merged
    assert registry.toolsets["test1"].config == {"existing": "value", "new": "data"}


@patch("holmes.core.toolset_manager.load_builtin_toolsets")
def test_custom_file_cannot_override_builtin(mock_load_builtin_toolsets, tmp_path):
    """Test that custom YAML files cannot override builtin toolsets"""
    # Create a mock builtin toolset named dummy_tool
    builtin_toolset = MagicMock(spec=Toolset)
    builtin_toolset.name = "dummy_tool"
    builtin_toolset.tags = [ToolsetTag.CORE]
    builtin_toolset.enabled = False  # Default disabled
    builtin_toolset.config = None
    builtin_toolset.additional_instructions = None

    mock_load_builtin_toolsets.return_value = [builtin_toolset]

    # Try to override it with custom YAML (should fail)
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {
        "toolsets": {
            "dummy_tool": {
                "enabled": True,  # Try to override to enabled
                "description": "Custom override attempt",
            }
        }
    }
    custom_file.write_text(yaml.dump(data))

    # This should raise an error about conflict
    with pytest.raises(ValueError) as exc_info:
        ToolsetManager(
            tags=[ToolsetTag.CORE],
            config={},
            custom_toolset_paths=[custom_file],
            default_enabled=False,
        )

    assert "conflict with builtin toolsets" in str(exc_info.value)


def test_load_custom_toolsets_valid(tmp_path):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {
        "toolsets": {
            "dummy_tool": {
                "enabled": True,
                "description": "dummy",
                "config": {"key": "value"},
                "tools": [],  # Required field after validator fix
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
    """Test that toolsets missing required fields are skipped with error logging"""
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {"toolsets": {"dummy_tool": {"enabled": True, "config": {"key": "value"}}}}
    custom_file.write_text(yaml.dump(data))

    # This should log an error but not raise - invalid toolset is skipped
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


def test_mcp_servers_can_be_added_via_config():
    """Test that MCP servers CAN be added via mcp_servers config section"""
    mcp_servers = {
        "mcp1": {
            "url": "http://example.com:8000/sse",
            "description": "Test MCP server",
            "config": {"key": "value"},
        }
    }

    # MCP servers can be added via the mcp_servers section
    toolset_manager = ToolsetManager(
        tags=[ToolsetTag.CORE],
        config={"toolsets": {}, "mcp_servers": mcp_servers},
        default_enabled=True,
    )
    assert len(toolset_manager.toolsets) == 1
    assert "mcp1" in toolset_manager.toolsets
    assert toolset_manager.toolsets["mcp1"]["type"] == ToolsetType.MCP.value


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
    manager = ToolsetManager(global_fast_model=global_fast_model)

    # Load toolsets (this triggers injection)
    result = manager._list_all_toolsets(check_prerequisites=False)

    # Verify the toolset received the global_fast_model injection
    kubernetes_toolset = next(t for t in result if t.name == "kubernetes")
    config_dict = {t.name: t.config for t in kubernetes_toolset.transformers}

    assert config_dict["llm_summarize"]["global_fast_model"] == "azure/gpt-4.1"
    assert config_dict["llm_summarize"]["input_threshold"] == 1000  # Original
    assert config_dict["llm_summarize"]["prompt"] == "K8s prompt"  # Original

    # MCP server should be added
    assert "mcp1" in toolset_manager.registry.toolsets
    assert toolset_manager.registry.toolsets["mcp1"].type == ToolsetType.MCP
