"""
Unit tests for transformer configuration fields.

These tests verify that the fast_model configuration
fields work correctly with different configuration sources (file, env, CLI).
"""

import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch


def test_transformer_fields_exist():
    """Test that Config class has the transformer configuration fields."""
    # Mock the dependencies at their actual import locations
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer

        # Import Transformer class to resolve forward reference
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer

        # Rebuild the model to resolve forward references
        Config.model_rebuild()

        # Test default values
        config = Config()
        assert hasattr(config, "fast_model")
        assert config.fast_model is None


def test_transformer_from_file():
    """Test loading transformer config from YAML file."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer
        Config.model_rebuild()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {
                "fast_model": "gpt-4o-mini",
                "model": "gpt-4o",
            }
            yaml.dump(config_data, f)
            f.flush()

            try:
                config = Config.load_from_file(Path(f.name))
                assert config.fast_model == "gpt-4o-mini"
                assert config.model == "gpt-4o"
            finally:
                os.unlink(f.name)


def test_transformer_from_env():
    """Test loading transformer config from environment variables."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer
        Config.model_rebuild()

        with patch.dict(
            os.environ,
            {
                "FAST_MODEL": "gpt-3.5-turbo",
                "MODEL": "gpt-4o",
            },
        ):
            config = Config.load_from_env()
            assert config.fast_model == "gpt-3.5-turbo"
            assert config.model == "gpt-4o"


def test_transformer_cli_override():
    """Test that CLI options override config file values."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer
        Config.model_rebuild()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"fast_model": "gpt-4o-mini"}
            yaml.dump(config_data, f)
            f.flush()

            try:
                config = Config.load_from_file(Path(f.name), fast_model="gpt-3.5-turbo")
                assert config.fast_model == "gpt-3.5-turbo"
            finally:
                os.unlink(f.name)


def test_transformer_backward_compatibility():
    """Test that existing configs without transformer fields still work."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer
        Config.model_rebuild()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"model": "gpt-4o", "max_steps": 5}
            yaml.dump(config_data, f)
            f.flush()

            try:
                config = Config.load_from_file(Path(f.name))
                assert config.model == "gpt-4o"
                assert config.max_steps == 5
                # New fields should have defaults
                assert config.fast_model is None
            finally:
                os.unlink(f.name)


def test_transformer_env_vars_in_load_from_env_list():
    """Test that the fast_model environment variable is properly loaded by load_from_env method."""
    # This tests that the fast_model field is correctly loaded from environment variables
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer
        Config.model_rebuild()

        # Test that FAST_MODEL environment variable is properly loaded
        with patch.dict(os.environ, {"FAST_MODEL": "test-model"}):
            config = Config.load_from_env()
            assert config.fast_model == "test-model"


def test_auto_generate_transformers_with_fast_model():
    """Test that Config stores fast_model for ToolsetManager injection."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer
        Config.model_rebuild()

        # Test with fast_model provided
        config = Config(fast_model="gpt-4o-mini")

        # Should store fast_model for ToolsetManager injection
        assert config.fast_model == "gpt-4o-mini"
        # Should auto-generate transformers for backwards compatibility
        assert config.transformers is not None
        assert len(config.transformers) == 1
        assert config.transformers[0].name == "llm_summarize"
        assert config.transformers[0].config["fast_model"] == "gpt-4o-mini"


def test_auto_generate_transformers_without_fast_model():
    """Test that transformers are not auto-generated when fast_model is not provided."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer
        import sys

        sys.modules[__name__].__dict__["Transformer"] = Transformer
        Config.model_rebuild()

        # Test without fast_model
        config = Config()

        # Should not auto-generate transformers
        assert config.transformers is None
        assert config.fast_model is None


def test_auto_generate_transformers_respects_existing_configs():
    """Test that existing transformers are not overridden by auto-generation."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        from holmes.core.transformers import Transformer

        # Test with existing transformers
        existing_configs = [
            Transformer(name="custom_transformer", config={"param": "value"})
        ]
        config = Config(fast_model="gpt-4o-mini", transformers=existing_configs)

        # Should preserve existing transformers
        assert config.transformers == existing_configs


def test_auto_generate_transformers_cli_override():
    """Test that CLI fast_model parameter is stored for ToolsetManager injection."""
    with patch("holmes.version.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        # Test CLI override case (similar to holmes ask --fast-model)
        config = Config.load_from_file(
            None,  # No config file
            fast_model="azure/gpt-4.1",
        )

        # Should store fast_model for ToolsetManager injection and auto-generate transformers
        assert config.fast_model == "azure/gpt-4.1"
        assert config.transformers is not None
        assert len(config.transformers) == 1
        assert config.transformers[0].name == "llm_summarize"
        assert config.transformers[0].config["fast_model"] == "azure/gpt-4.1"
