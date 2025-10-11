"""Critical end-to-end tests for toolset configuration architecture.

These tests use REAL toolset classes and manager without mocking the core behavior.
We only mock external dependencies like network/subprocess calls.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
import pytest
import yaml

from holmes.core.tools import (
    YAMLToolset,
    ToolsetStatusEnum,
    ToolsetTag,
    CallablePrerequisite,
    ToolsetCommandPrerequisite,
)
from holmes.core.toolset_manager import ToolsetManager
from holmes.plugins.toolsets import load_builtin_toolsets


class TestConfigFieldPresenceBehavior:
    """Test how different config field values affect builtin toolsets."""

    def test_missing_config_field_preserves_builtin_config(self):
        """When config field is not present, builtin config should be untouched."""
        # Use REAL builtin toolsets
        builtin_toolsets = load_builtin_toolsets()

        # Find a toolset with default config
        prometheus = next(
            (t for t in builtin_toolsets if t.name == "prometheus/metrics"), None
        )
        if not prometheus:
            pytest.skip("Prometheus toolset not found")

        original_config = prometheus.config.copy() if prometheus.config else None

        # Config that enables prometheus but doesn't specify config field
        config = {
            "toolsets": {
                "prometheus/metrics": {
                    "enabled": True
                    # Note: NO config field at all
                }
            }
        }

        manager = ToolsetManager(
            tags=[], config=config, default_enabled=False, suppress_logging=True
        )

        result = manager.registry.toolsets.get("prometheus/metrics")
        assert result is not None
        assert result.enabled is True
        # Config should be completely unchanged
        assert result.config == original_config

    def test_null_config_field_behavior(self):
        """Test that config: null is handled correctly."""
        builtin_toolsets = load_builtin_toolsets()
        grafana = next(
            (t for t in builtin_toolsets if t.name == "grafana/grafana"), None
        )
        if not grafana:
            pytest.skip("Grafana toolset not found")

        config = {
            "toolsets": {
                "grafana/grafana": {
                    "enabled": True,
                    "config": None,  # Explicitly null
                }
            }
        }

        manager = ToolsetManager(
            tags=[], config=config, default_enabled=False, suppress_logging=True
        )

        result = manager.registry.toolsets.get("grafana/grafana")
        # With our current implementation, None should replace the config
        assert result.config is None

    def test_empty_dict_config_preserves_defaults(self):
        """Test that config: {} preserves default values."""
        builtin_toolsets = load_builtin_toolsets()
        datadog = next(
            (t for t in builtin_toolsets if t.name == "datadog/metrics"), None
        )
        if not datadog:
            pytest.skip("Datadog toolset not found")

        original_config = datadog.config.copy() if datadog.config else {}

        config = {
            "toolsets": {
                "datadog/metrics": {
                    "enabled": True,
                    "config": {},  # Empty dict - should preserve defaults
                }
            }
        }

        manager = ToolsetManager(
            tags=[], config=config, default_enabled=False, suppress_logging=True
        )

        result = manager.registry.toolsets.get("datadog/metrics")
        # Empty dict merged with original should preserve original
        assert result.config == original_config

    def test_partial_config_merges_correctly(self):
        """Test that partial config merges with defaults."""
        # Create a custom builtin-like toolset with known config
        test_toolset = YAMLToolset(
            name="test-service",
            description="Test service",
            tools=[],
            enabled=False,
            config={
                "url": "https://default.example.com",
                "port": 8080,
                "timeout": 30,
                "features": ["feature1", "feature2"],
            },
        )

        with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
            mock_load.return_value = [test_toolset]

            config = {
                "toolsets": {
                    "test-service": {
                        "enabled": True,
                        "config": {
                            "url": "https://custom.example.com",  # Override
                            "timeout": 60,  # Override
                            # port not specified - should keep default
                            # features not specified - should keep default
                        },
                    }
                }
            }

            manager = ToolsetManager(
                tags=[], config=config, default_enabled=False, suppress_logging=True
            )

            result = manager.registry.toolsets["test-service"]
            assert result.enabled is True
            assert result.config["url"] == "https://custom.example.com"
            assert result.config["timeout"] == 60
            assert result.config["port"] == 8080  # Preserved
            assert result.config["features"] == ["feature1", "feature2"]  # Preserved


class TestDefaultEnabledVsExplicitSettings:
    """Test interaction between default_enabled and explicit settings."""

    def test_explicit_disabled_overrides_default_enabled_true(self):
        """Explicitly disabled toolsets stay disabled even with default_enabled=True."""
        # Use real builtin toolsets
        builtin_toolsets = load_builtin_toolsets()

        # Find a few toolsets to test with
        test_names = ["kubernetes/core", "prometheus/metrics", "grafana/grafana"]
        available = [
            name for name in test_names if any(t.name == name for t in builtin_toolsets)
        ]

        if len(available) < 2:
            pytest.skip("Not enough test toolsets available")

        config = {
            "toolsets": {
                available[0]: {"enabled": False},  # Explicitly disabled
                available[1]: {"enabled": True},  # Explicitly enabled
                # available[2] if exists - not mentioned, should use default_enabled
            }
        }

        # default_enabled=True should not override explicit settings
        manager = ToolsetManager(
            tags=[],
            config=config,
            default_enabled=True,  # This is True!
            suppress_logging=True,
        )

        assert (
            manager.registry.toolsets[available[0]].enabled is False
        )  # Stays disabled
        assert manager.registry.toolsets[available[1]].enabled is True  # Stays enabled

        if len(available) > 2:
            # Not configured one should use default_enabled
            other_toolset = next(
                (
                    t
                    for t in manager.registry.toolsets.values()
                    if t.name not in [available[0], available[1]]
                ),
                None,
            )
            if other_toolset:
                assert other_toolset.enabled is True  # Uses default_enabled


class TestMixedSourceLoading:
    """Test loading from builtin, custom files, and MCP servers together."""

    def test_all_three_sources_work_together(self):
        """Test builtin config + custom YAML + MCP server all work together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a custom toolset file
            custom_file = Path(tmpdir) / "custom.yaml"
            custom_data = {
                "toolsets": {
                    "my-custom-monitor": {
                        "description": "Custom monitoring tool",
                        "tools": [
                            {
                                "name": "check_status",
                                "description": "Check service status",
                                "command": "echo 'checking status'",
                            }
                        ],
                        "enabled": True,
                        "config": {"custom_url": "http://monitor.local"},
                    }
                }
            }
            custom_file.write_text(yaml.dump(custom_data))

            # Config with builtin override and MCP server
            config = {
                "toolsets": {
                    "kubernetes/core": {
                        "enabled": True,
                        "config": {"custom_param": "test"},
                    }
                },
                "mcp_servers": {
                    "test-mcp-server": {
                        "url": "http://localhost:8000/sse",
                        "description": "Test MCP server",
                        "config": {"api_key": "test-key"},
                    }
                },
            }

            manager = ToolsetManager(
                tags=[],
                config=config,
                custom_toolset_paths=[custom_file],
                default_enabled=False,
                suppress_logging=True,
            )

            # Check all three exist
            assert "kubernetes/core" in manager.registry.toolsets
            assert "my-custom-monitor" in manager.registry.toolsets
            assert "test-mcp-server" in manager.registry.toolsets

            # Verify types and configs
            k8s = manager.registry.toolsets["kubernetes/core"]
            assert k8s.enabled is True
            if k8s.config:
                assert k8s.config.get("custom_param") == "test"

            custom = manager.registry.toolsets["my-custom-monitor"]
            assert custom.enabled is True
            assert custom.config["custom_url"] == "http://monitor.local"
            assert len(custom.tools) == 1

            mcp = manager.registry.toolsets["test-mcp-server"]
            assert mcp.type.value == "mcp"
            assert mcp.config["api_key"] == "test-key"

    def test_custom_cannot_override_builtin_names(self):
        """Test that custom toolsets cannot use builtin names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_file = Path(tmpdir) / "custom.yaml"
            custom_data = {
                "toolsets": {
                    "kubernetes/core": {  # This is a builtin name!
                        "description": "My fake kubernetes",
                        "tools": [],
                        "enabled": True,
                    },
                    "my-valid-custom": {
                        "description": "Valid custom toolset",
                        "tools": [],
                        "enabled": True,
                    },
                }
            }
            custom_file.write_text(yaml.dump(custom_data))

            # Should raise error about conflict
            with pytest.raises(ValueError) as exc_info:
                ToolsetManager(
                    tags=[],
                    config={},
                    custom_toolset_paths=[custom_file],
                    default_enabled=False,
                    suppress_logging=True,
                )

            assert "conflict with builtin toolsets" in str(exc_info.value)
            assert "kubernetes/core" in str(exc_info.value)


class TestEnvironmentVariableSubstitution:
    """Test environment variable substitution in configs."""

    def test_env_vars_in_deeply_nested_config(self):
        """Test that env vars work in deeply nested configuration."""
        # Set up test environment variables
        os.environ["TEST_DB_HOST"] = "db.production.example.com"
        os.environ["TEST_DB_PASS"] = "super-secret-password"
        os.environ["TEST_DB_PORT"] = "5432"
        os.environ["TEST_API_KEY"] = "api-key-12345"

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                custom_file = Path(tmpdir) / "custom.yaml"
                custom_data = {
                    "toolsets": {
                        "database-monitor": {
                            "description": "Database monitoring",
                            "tools": [],
                            "enabled": True,
                            "config": {
                                "database": {
                                    "primary": {
                                        "host": "{{env.TEST_DB_HOST}}",
                                        "port": "{{env.TEST_DB_PORT}}",
                                        "auth": {
                                            "password": "{{env.TEST_DB_PASS}}",
                                            "api_key": "{{env.TEST_API_KEY}}",
                                        },
                                    },
                                    "replica": {
                                        "host": "{{env.TEST_DB_HOST}}",  # Same var used twice
                                        "port": "{{env.TEST_DB_PORT}}",
                                    },
                                },
                                "monitoring": {
                                    "api_key": "{{env.TEST_API_KEY}}"  # Same var used third time
                                },
                            },
                        }
                    }
                }
                custom_file.write_text(yaml.dump(custom_data))

                manager = ToolsetManager(
                    tags=[],
                    config={},
                    custom_toolset_paths=[custom_file],
                    default_enabled=False,
                    suppress_logging=True,
                )

                toolset = manager.registry.toolsets["database-monitor"]

                # Verify all substitutions worked
                assert (
                    toolset.config["database"]["primary"]["host"]
                    == "db.production.example.com"
                )
                assert toolset.config["database"]["primary"]["port"] == "5432"
                assert (
                    toolset.config["database"]["primary"]["auth"]["password"]
                    == "super-secret-password"
                )
                assert (
                    toolset.config["database"]["primary"]["auth"]["api_key"]
                    == "api-key-12345"
                )
                assert (
                    toolset.config["database"]["replica"]["host"]
                    == "db.production.example.com"
                )
                assert toolset.config["monitoring"]["api_key"] == "api-key-12345"

        finally:
            # Clean up environment
            for key in ["TEST_DB_HOST", "TEST_DB_PASS", "TEST_DB_PORT", "TEST_API_KEY"]:
                if key in os.environ:
                    del os.environ[key]


class TestPrerequisitesWithMergedConfig:
    """Test that prerequisites see and use the merged configuration."""

    def test_callable_prerequisite_sees_merged_config(self):
        """Test that callable prerequisites get the final merged config."""

        def check_api_url(config_dict):
            """Prerequisite that checks if API URL is valid."""
            if not config_dict:
                return False, "No config provided"
            url = config_dict.get("api_url", "")
            if url.startswith("https://valid."):
                return True, None
            return False, f"Invalid API URL: {url}"

        # Create a toolset with a prerequisite that checks config
        test_toolset = YAMLToolset(
            name="api-service",
            description="API service",
            tools=[],
            enabled=True,
            config={
                "api_url": "https://default.example.com",  # Default would fail
                "api_key": "default-key",
                "timeout": 30,
            },
            prerequisites=[CallablePrerequisite(callable=check_api_url)],
        )

        with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
            mock_load.return_value = [test_toolset]

            # Override config to make prerequisite pass
            config = {
                "toolsets": {
                    "api-service": {
                        "config": {
                            "api_url": "https://valid.example.com",  # This should pass
                            # Other fields not overridden
                        }
                    }
                }
            }

            manager = ToolsetManager(
                tags=[], config=config, default_enabled=False, suppress_logging=True
            )

            toolset = manager.registry.toolsets["api-service"]

            # Verify config was merged
            assert toolset.config["api_url"] == "https://valid.example.com"
            assert toolset.config["api_key"] == "default-key"  # Preserved
            assert toolset.config["timeout"] == 30  # Preserved

            # Check prerequisites with merged config
            toolset.check_prerequisites(quiet=True)
            assert toolset.status == ToolsetStatusEnum.ENABLED

    @patch("subprocess.run")
    def test_command_prerequisite_with_config_values(self, mock_run):
        """Test command prerequisites can use config values."""
        # Mock successful command execution
        mock_run.return_value = Mock(returncode=0, stdout="success", stderr="")

        test_toolset = YAMLToolset(
            name="cli-tool",
            description="CLI tool",
            tools=[],
            enabled=True,
            config={"binary_path": "/usr/local/bin/tool", "version": "1.0"},
            prerequisites=[
                ToolsetCommandPrerequisite(
                    command="{{config.binary_path}} --version",
                    expected_output="{{config.version}}",
                )
            ],
        )

        with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
            mock_load.return_value = [test_toolset]

            # Override the binary path
            config = {
                "toolsets": {
                    "cli-tool": {
                        "config": {
                            "binary_path": "/opt/custom/tool",
                            # version not overridden
                        }
                    }
                }
            }

            manager = ToolsetManager(
                tags=[], config=config, default_enabled=False, suppress_logging=True
            )

            toolset = manager.registry.toolsets["cli-tool"]

            # Verify merged config
            assert toolset.config["binary_path"] == "/opt/custom/tool"
            assert toolset.config["version"] == "1.0"

            # Prerequisites should use the merged config
            # The command should be interpolated with merged values
            # We can't easily test the interpolation without diving into internals
            # but we can verify the prerequisite check works
            mock_run.return_value.stdout = "1.0"  # Match expected version
            toolset.check_prerequisites(quiet=True)

            # Should have called subprocess with interpolated command
            assert mock_run.called


class TestCacheAndUserOverrideInteraction:
    """Test that user overrides always win over cached status."""

    def test_user_disable_overrides_cached_enabled_status(self):
        """Test that user setting enabled:false overrides cached ENABLED status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test_cache.json"

            # Create a test toolset that would pass prerequisites
            test_toolset = YAMLToolset(
                name="cached-tool",
                description="Tool that gets cached",
                tools=[],
                enabled=True,  # Initially enabled
                config={"test": "value"},
                prerequisites=[],  # No prerequisites, so it will be ENABLED
            )

            with patch(
                "holmes.core.toolset_manager.load_builtin_toolsets"
            ) as mock_load:
                mock_load.return_value = [test_toolset]

                # First run: toolset is enabled and passes prerequisites
                manager1 = ToolsetManager(
                    tags=[ToolsetTag.CORE],  # Match the default toolset tag
                    config={},  # No override
                    cache_path=cache_path,
                    default_enabled=False,
                    suppress_logging=True,
                )

                # Load without cache to generate it
                toolsets1 = manager1.load(use_cache=False, include_disabled=True)

                # The toolset should be in the registry after load
                cached_tool1 = manager1.registry.toolsets.get("cached-tool")
                assert cached_tool1 is not None
                assert cached_tool1.enabled is True

                # Check the actual loaded/checked version
                loaded_cached = next(
                    (t for t in toolsets1 if t.name == "cached-tool"), None
                )
                assert loaded_cached is not None
                assert loaded_cached.status == ToolsetStatusEnum.ENABLED

                # Verify cache was created
                assert cache_path.exists()
                with open(cache_path) as f:
                    cache_data = json.load(f)
                    assert "cached-tool" in cache_data.get("toolsets", {})
                    assert cache_data["toolsets"]["cached-tool"]["status"] == "enabled"

                # Second run: user explicitly disables the toolset
                config_with_disable = {
                    "toolsets": {
                        "cached-tool": {
                            "enabled": False  # User says: disable this!
                        }
                    }
                }

                # Create new instance of the toolset for second manager
                test_toolset2 = YAMLToolset(
                    name="cached-tool",
                    description="Tool that gets cached",
                    tools=[],
                    enabled=True,  # Default is enabled
                    config={"test": "value"},
                    prerequisites=[],
                )
                mock_load.return_value = [test_toolset2]

                manager2 = ToolsetManager(
                    tags=[ToolsetTag.CORE],  # Match the default toolset tag
                    config=config_with_disable,
                    cache_path=cache_path,
                    default_enabled=False,
                    suppress_logging=True,
                )

                # Even though cache says ENABLED, user override should win
                toolsets2 = manager2.load(use_cache=True, include_disabled=True)
                cached_tool2 = next(
                    (t for t in toolsets2 if t.name == "cached-tool"), None
                )
                assert cached_tool2 is not None
                assert cached_tool2.enabled is False  # User override wins!

                # The toolset should not be in the enabled list
                enabled_only = manager2.load(use_cache=True, include_disabled=False)
                assert not any(t.name == "cached-tool" for t in enabled_only)

    def test_cache_invalidation_on_config_change(self):
        """Test that cache properly invalidates when configuration changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test_cache.json"

            test_toolset = YAMLToolset(
                name="config-test",
                description="Config test tool",
                tools=[],
                enabled=True,
                config={"url": "http://default.com"},
                prerequisites=[],
            )

            with patch(
                "holmes.core.toolset_manager.load_builtin_toolsets"
            ) as mock_load:
                mock_load.return_value = [test_toolset]

                # First load with one config
                config1 = {
                    "toolsets": {"config-test": {"config": {"url": "http://first.com"}}}
                }

                manager1 = ToolsetManager(
                    tags=[],
                    config=config1,
                    cache_path=cache_path,
                    default_enabled=False,
                    suppress_logging=True,
                )

                manager1.load(use_cache=False)  # Generate cache

                # Second load with different config
                config2 = {
                    "toolsets": {
                        "config-test": {"config": {"url": "http://second.com"}}
                    }
                }

                # Reset the toolset for second manager
                test_toolset2 = YAMLToolset(
                    name="config-test",
                    description="Config test tool",
                    tools=[],
                    enabled=True,
                    config={"url": "http://default.com"},
                    prerequisites=[],
                )
                mock_load.return_value = [test_toolset2]

                manager2 = ToolsetManager(
                    tags=[],
                    config=config2,
                    cache_path=cache_path,
                    default_enabled=False,
                    suppress_logging=True,
                )

                # Should detect config change and invalidate cache
                toolsets2 = manager2.load(use_cache=True)
                config_test = next(
                    (t for t in toolsets2 if t.name == "config-test"), None
                )

                if config_test:
                    # The new config should be applied
                    assert config_test.config["url"] == "http://second.com"
