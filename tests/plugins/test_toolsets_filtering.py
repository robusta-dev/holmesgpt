import pytest
from holmes.plugins.toolsets import load_builtin_toolsets


def test_load_builtin_toolsets_no_filter():
    """Test that None filter preserves existing behavior"""
    toolsets_none = load_builtin_toolsets(allowed_builtin_toolsets=None)
    toolsets_default = load_builtin_toolsets()  # Default behavior

    assert len(toolsets_none) == len(toolsets_default)
    assert {t.name for t in toolsets_none} == {t.name for t in toolsets_default}


def test_load_builtin_toolsets_with_single_filter():
    """Test filtering to single toolset"""
    all_toolsets = load_builtin_toolsets()
    if not all_toolsets:
        pytest.skip("No builtin toolsets available")

    first_toolset_name = all_toolsets[0].name
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=[first_toolset_name])

    assert len(filtered) == 1
    assert filtered[0].name == first_toolset_name


def test_load_builtin_toolsets_with_multiple_filters():
    """Test filtering to multiple toolsets"""
    all_toolsets = load_builtin_toolsets()
    if len(all_toolsets) < 2:
        pytest.skip("Need at least 2 builtin toolsets")

    # Use reverse order to test that discovery order is preserved
    target_names = [all_toolsets[1].name, all_toolsets[0].name]
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=target_names)

    assert len(filtered) == 2
    # Should preserve discovery order, not filter order
    assert [t.name for t in filtered] == [all_toolsets[0].name, all_toolsets[1].name]


def test_load_builtin_toolsets_empty_filter():
    """Test that empty list results in no toolsets"""
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=[])
    assert len(filtered) == 0


def test_load_builtin_toolsets_invalid_names():
    """Test that invalid toolset names are handled gracefully"""
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=["nonexistent/toolset"])
    assert len(filtered) == 0


def test_load_builtin_toolsets_mixed_valid_invalid():
    """Test mix of valid and invalid names"""
    all_toolsets = load_builtin_toolsets()
    if not all_toolsets:
        pytest.skip("No builtin toolsets available")

    valid_name = all_toolsets[0].name
    mixed_names = [valid_name, "nonexistent/toolset"]
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=mixed_names)

    assert len(filtered) == 1
    assert filtered[0].name == valid_name


def test_load_builtin_toolsets_preserves_toolset_properties():
    """Test that filtered toolsets maintain their properties"""
    all_toolsets = load_builtin_toolsets()
    if not all_toolsets:
        pytest.skip("No builtin toolsets available")

    target_toolset = all_toolsets[0]
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=[target_toolset.name])

    assert len(filtered) == 1
    filtered_toolset = filtered[0]

    # Check that properties are preserved
    assert filtered_toolset.name == target_toolset.name
    assert filtered_toolset.type == target_toolset.type
    assert filtered_toolset.path == target_toolset.path


def test_load_builtin_toolsets_with_dal_parameter():
    """Test that dal parameter works with filtering"""
    # Test with dal=None and filtering
    filtered = load_builtin_toolsets(dal=None, allowed_builtin_toolsets=[])
    assert len(filtered) == 0

    # Test that dal parameter doesn't interfere with filtering
    all_toolsets = load_builtin_toolsets(dal=None)
    if all_toolsets:
        target_name = all_toolsets[0].name
        filtered_with_dal = load_builtin_toolsets(
            dal=None, allowed_builtin_toolsets=[target_name]
        )
        assert len(filtered_with_dal) == 1
        assert filtered_with_dal[0].name == target_name


def test_load_builtin_toolsets_case_sensitive_matching():
    """Test that toolset name matching is case-sensitive"""
    all_toolsets = load_builtin_toolsets()
    if not all_toolsets:
        pytest.skip("No builtin toolsets available")

    original_name = all_toolsets[0].name
    uppercase_name = original_name.upper()

    # Should not match if case is different
    if uppercase_name != original_name:  # Only test if case actually differs
        filtered = load_builtin_toolsets(allowed_builtin_toolsets=[uppercase_name])
        assert len(filtered) == 0


def test_load_builtin_toolsets_exact_name_matching():
    """Test that toolset name matching is exact (not substring)"""
    all_toolsets = load_builtin_toolsets()
    if not all_toolsets:
        pytest.skip("No builtin toolsets available")

    original_name = all_toolsets[0].name
    partial_name = (
        original_name[: len(original_name) // 2]
        if len(original_name) > 1
        else original_name
    )

    # Should not match partial name if it's different from full name
    if partial_name != original_name:
        filtered = load_builtin_toolsets(allowed_builtin_toolsets=[partial_name])
        assert len(filtered) == 0


def test_load_builtin_toolsets_all_valid_names():
    """Test filtering with all valid toolset names (should return all toolsets)"""
    all_toolsets = load_builtin_toolsets()
    if not all_toolsets:
        pytest.skip("No builtin toolsets available")

    all_names = [toolset.name for toolset in all_toolsets]
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=all_names)

    assert len(filtered) == len(all_toolsets)
    assert {t.name for t in filtered} == {t.name for t in all_toolsets}


def test_load_builtin_toolsets_duplicate_names_in_filter():
    """Test that duplicate names in filter list don't cause issues"""
    all_toolsets = load_builtin_toolsets()
    if not all_toolsets:
        pytest.skip("No builtin toolsets available")

    target_name = all_toolsets[0].name
    duplicate_filter = [target_name, target_name, target_name]
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=duplicate_filter)

    # Should still return only one instance of the toolset
    assert len(filtered) == 1
    assert filtered[0].name == target_name


def test_load_builtin_toolsets_maintains_order():
    """Test that filtering maintains the original order of toolsets"""
    all_toolsets = load_builtin_toolsets()
    if len(all_toolsets) < 3:
        pytest.skip("Need at least 3 builtin toolsets")

    # Select third then first toolsets (reverse of discovery order)
    target_names = [all_toolsets[2].name, all_toolsets[0].name]
    filtered = load_builtin_toolsets(allowed_builtin_toolsets=target_names)

    assert len(filtered) == 2
    # Should preserve discovery order, not allowlist order
    assert filtered[0].name == all_toolsets[0].name
    assert filtered[1].name == all_toolsets[2].name
