"""Test that configuration merging uses Helm-style deep merge."""

from unittest.mock import patch

from holmes.core.toolset_manager import ToolsetManager
from holmes.core.tools import ToolsetTag, YAMLToolset


def test_helm_style_deep_merge():
    """Test that nested configs are deep merged like Helm values."""

    # Create a builtin toolset with nested config
    builtin = YAMLToolset(
        name="database-tool",
        description="Database tool",
        tools=[],
        config={
            "connection": {
                "host": "localhost",
                "port": 3306,
                "timeout": 30,
                "credentials": {
                    "username": "admin",
                    "password": "default-pass",
                    "database": "mydb",
                },
                "options": {"ssl": True, "poolSize": 10},
            },
            "monitoring": {"enabled": True, "interval": 60},
        },
        tags=[ToolsetTag.CORE],
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [builtin]

        # User provides partial overrides
        config = {
            "toolsets": {
                "database-tool": {
                    "enabled": True,
                    "config": {
                        "connection": {
                            "host": "prod.example.com",
                            "port": 5432,  # Different port
                            # timeout not specified - should keep default
                            "credentials": {
                                "password": "secret123",
                                # username and database not specified - should keep defaults
                            },
                            # options not specified - should keep defaults
                        },
                        # monitoring not specified - should keep defaults
                    },
                }
            }
        }

        manager = ToolsetManager(
            tags=[ToolsetTag.CORE],
            config=config,
            default_enabled=False,
            suppress_logging=True,
        )

        toolset = manager.registry.toolsets["database-tool"]

        # Check deep merge results
        assert toolset.enabled is True

        # First level overrides
        assert toolset.config["connection"]["host"] == "prod.example.com"
        assert toolset.config["connection"]["port"] == 5432

        # First level preserved
        assert toolset.config["connection"]["timeout"] == 30

        # Second level overrides
        assert toolset.config["connection"]["credentials"]["password"] == "secret123"

        # Second level preserved
        assert toolset.config["connection"]["credentials"]["username"] == "admin"
        assert toolset.config["connection"]["credentials"]["database"] == "mydb"

        # Entire nested object preserved when not mentioned
        assert toolset.config["connection"]["options"]["ssl"] is True
        assert toolset.config["connection"]["options"]["poolSize"] == 10

        # Top level object preserved when not mentioned
        assert toolset.config["monitoring"]["enabled"] is True
        assert toolset.config["monitoring"]["interval"] == 60


def test_deep_merge_with_lists():
    """Test that lists are replaced entirely, not merged."""

    builtin = YAMLToolset(
        name="monitoring-tool",
        description="Monitoring tool",
        tools=[],
        config={
            "targets": ["server1", "server2", "server3"],
            "metrics": {"cpu": ["usage", "load"], "memory": ["used", "free", "cached"]},
        },
        tags=[ToolsetTag.CORE],
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [builtin]

        config = {
            "toolsets": {
                "monitoring-tool": {
                    "enabled": True,
                    "config": {
                        "targets": ["prod1", "prod2"],  # Replace entire list
                        "metrics": {
                            "cpu": ["usage"],  # Replace entire list
                            # memory not specified - should keep default list
                        },
                    },
                }
            }
        }

        manager = ToolsetManager(
            tags=[ToolsetTag.CORE],
            config=config,
            default_enabled=False,
            suppress_logging=True,
        )

        toolset = manager.registry.toolsets["monitoring-tool"]

        # Lists are replaced entirely
        assert toolset.config["targets"] == ["prod1", "prod2"]
        assert toolset.config["metrics"]["cpu"] == ["usage"]

        # Unspecified lists are preserved
        assert toolset.config["metrics"]["memory"] == ["used", "free", "cached"]


def test_deep_merge_with_none_values():
    """Test that None values in config are handled properly."""

    builtin = YAMLToolset(
        name="api-tool",
        description="API tool",
        tools=[],
        config={"auth": {"token": "default-token", "username": "admin"}, "timeout": 30},
        tags=[ToolsetTag.CORE],
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [builtin]

        # Test with explicit None - should replace the value
        config = {
            "toolsets": {
                "api-tool": {
                    "enabled": True,
                    "config": {
                        "auth": {
                            "token": None,  # Explicitly set to None
                            # username not specified - should keep default
                        }
                    },
                }
            }
        }

        manager = ToolsetManager(
            tags=[ToolsetTag.CORE],
            config=config,
            default_enabled=False,
            suppress_logging=True,
        )

        toolset = manager.registry.toolsets["api-tool"]

        # None value is preserved - explicit "no value"
        assert toolset.config["auth"]["token"] is None

        # Other values preserved
        assert toolset.config["auth"]["username"] == "admin"
        assert toolset.config["timeout"] == 30
