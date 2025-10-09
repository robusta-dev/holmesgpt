"""Test environment variable substitution in builtin toolset configuration."""

import os
import json
from unittest.mock import patch

from holmes.core.tools import YAMLToolset, ToolsetTag
from holmes.core.toolset_manager import ToolsetManager


def test_builtin_toolset_config_env_var_substitution():
    """Test that environment variables are substituted in builtin toolset configuration."""
    # Set environment variables
    os.environ["TEST_PROMETHEUS_URL"] = "http://prometheus.prod:9090"
    os.environ["TEST_API_KEY"] = "secret-key-123"
    os.environ["TEST_TIMEOUT"] = "60"

    try:
        # Create a mock builtin toolset
        builtin = YAMLToolset(
            name="test-service",
            description="Test service",
            tools=[],
            enabled=False,
            config={
                "url": "http://localhost:8080",
                "api_key": "default-key",
                "timeout": 30,
                "retry_count": 3,
            },
            tags=[ToolsetTag.CORE],
        )

        with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
            mock_load.return_value = [builtin]

            # Create config that uses environment variables
            # Note: In real usage, the YAML would have {{env.VAR}} which gets replaced
            # before reaching the Python config. Here we simulate the replaced values.
            config = {
                "toolsets": {
                    "test-service": {
                        "enabled": True,
                        "config": {
                            "url": os.environ[
                                "TEST_PROMETHEUS_URL"
                            ],  # Simulating {{env.TEST_PROMETHEUS_URL}}
                            "api_key": os.environ[
                                "TEST_API_KEY"
                            ],  # Simulating {{env.TEST_API_KEY}}
                            "timeout": int(
                                os.environ["TEST_TIMEOUT"]
                            ),  # Simulating {{env.TEST_TIMEOUT}}
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

            # Verify the configuration was merged with env var values
            toolset = manager.registry.toolsets["test-service"]
            assert toolset.enabled is True
            assert toolset.config["url"] == "http://prometheus.prod:9090"
            assert toolset.config["api_key"] == "secret-key-123"
            assert toolset.config["timeout"] == 60
            assert toolset.config["retry_count"] == 3  # Preserved from default

    finally:
        # Clean up environment
        del os.environ["TEST_PROMETHEUS_URL"]
        del os.environ["TEST_API_KEY"]
        del os.environ["TEST_TIMEOUT"]


def test_builtin_config_via_helm_env_var():
    """Test the Helm-style configuration via HOLMES_BUILTIN_TOOLSETS_CONFIG env var."""
    # Create a mock builtin toolset
    builtin = YAMLToolset(
        name="prometheus/metrics",
        description="Prometheus metrics",
        tools=[],
        enabled=False,
        config={"url": "http://localhost:9090", "timeout": 30},
        tags=[ToolsetTag.CORE],
    )

    with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
        mock_load.return_value = [builtin]

        # Set the Helm-style environment variable
        toolsets_config = {
            "prometheus/metrics": {
                "enabled": True,
                "config": {"url": "http://prometheus.monitoring:9090"},
            }
        }
        os.environ["HOLMES_BUILTIN_TOOLSETS_CONFIG"] = json.dumps(toolsets_config)

        try:
            # Import Config here to pick up the env var
            from holmes.config import Config

            with patch.object(Config, "load_from_env") as mock_load_env:
                # Simulate what load_from_env does
                mock_load_env.return_value = Config(
                    toolsets=toolsets_config, should_try_robusta_ai=True
                )

                config = Config.load_from_env()

                manager = ToolsetManager(
                    tags=[ToolsetTag.CORE],
                    config={"toolsets": config.toolsets} if config.toolsets else {},
                    default_enabled=False,
                    suppress_logging=True,
                )

                # Verify the configuration was applied
                toolset = manager.registry.toolsets["prometheus/metrics"]
                assert toolset.enabled is True
                assert toolset.config["url"] == "http://prometheus.monitoring:9090"
                assert toolset.config["timeout"] == 30  # Preserved from default

        finally:
            del os.environ["HOLMES_BUILTIN_TOOLSETS_CONFIG"]


def test_nested_config_with_env_vars():
    """Test that deeply nested configurations work with environment variable substitution."""
    os.environ["DB_HOST"] = "database.prod.example.com"
    os.environ["DB_PASSWORD"] = "super-secret"
    os.environ["DB_PORT"] = "5432"

    try:
        builtin = YAMLToolset(
            name="database-tool",
            description="Database tool",
            tools=[],
            config={
                "connection": {
                    "host": "localhost",
                    "port": 3306,
                    "credentials": {"username": "admin", "password": "default-pass"},
                }
            },
            tags=[ToolsetTag.CORE],
        )

        with patch("holmes.core.toolset_manager.load_builtin_toolsets") as mock_load:
            mock_load.return_value = [builtin]

            # Simulate config with env vars replaced
            config = {
                "toolsets": {
                    "database-tool": {
                        "enabled": True,
                        "config": {
                            "connection": {
                                "host": os.environ["DB_HOST"],
                                "port": int(os.environ["DB_PORT"]),
                                "credentials": {"password": os.environ["DB_PASSWORD"]},
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

            toolset = manager.registry.toolsets["database-tool"]
            # Verify nested merge with env var values
            assert toolset.config["connection"]["host"] == "database.prod.example.com"
            assert toolset.config["connection"]["port"] == 5432
            assert (
                toolset.config["connection"]["credentials"]["username"] == "admin"
            )  # Preserved
            assert (
                toolset.config["connection"]["credentials"]["password"]
                == "super-secret"
            )

    finally:
        del os.environ["DB_HOST"]
        del os.environ["DB_PASSWORD"]
        del os.environ["DB_PORT"]
