import pytest
from unittest.mock import patch
from holmes.config import Config
from holmes.core.toolset_manager import ToolsetManager
from holmes.plugins.toolsets import load_builtin_toolsets
from holmes.core.tools import ToolsetType


class TestAllowedBuiltinToolsetsIntegration:
    """Comprehensive integration tests for the complete feature"""

    def test_full_backward_compatibility(self):
        """Test that all existing functionality works unchanged"""
        # Test default behavior
        config_default = Config()
        manager_default = ToolsetManager(config=config_default)
        toolsets_default = manager_default._list_all_toolsets()

        # Test explicit None
        config_none = Config(allowed_builtin_toolsets=None)
        manager_none = ToolsetManager(config=config_none)
        toolsets_none = manager_none._list_all_toolsets()

        # Should be identical
        assert len(toolsets_default) == len(toolsets_none)
        assert {t.name for t in toolsets_default} == {t.name for t in toolsets_none}

    def test_error_handling(self):
        """Test error handling for malformed input"""
        # Test various edge cases that shouldn't crash
        test_cases = [
            [],  # Empty list
            [""],  # Empty string in list
            ["  "],  # Whitespace only
            ["invalid/toolset"],  # Non-existent toolset
            ["kubernetes/core", "", "prometheus/core"],  # Mixed valid/invalid
        ]

        for test_case in test_cases:
            config = Config(allowed_builtin_toolsets=test_case)
            manager = ToolsetManager(config=config)
            # Should not raise exception
            toolsets = manager._list_all_toolsets()
            assert isinstance(toolsets, list)

    @pytest.mark.slow
    def test_all_builtin_toolsets_individually(self):
        """Test that each builtin toolset can be filtered individually"""
        all_toolsets = load_builtin_toolsets()
        if not all_toolsets:
            pytest.skip("no builtin toolsets discovered")

        for toolset in all_toolsets:
            config = Config(allowed_builtin_toolsets=[toolset.name])
            manager = ToolsetManager(config=config)
            filtered_toolsets = manager._list_all_toolsets()

            builtin_filtered = [
                t for t in filtered_toolsets if t.type == ToolsetType.BUILTIN
            ]
            assert len(builtin_filtered) == 1
            assert builtin_filtered[0].name == toolset.name

    def test_config_validation(self):
        """Test that Config field validation works correctly"""
        # Test that empty strings and whitespace are filtered out
        config = Config(
            allowed_builtin_toolsets=["kubernetes/core", "", "  ", "prometheus/core"]
        )
        # Validation should filter out empty/whitespace strings
        expected = ["kubernetes/core", "prometheus/core"]
        assert config.allowed_builtin_toolsets == expected

        # Test that all empty results in empty list (not None)
        config_empty = Config(allowed_builtin_toolsets=["", "  "])
        assert config_empty.allowed_builtin_toolsets == []

    def test_warning_for_invalid_toolsets(self):
        """Test that warnings are logged for invalid toolset names"""
        # Test with invalid toolset names
        with patch("holmes.plugins.toolsets.logging.warning") as mock_warning:
            config = Config(
                allowed_builtin_toolsets=["nonexistent/toolset", "another/fake"]
            )
            manager = ToolsetManager(config=config)
            manager._list_all_toolsets()  # This will trigger the filtering

            # Should have called warning about invalid names
            mock_warning.assert_called()
            # Check the last call for the expected message content
            last_call_args = mock_warning.call_args[0][0]
            assert "Unknown builtin toolsets specified" in last_call_args
            assert "nonexistent/toolset" in last_call_args
            assert "another/fake" in last_call_args

    def test_warning_partial_invalid_toolsets(self):
        """Test warnings when some toolsets are valid and some invalid"""
        all_toolsets = load_builtin_toolsets()
        if not all_toolsets:
            pytest.skip("No builtin toolsets available")

        valid_name = all_toolsets[0].name
        invalid_names = ["nonexistent/toolset"]

        with patch("holmes.plugins.toolsets.logging.warning") as mock_warning:
            config = Config(allowed_builtin_toolsets=[valid_name] + invalid_names)
            manager = ToolsetManager(config=config)
            filtered_toolsets = manager._list_all_toolsets()

            # Should warn about invalid names
            assert mock_warning.called
            warning_message = mock_warning.call_args[0][0]
            assert "Unknown builtin toolsets specified" in warning_message
            assert "nonexistent/toolset" in warning_message

            # But should still include valid toolset
            builtin_filtered = [
                t for t in filtered_toolsets if t.type == ToolsetType.BUILTIN
            ]
            assert len(builtin_filtered) == 1
            assert builtin_filtered[0].name == valid_name

    def test_no_warning_for_valid_toolsets(self):
        """Test that no warnings are logged for valid toolset names"""
        all_toolsets = load_builtin_toolsets()
        if not all_toolsets:
            pytest.skip("No builtin toolsets available")

        valid_name = all_toolsets[0].name

        with patch("logging.warning") as mock_warning:
            config = Config(allowed_builtin_toolsets=[valid_name])
            manager = ToolsetManager(config=config)
            manager._list_all_toolsets()

            # Should not have called warning about unknown toolsets specifically
            assert not any(
                "Unknown builtin toolsets specified" in str(args[0])
                if args
                else False
                or "Unknown builtin toolsets specified" in kwargs.get("msg", "")
                for args, kwargs in mock_warning.call_args_list
            )

    def test_filtering_preserves_toolset_order(self):
        """Test that filtering maintains the original order of toolsets"""
        all_toolsets = load_builtin_toolsets()
        if len(all_toolsets) < 3:
            pytest.skip("Need at least 3 toolsets for order test")

        # Select first and third toolsets
        target_names = [all_toolsets[0].name, all_toolsets[2].name]

        config = Config(allowed_builtin_toolsets=target_names)
        manager = ToolsetManager(config=config)
        filtered_toolsets = manager._list_all_toolsets()
        builtin_filtered = [
            t for t in filtered_toolsets if t.type == ToolsetType.BUILTIN
        ]

        # Should maintain original order
        assert len(builtin_filtered) == 2
        assert builtin_filtered[0].name == all_toolsets[0].name
        assert builtin_filtered[1].name == all_toolsets[2].name

    def test_config_cli_parsing_integration(self):
        """Test integration between CLI parsing and Config validation"""
        # Test that CLI parsing + validation works together
        config = Config.load_from_file(
            None, allowed_builtin_toolsets="kubernetes/core, , prometheus/core,  "
        )

        # Should parse comma-separated string and validate
        expected = ["kubernetes/core", "prometheus/core"]
        assert config.allowed_builtin_toolsets == expected

    def test_empty_filter_behavior(self):
        """Test behavior when filter results in empty list"""
        config = Config(allowed_builtin_toolsets=[])
        manager = ToolsetManager(config=config)
        filtered_toolsets = manager._list_all_toolsets()
        builtin_filtered = [
            t for t in filtered_toolsets if t.type == ToolsetType.BUILTIN
        ]

        # Should have no builtin toolsets
        assert len(builtin_filtered) == 0

        # But other types should still be present
        non_builtin = [t for t in filtered_toolsets if t.type != ToolsetType.BUILTIN]
        # The count depends on what's configured, but should not crash
        assert isinstance(non_builtin, list)

    def test_toolset_manager_caching_with_filter(self):
        """Test that Config caches ToolsetManager correctly with filtering"""
        config = Config(allowed_builtin_toolsets=["kubernetes/core"])

        # Access toolset_manager multiple times
        manager1 = config.toolset_manager
        manager2 = config.toolset_manager

        # Should be same instance (cached)
        assert manager1 is manager2

        # Both should have same config reference
        assert manager1._config is config
        assert manager2._config is config

    def test_console_and_server_toolset_filtering(self):
        """Test that console and server toolset methods respect filtering"""
        all_toolsets = load_builtin_toolsets()
        if not all_toolsets:
            pytest.skip("No builtin toolsets available")

        target_name = all_toolsets[0].name
        config = Config(allowed_builtin_toolsets=[target_name])
        manager = ToolsetManager(config=config)

        # Test console toolsets
        console_toolsets = manager.list_console_toolsets()
        console_builtin = [t for t in console_toolsets if t.type == ToolsetType.BUILTIN]

        # Should only include allowed toolsets (filtered by both tags and allowed list)
        for toolset in console_builtin:
            assert toolset.name == target_name

        # Test server toolsets
        server_toolsets = manager.list_server_toolsets()
        server_builtin = [t for t in server_toolsets if t.type == ToolsetType.BUILTIN]

        # Should only include allowed toolsets (filtered by both tags and allowed list)
        for toolset in server_builtin:
            assert toolset.name == target_name

    def test_feature_robustness(self):
        """Test that feature is robust to various edge cases"""
        edge_cases = [
            None,  # None value
            [],  # Empty list
            [""],  # List with empty string
            ["kubernetes/core"] * 5,  # Duplicate names
            ["KUBERNETES/CORE"],  # Wrong case (should not match)
            ["kubernetes/core/extra"],  # Extra path components
        ]

        for case in edge_cases:
            try:
                config = Config(allowed_builtin_toolsets=case)
                manager = ToolsetManager(config=config)
                toolsets = manager._list_all_toolsets()
                # Should not crash and return a list
                assert isinstance(toolsets, list)
            except Exception as e:
                pytest.fail(
                    f"Feature should be robust to edge case {case}, but got: {e}"
                )
