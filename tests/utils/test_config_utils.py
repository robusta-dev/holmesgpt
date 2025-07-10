"""
Tests for configuration utility functions.
"""

from holmes.utils.config_utils import merge_transformer_configs


def test_merge_transformer_configs_both_none():
    """Test that merging None configs returns None."""
    result = merge_transformer_configs(None, None)
    assert result is None


def test_merge_transformer_configs_base_none():
    """Test that when base is None, override configs are returned."""
    override = [{"llm_summarize": {"input_threshold": 1000}}]
    result = merge_transformer_configs(None, override)
    assert result == override


def test_merge_transformer_configs_override_none():
    """Test that when override is None, base configs are returned."""
    base = [{"llm_summarize": {"fast_model": "gpt-4o-mini"}}]
    result = merge_transformer_configs(base, None)
    assert result == base


def test_merge_transformer_configs_both_empty():
    """Test that merging empty lists returns None."""
    result = merge_transformer_configs([], [])
    assert result is None


def test_merge_transformer_configs_field_level_merge():
    """Test field-level merging with precedence."""
    base = [{"llm_summarize": {"fast_model": "gpt-4o-mini", "input_threshold": 500}}]
    override = [{"llm_summarize": {"input_threshold": 1000, "prompt": "Custom"}}]

    result = merge_transformer_configs(base, override)

    expected = [
        {
            "llm_summarize": {
                "fast_model": "gpt-4o-mini",  # From base
                "input_threshold": 1000,  # Override wins
                "prompt": "Custom",  # From override
            }
        }
    ]

    assert result == expected


def test_merge_transformer_configs_different_types():
    """Test merging different transformer types."""
    base = [{"llm_summarize": {"fast_model": "gpt-4o-mini"}}]
    override = [{"custom_transformer": {"param": "value"}}]

    result = merge_transformer_configs(base, override)

    # Order might vary, so check both types are present
    result_types = set()
    for config in result:
        result_types.update(config.keys())

    assert "llm_summarize" in result_types
    assert "custom_transformer" in result_types
    assert len(result) == 2


def test_merge_transformer_configs_multiple_base_configs():
    """Test merging with multiple configs in base list."""
    base = [
        {"llm_summarize": {"fast_model": "gpt-4o-mini"}},
        {"custom_transformer": {"param": "base_value"}},
    ]
    override = [{"llm_summarize": {"input_threshold": 1000}}]

    result = merge_transformer_configs(base, override)

    # Check that llm_summarize was merged and custom_transformer was preserved
    result_dict = {}
    for config in result:
        result_dict.update(config)

    assert result_dict["llm_summarize"]["fast_model"] == "gpt-4o-mini"
    assert result_dict["llm_summarize"]["input_threshold"] == 1000
    assert result_dict["custom_transformer"]["param"] == "base_value"


def test_merge_transformer_configs_override_precedence():
    """Test that override configs take precedence for existing fields."""
    base = [
        {
            "llm_summarize": {
                "fast_model": "gpt-4o-mini",
                "input_threshold": 500,
                "prompt": "Base prompt",
            }
        }
    ]
    override = [
        {"llm_summarize": {"input_threshold": 2000, "prompt": "Override prompt"}}
    ]

    result = merge_transformer_configs(base, override)

    expected = [
        {
            "llm_summarize": {
                "fast_model": "gpt-4o-mini",  # From base (not overridden)
                "input_threshold": 2000,  # Override wins
                "prompt": "Override prompt",  # Override wins
            }
        }
    ]

    assert result == expected


def test_merge_transformer_configs_complex_scenario():
    """Test complex merging scenario with multiple types and configs."""
    base = [
        {"llm_summarize": {"fast_model": "gpt-4o-mini", "input_threshold": 500}},
        {"data_filter": {"max_items": 100}},
    ]
    override = [
        {"llm_summarize": {"input_threshold": 1000, "prompt": "Custom"}},
        {"result_formatter": {"format": "json"}},
    ]

    result = merge_transformer_configs(base, override)

    # Convert to dict for easier assertions
    result_dict = {}
    for config in result:
        result_dict.update(config)

    # Check llm_summarize was merged properly
    assert result_dict["llm_summarize"]["fast_model"] == "gpt-4o-mini"  # From base
    assert result_dict["llm_summarize"]["input_threshold"] == 1000  # Override
    assert result_dict["llm_summarize"]["prompt"] == "Custom"  # Override

    # Check other types were preserved
    assert result_dict["data_filter"]["max_items"] == 100
    assert result_dict["result_formatter"]["format"] == "json"

    # Should have 3 transformer types
    assert len(result_dict) == 3
