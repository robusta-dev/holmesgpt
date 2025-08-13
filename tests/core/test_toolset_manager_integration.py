import pytest
from holmes.core.toolset_manager import ToolsetManager
from holmes.config import Config
from holmes.core.tools import ToolsetType


def test_toolset_manager_filtering_integration():
    """Test end-to-end filtering through ToolsetManager"""
    # Create config with filter
    config = Config(allowed_builtin_toolsets=["kubernetes/core"])
    manager = ToolsetManager(config=config)

    toolsets = manager._list_all_toolsets()
    builtin_toolsets = [t for t in toolsets if t.type == ToolsetType.BUILTIN]

    # Should only contain allowed toolsets
    assert len(builtin_toolsets) <= 1  # May be 0 if kubernetes/core not available
    if builtin_toolsets:
        assert builtin_toolsets[0].name == "kubernetes/core"


def test_custom_toolsets_unaffected():
    """Test that custom toolsets are not affected by filtering"""
    config = Config(allowed_builtin_toolsets=["kubernetes/core"])
    manager = ToolsetManager(config=config)

    toolsets = manager._list_all_toolsets()
    custom_toolsets = [t for t in toolsets if t.type == ToolsetType.CUSTOMIZED]

    # Custom toolsets should be unaffected
    # Compare with no-filter case
    config_no_filter = Config()
    manager_no_filter = ToolsetManager(config=config_no_filter)
    toolsets_no_filter = manager_no_filter._list_all_toolsets()
    custom_toolsets_no_filter = [
        t for t in toolsets_no_filter if t.type == ToolsetType.CUSTOMIZED
    ]

    assert len(custom_toolsets) == len(custom_toolsets_no_filter)


def test_toolset_manager_no_filter():
    """Test ToolsetManager works normally when no filter specified"""
    config = Config()  # No filter
    manager = ToolsetManager(config=config)

    toolsets = manager._list_all_toolsets()
    builtin_toolsets = [t for t in toolsets if t.type == ToolsetType.BUILTIN]

    # Should load all builtin toolsets
    assert len(builtin_toolsets) > 0  # Assuming some builtin toolsets exist


def test_toolset_manager_empty_filter():
    """Test ToolsetManager with empty filter list"""
    config = Config(allowed_builtin_toolsets=[])
    manager = ToolsetManager(config=config)

    toolsets = manager._list_all_toolsets()
    builtin_toolsets = [t for t in toolsets if t.type == ToolsetType.BUILTIN]

    # Should have no builtin toolsets
    assert len(builtin_toolsets) == 0


def test_toolset_manager_multiple_filters():
    """Test ToolsetManager with multiple allowed toolsets"""
    # Get all toolsets first to select valid names
    config_all = Config()
    manager_all = ToolsetManager(config=config_all)
    all_toolsets = manager_all._list_all_toolsets()
    all_builtin = [t for t in all_toolsets if t.type == ToolsetType.BUILTIN]

    if len(all_builtin) < 2:
        pytest.skip("Need at least 2 builtin toolsets for this test")

    # Select first two toolset names
    target_names = [all_builtin[0].name, all_builtin[1].name]

    config = Config(allowed_builtin_toolsets=target_names)
    manager = ToolsetManager(config=config)

    toolsets = manager._list_all_toolsets()
    builtin_toolsets = [t for t in toolsets if t.type == ToolsetType.BUILTIN]

    # Should have exactly 2 builtin toolsets
    assert len(builtin_toolsets) == 2
    assert {t.name for t in builtin_toolsets} == set(target_names)


def test_toolset_manager_invalid_names():
    """Test ToolsetManager with invalid toolset names"""
    config = Config(allowed_builtin_toolsets=["nonexistent/toolset"])
    manager = ToolsetManager(config=config)

    toolsets = manager._list_all_toolsets()
    builtin_toolsets = [t for t in toolsets if t.type == ToolsetType.BUILTIN]

    # Should have no builtin toolsets (invalid names filtered out)
    assert len(builtin_toolsets) == 0


def test_toolset_manager_backward_compatibility():
    """Test that ToolsetManager maintains backward compatibility"""
    # Test that ToolsetManager can be created without config parameter
    manager_without_config = ToolsetManager()
    toolsets_without_config = manager_without_config._list_all_toolsets()

    # Test that ToolsetManager with None config works the same
    manager_with_none = ToolsetManager(config=None)
    toolsets_with_none = manager_with_none._list_all_toolsets()

    # Should be identical
    assert len(toolsets_without_config) == len(toolsets_with_none)
    assert {t.name for t in toolsets_without_config} == {
        t.name for t in toolsets_with_none
    }


def test_config_toolset_manager_property():
    """Test that Config.toolset_manager property works with filtering"""
    config = Config(allowed_builtin_toolsets=["kubernetes/core"])

    # Access toolset_manager property
    manager = config.toolset_manager
    assert isinstance(manager, ToolsetManager)
    assert manager._config is config

    # Test that _get_allowed_builtin_toolsets returns correct value
    allowed = manager._get_allowed_builtin_toolsets()
    assert allowed == ["kubernetes/core"]


def test_config_toolset_manager_no_filter():
    """Test that Config.toolset_manager works without filter"""
    config = Config()

    # Access toolset_manager property
    manager = config.toolset_manager
    assert isinstance(manager, ToolsetManager)
    assert manager._config is config

    # Test that _get_allowed_builtin_toolsets returns None
    allowed = manager._get_allowed_builtin_toolsets()
    assert allowed is None


def test_toolset_manager_caching():
    """Test that ToolsetManager is cached in Config"""
    config = Config(allowed_builtin_toolsets=["kubernetes/core"])

    # Access toolset_manager twice
    manager1 = config.toolset_manager
    manager2 = config.toolset_manager

    # Should be the same instance (cached)
    assert manager1 is manager2


def test_end_to_end_filtering_flow():
    """Test the complete end-to-end filtering flow"""
    # This test verifies that the complete chain works:
    # Config -> ToolsetManager -> load_builtin_toolsets -> filtered results

    # Get baseline - all toolsets
    config_all = Config()
    all_toolsets = config_all.toolset_manager._list_all_toolsets()
    all_builtin_names = [t.name for t in all_toolsets if t.type == ToolsetType.BUILTIN]

    if not all_builtin_names:
        pytest.skip("No builtin toolsets available")

    # Test filtering to single toolset
    target_name = all_builtin_names[0]
    config_filtered = Config(allowed_builtin_toolsets=[target_name])
    filtered_toolsets = config_filtered.toolset_manager._list_all_toolsets()
    filtered_builtin = [t for t in filtered_toolsets if t.type == ToolsetType.BUILTIN]

    # Verify filtering worked
    assert len(filtered_builtin) == 1
    assert filtered_builtin[0].name == target_name

    # Verify other toolset types are unaffected
    all_non_builtin = [t for t in all_toolsets if t.type != ToolsetType.BUILTIN]
    filtered_non_builtin = [
        t for t in filtered_toolsets if t.type != ToolsetType.BUILTIN
    ]

    # Non-builtin toolsets should be unchanged
    assert len(all_non_builtin) == len(filtered_non_builtin)


def test_console_toolsets_filtering():
    """Test that list_console_toolsets respects filtering"""
    # Get all console toolsets without filtering
    config_all = Config()
    manager_all = ToolsetManager(config=config_all)
    all_console_toolsets = manager_all.list_console_toolsets()
    all_console_builtin = [
        t for t in all_console_toolsets if t.type == ToolsetType.BUILTIN
    ]

    if not all_console_builtin:
        pytest.skip("No builtin console toolsets available")

    # Filter to one toolset
    target_name = all_console_builtin[0].name
    config_filtered = Config(allowed_builtin_toolsets=[target_name])
    manager_filtered = ToolsetManager(config=config_filtered)
    filtered_console_toolsets = manager_filtered.list_console_toolsets()
    filtered_console_builtin = [
        t for t in filtered_console_toolsets if t.type == ToolsetType.BUILTIN
    ]

    # Should only have the one allowed toolset
    assert (
        len(filtered_console_builtin) <= 1
    )  # May be 0 if target doesn't have console tags
    if filtered_console_builtin:
        assert filtered_console_builtin[0].name == target_name


def test_server_toolsets_filtering():
    """Test that list_server_toolsets respects filtering"""
    # Get all server toolsets without filtering
    config_all = Config()
    manager_all = ToolsetManager(config=config_all)
    all_server_toolsets = manager_all.list_server_toolsets()
    all_server_builtin = [
        t for t in all_server_toolsets if t.type == ToolsetType.BUILTIN
    ]

    if not all_server_builtin:
        pytest.skip("No builtin server toolsets available")

    # Filter to one toolset
    target_name = all_server_builtin[0].name
    config_filtered = Config(allowed_builtin_toolsets=[target_name])
    manager_filtered = ToolsetManager(config=config_filtered)
    filtered_server_toolsets = manager_filtered.list_server_toolsets()
    filtered_server_builtin = [
        t for t in filtered_server_toolsets if t.type == ToolsetType.BUILTIN
    ]

    # Should only have the one allowed toolset
    assert (
        len(filtered_server_builtin) <= 1
    )  # May be 0 if target doesn't have server tags
    if filtered_server_builtin:
        assert filtered_server_builtin[0].name == target_name
