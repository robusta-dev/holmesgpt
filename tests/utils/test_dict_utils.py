"""Unit tests for dict_utils module."""

from holmes.utils.dict_utils import deep_merge


class TestDeepMerge:
    """Test cases for deep_merge function."""

    def test_simple_merge(self):
        """Test basic dictionary merging."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}
        # Ensure original dicts are not modified
        assert base == {"a": 1, "b": 2}
        assert override == {"b": 3, "c": 4}

    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        base = {"level1": {"level2": {"a": 1, "b": 2}, "other": "value"}}
        override = {"level1": {"level2": {"b": 3, "c": 4}}}
        result = deep_merge(base, override)

        assert result == {
            "level1": {
                "level2": {
                    "a": 1,  # Preserved
                    "b": 3,  # Overridden
                    "c": 4,  # Added
                },
                "other": "value",  # Preserved
            }
        }

    def test_list_replacement(self):
        """Test that lists are replaced entirely, not merged."""
        base = {"items": [1, 2, 3], "nested": {"tags": ["a", "b", "c"]}}
        override = {"items": [4, 5], "nested": {"tags": ["x"]}}
        result = deep_merge(base, override)

        assert result == {
            "items": [4, 5],  # Replaced entirely
            "nested": {
                "tags": ["x"]  # Replaced entirely
            },
        }

    def test_none_values(self):
        """Test that None values are preserved."""
        base = {"a": "value", "b": "another", "nested": {"x": 1, "y": 2}}
        override = {
            "a": None,  # Set to None
            "nested": {
                "x": None  # Set to None
            },
        }
        result = deep_merge(base, override)

        assert result == {
            "a": None,
            "b": "another",  # Preserved
            "nested": {
                "x": None,
                "y": 2,  # Preserved
            },
        }

    def test_empty_dicts(self):
        """Test merging with empty dictionaries."""
        base = {"a": 1}

        # Empty override
        result = deep_merge(base, {})
        assert result == {"a": 1}

        # Empty base
        result = deep_merge({}, {"b": 2})
        assert result == {"b": 2}

        # Both empty
        result = deep_merge({}, {})
        assert result == {}

    def test_non_dict_base(self):
        """Test when base is not a dictionary."""
        # Non-dict base should be replaced
        result = deep_merge("not a dict", {"a": 1})
        assert result == {"a": 1}

        result = deep_merge(None, {"a": 1})
        assert result == {"a": 1}

        result = deep_merge(123, {"a": 1})
        assert result == {"a": 1}

    def test_non_dict_override(self):
        """Test when override is not a dictionary."""
        base = {"a": 1}

        # Non-dict override replaces entirely
        result = deep_merge(base, "string value")
        assert result == "string value"

        result = deep_merge(base, None)
        assert result is None

        result = deep_merge(base, 123)
        assert result == 123

    def test_deeply_nested_preservation(self):
        """Test that deeply nested values are preserved when not overridden."""
        base = {
            "level1": {
                "level2": {
                    "level3": {"keep": "this", "change": "old"},
                    "also_keep": "value",
                }
            },
            "top_level": "original",
        }
        override = {"level1": {"level2": {"level3": {"change": "new", "add": "extra"}}}}
        result = deep_merge(base, override)

        assert result == {
            "level1": {
                "level2": {
                    "level3": {
                        "keep": "this",  # Preserved
                        "change": "new",  # Changed
                        "add": "extra",  # Added
                    },
                    "also_keep": "value",  # Preserved
                }
            },
            "top_level": "original",  # Preserved
        }

    def test_mixed_types(self):
        """Test merging with mixed types (dict replacing non-dict and vice versa)."""
        base = {"was_string": "text", "was_dict": {"a": 1}, "stays_dict": {"b": 2}}
        override = {
            "was_string": {"now": "dict"},  # String replaced by dict
            "was_dict": "now string",  # Dict replaced by string
            "stays_dict": {"c": 3},  # Dict merged with dict
        }
        result = deep_merge(base, override)

        assert result == {
            "was_string": {"now": "dict"},
            "was_dict": "now string",
            "stays_dict": {"b": 2, "c": 3},
        }

    def test_real_world_config_scenario(self):
        """Test a realistic configuration merging scenario."""
        default_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "admin", "password": "default123"},
                "pool": {"min": 1, "max": 10, "timeout": 30},
            },
            "logging": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "features": {"cache": True, "metrics": False},
        }

        production_override = {
            "database": {
                "host": "prod-db.example.com",
                "credentials": {"password": "prod-secret-123"},
                "pool": {"min": 5, "max": 50},
            },
            "logging": {
                "level": "WARNING",
                "handlers": ["syslog"],  # Replace handlers entirely
            },
            "features": {
                "metrics": True  # Enable metrics in prod
            },
        }

        result = deep_merge(default_config, production_override)

        # Check merged result
        assert result["database"]["host"] == "prod-db.example.com"
        assert result["database"]["port"] == 5432  # Preserved
        assert result["database"]["credentials"]["username"] == "admin"  # Preserved
        assert result["database"]["credentials"]["password"] == "prod-secret-123"
        assert result["database"]["pool"]["min"] == 5
        assert result["database"]["pool"]["max"] == 50
        assert result["database"]["pool"]["timeout"] == 30  # Preserved

        assert result["logging"]["level"] == "WARNING"
        assert result["logging"]["handlers"] == ["syslog"]  # Replaced entirely
        assert "format" in result["logging"]  # Preserved

        assert result["features"]["cache"] is True  # Preserved
        assert result["features"]["metrics"] is True  # Overridden
