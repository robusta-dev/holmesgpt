"""Tests for the new toolset configuration override behavior."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import yaml

from holmes.core.tools import (
    Toolset,
    ToolsetStatusEnum,
    YAMLToolset,
    CallablePrerequisite,
    ToolsetEnvironmentPrerequisite,
)
from holmes.core.toolset_manager import ToolsetManager


class TestBuiltinToolsetConfigOverride:
    """Test that builtin toolsets can be configured via config.yaml"""

    @patch("holmes.core.toolset_manager.load_builtin_toolsets")
    def test_override_builtin_config_values(self, mock_load_builtin_toolsets):
        """Test that config values can be overridden for builtin toolsets"""
        # Create a mock builtin toolset with default config
        builtin = MagicMock(spec=Toolset)
        builtin.name = "test-service"
        builtin.enabled = False  # Default disabled
        builtin.config = {
            "api_url": "https://default.example.com",
            "api_key": "default-key",
            "timeout": 30,
            "retry_count": 3,
        }
        builtin.additional_instructions = None
        builtin.tags = []
        mock_load_builtin_toolsets.return_value = [builtin]

        # Create manager with config that overrides some values
        config = {
            "toolsets": {
                "test-service": {
                    "enabled": True,  # Override to enabled
                    "config": {
                        "api_url": "https://custom.example.com",  # Override URL
                        "api_key": "custom-key",  # Override key
                        # Note: timeout and retry_count not specified - should keep defaults
                    },
                }
            }
        }

        manager = ToolsetManager(
            tags=[],
            config=config,
            default_enabled=False,
        )

        # Check that the toolset was configured correctly
        toolset = manager.registry.toolsets["test-service"]
        assert toolset.enabled is True, "Should override enabled to True"
        assert (
            toolset.config["api_url"] == "https://custom.example.com"
        ), "Should override api_url"
        assert toolset.config["api_key"] == "custom-key", "Should override api_key"
        assert toolset.config["timeout"] == 30, "Should preserve default timeout"
        assert toolset.config["retry_count"] == 3, "Should preserve default retry_count"

    @patch("holmes.core.toolset_manager.load_builtin_toolsets")
    def test_config_merge_preserves_defaults(self, mock_load_builtin_toolsets):
        """Test that unspecified config values are preserved from defaults"""
        builtin = MagicMock(spec=Toolset)
        builtin.name = "monitoring"
        builtin.enabled = True
        builtin.config = {
            "host": "localhost",
            "port": 9090,
            "protocol": "https",
            "path": "/api/v1",
            "headers": {"User-Agent": "Holmes/1.0"},
        }
        builtin.additional_instructions = "Default instructions"
        builtin.tags = []
        mock_load_builtin_toolsets.return_value = [builtin]

        # Only override the port
        config = {
            "toolsets": {
                "monitoring": {
                    "config": {
                        "port": 8080,  # Only change port
                    }
                }
            }
        }

        manager = ToolsetManager(
            tags=[],
            config=config,
            default_enabled=False,
        )

        toolset = manager.registry.toolsets["monitoring"]
        # Changed value
        assert toolset.config["port"] == 8080
        # Preserved values
        assert toolset.config["host"] == "localhost"
        assert toolset.config["protocol"] == "https"
        assert toolset.config["path"] == "/api/v1"
        assert toolset.config["headers"] == {"User-Agent": "Holmes/1.0"}
        assert toolset.additional_instructions == "Default instructions"

    @patch("holmes.core.toolset_manager.load_builtin_toolsets")
    def test_additional_instructions_override(self, mock_load_builtin_toolsets):
        """Test that additional_instructions can be overridden"""
        builtin = MagicMock(spec=Toolset)
        builtin.name = "database"
        builtin.enabled = True
        builtin.config = {"connection": "default"}
        builtin.additional_instructions = "Default instructions"
        builtin.tags = []
        mock_load_builtin_toolsets.return_value = [builtin]

        config = {
            "toolsets": {
                "database": {
                    "additional_instructions": "Custom instructions for special handling"
                }
            }
        }

        manager = ToolsetManager(
            tags=[],
            config=config,
            default_enabled=False,
        )

        toolset = manager.registry.toolsets["database"]
        assert (
            toolset.additional_instructions
            == "Custom instructions for special handling"
        )
        assert toolset.config == {"connection": "default"}  # Config unchanged


class TestPrerequisiteChecksWithOverriddenConfig:
    """Test that prerequisite checks use the overridden configuration"""

    @patch("holmes.core.toolset_manager.load_builtin_toolsets")
    def test_prerequisite_uses_overridden_config(self, mock_load_builtin_toolsets):
        """Test that prerequisites are checked with overridden config values"""

        # Create a callable that checks the config
        def check_api_key(config_dict):
            """Check that API key is valid"""
            if not config_dict:
                return False, "No config provided"
            api_key = config_dict.get("api_key", "")
            if api_key.startswith("valid-"):
                return True, None
            return False, f"Invalid API key: {api_key}"

        # Create builtin with prerequisite that checks config
        builtin = YAMLToolset(
            name="api-service",
            description="Test API service",
            tools=[],
            enabled=True,
            config={"api_key": "invalid-default"},  # Default would fail
            prerequisites=[CallablePrerequisite(callable=check_api_key)],
        )
        builtin.tags = []
        mock_load_builtin_toolsets.return_value = [builtin]

        # Override with valid API key
        config = {
            "toolsets": {
                "api-service": {
                    "config": {
                        "api_key": "valid-custom-key"  # This should pass
                    }
                }
            }
        }

        manager = ToolsetManager(
            tags=[],
            config=config,
            default_enabled=False,
        )

        toolset = manager.registry.toolsets["api-service"]
        # The config should be overridden
        assert toolset.config["api_key"] == "valid-custom-key"

        # Check prerequisites with the overridden config
        toolset.check_prerequisites(quiet=True)
        assert (
            toolset.status == ToolsetStatusEnum.ENABLED
        ), f"Should pass with valid key, but got: {toolset.error}"

    @patch("holmes.core.toolset_manager.load_builtin_toolsets")
    def test_env_prerequisite_with_overridden_config(self, mock_load_builtin_toolsets):
        """Test environment prerequisites work with config overrides"""
        builtin = YAMLToolset(
            name="cloud-service",
            description="Test cloud service",
            tools=[],
            enabled=True,
            config={"region": "us-east-1"},
            prerequisites=[ToolsetEnvironmentPrerequisite(var_name="CLOUD_API_KEY")],
        )
        builtin.tags = []
        mock_load_builtin_toolsets.return_value = [builtin]

        # Set the environment variable
        os.environ["CLOUD_API_KEY"] = "test-key"

        try:
            config = {
                "toolsets": {
                    "cloud-service": {
                        "config": {
                            "region": "eu-west-1"  # Override region
                        }
                    }
                }
            }

            manager = ToolsetManager(
                tags=[],
                config=config,
                default_enabled=False,
            )

            toolset = manager.registry.toolsets["cloud-service"]
            assert toolset.config["region"] == "eu-west-1"

            # Prerequisites should still pass
            toolset.check_prerequisites(quiet=True)
            assert toolset.status == ToolsetStatusEnum.ENABLED
        finally:
            del os.environ["CLOUD_API_KEY"]


class TestMCPServersViaConfig:
    """Test that MCP servers can be added via config"""

    def test_mcp_servers_added_via_config(self):
        """Test that MCP servers can be added through mcp_servers config section"""
        config = {
            "mcp_servers": {
                "test-mcp": {
                    "url": "http://localhost:8000/sse",
                    "description": "Test MCP server",
                    "config": {"api_key": "test-key", "custom_param": "value"},
                }
            }
        }

        manager = ToolsetManager(
            tags=[],
            config=config,
            default_enabled=False,
        )

        # MCP server should be added
        assert "test-mcp" in manager.registry.toolsets
        mcp = manager.registry.toolsets["test-mcp"]
        assert mcp.type.value == "mcp"
        assert mcp.config["api_key"] == "test-key"
        assert mcp.config["custom_param"] == "value"

    def test_mcp_servers_and_toolsets_config_together(self):
        """Test that both mcp_servers and toolsets config work together"""
        with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
            builtin = MagicMock(spec=Toolset)
            builtin.name = "builtin-tool"
            builtin.enabled = False
            builtin.config = {"default": "value"}
            builtin.additional_instructions = None
            builtin.tags = []
            mock_load.return_value = [builtin]

            config = {
                "toolsets": {
                    "builtin-tool": {"enabled": True, "config": {"custom": "override"}}
                },
                "mcp_servers": {
                    "custom-mcp": {
                        "url": "http://mcp.example.com",
                        "description": "Custom MCP",
                        "config": {"mcp_key": "value"},
                    }
                },
            }

            manager = ToolsetManager(
                tags=[],
                config=config,
                default_enabled=False,
            )

            # Builtin should be configured
            builtin_toolset = manager.registry.toolsets["builtin-tool"]
            assert builtin_toolset.enabled is True
            assert builtin_toolset.config == {"default": "value", "custom": "override"}

            # MCP should be added
            assert "custom-mcp" in manager.registry.toolsets
            mcp = manager.registry.toolsets["custom-mcp"]
            assert mcp.type.value == "mcp"


class TestCustomToolsetsCannotOverrideBuiltins:
    """Test that custom YAML files cannot override builtin toolsets"""

    @patch("holmes.core.toolset_manager.load_builtin_toolsets")
    def test_custom_yaml_cannot_override_builtin(self, mock_load_builtin_toolsets):
        """Test that custom YAML files trying to override builtins raise error"""
        builtin = YAMLToolset(
            name="kubernetes/core",
            description="Builtin Kubernetes toolset",
            tools=[],
            enabled=True,
        )
        builtin.tags = []
        mock_load_builtin_toolsets.return_value = [builtin]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom YAML trying to override builtin
            custom_file = Path(tmpdir) / "custom.yaml"
            custom_config = {
                "toolsets": {
                    "kubernetes/core": {  # Same name as builtin!
                        "description": "My override attempt",
                        "tools": [],
                        "enabled": False,
                    }
                }
            }

            with open(custom_file, "w") as f:
                yaml.dump(custom_config, f)

            # Should raise error about conflict
            with pytest.raises(ValueError) as exc_info:
                ToolsetManager(
                    tags=[],
                    config={},
                    custom_toolset_paths=[custom_file],
                    default_enabled=False,
                )

            assert "conflict with builtin toolsets" in str(exc_info.value)
            assert "kubernetes/core" in str(exc_info.value)

    @patch("holmes.core.toolset_manager.load_builtin_toolsets")
    def test_custom_yaml_can_add_new_toolsets(self, mock_load_builtin_toolsets):
        """Test that custom YAML files can add new (non-conflicting) toolsets"""
        builtin = MagicMock(spec=Toolset)
        builtin.name = "existing"
        builtin.tags = []
        mock_load_builtin_toolsets.return_value = [builtin]

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_file = Path(tmpdir) / "custom.yaml"
            custom_config = {
                "toolsets": {
                    "my-custom-tool": {  # New name, no conflict
                        "description": "My custom toolset",
                        "tools": [],
                        "enabled": True,
                    }
                }
            }

            with open(custom_file, "w") as f:
                yaml.dump(custom_config, f)

            manager = ToolsetManager(
                tags=[],
                config={},
                custom_toolset_paths=[custom_file],
                default_enabled=False,
            )

            # Both should exist
            assert "existing" in manager.registry.toolsets
            assert "my-custom-tool" in manager.registry.toolsets

            # Custom toolset should have correct properties
            custom = manager.registry.toolsets["my-custom-tool"]
            assert custom.description == "My custom toolset"
            assert custom.enabled is True


class TestInvalidToolsetHandling:
    """Test that invalid toolsets are handled gracefully"""

    def test_invalid_custom_toolset_skipped(self):
        """Test that invalid toolsets in custom files are skipped with logging"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_file = Path(tmpdir) / "custom.yaml"
            custom_config = {
                "toolsets": {
                    "valid-tool": {
                        "description": "Valid toolset",
                        "tools": [],
                        "enabled": True,
                    },
                    "invalid-tool": {
                        # Missing required fields!
                        "enabled": True,
                    },
                    "another-valid": {
                        "description": "Another valid one",
                        "tools": [],
                        "enabled": False,
                    },
                }
            }

            with open(custom_file, "w") as f:
                yaml.dump(custom_config, f)

            manager = ToolsetManager(
                tags=[],
                config={},
                custom_toolset_paths=[custom_file],
                default_enabled=False,
                suppress_logging=True,  # Suppress error logs in test
            )

            # Valid toolsets should be loaded
            assert "valid-tool" in manager.registry.toolsets
            assert "another-valid" in manager.registry.toolsets

            # Invalid toolset should be skipped
            assert "invalid-tool" not in manager.registry.toolsets

            # Other toolsets should still work
            assert manager.registry.toolsets["valid-tool"].enabled is True
            assert manager.registry.toolsets["another-valid"].enabled is False
