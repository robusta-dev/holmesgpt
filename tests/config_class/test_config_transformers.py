"""
Unit tests for transformer configuration fields.

These tests verify that the fast_model and summarize_threshold configuration
fields work correctly with different configuration sources (file, env, CLI).
"""

import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch


def test_transformer_fields_exist():
    """Test that Config class has the new transformer configuration fields."""
    # Mock the dependencies at their actual import locations
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        # Test default values
        config = Config()
        assert hasattr(config, "fast_model")
        assert hasattr(config, "summarize_threshold")
        assert config.fast_model is None
        assert config.summarize_threshold == 1000


def test_transformer_from_file():
    """Test loading transformer config from YAML file."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {
                "fast_model": "gpt-4o-mini",
                "summarize_threshold": 500,
                "model": "gpt-4o",
            }
            yaml.dump(config_data, f)
            f.flush()

            try:
                config = Config.load_from_file(Path(f.name))
                assert config.fast_model == "gpt-4o-mini"
                assert config.summarize_threshold == 500
                assert config.model == "gpt-4o"
            finally:
                os.unlink(f.name)


def test_transformer_from_env():
    """Test loading transformer config from environment variables."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        with patch.dict(
            os.environ,
            {
                "FAST_MODEL": "gpt-3.5-turbo",
                "SUMMARIZE_THRESHOLD": "2000",
                "MODEL": "gpt-4o",
            },
        ):
            config = Config.load_from_env()
            assert config.fast_model == "gpt-3.5-turbo"
            assert (
                config.summarize_threshold == 2000
            )  # env vars converted to int by pydantic
            assert config.model == "gpt-4o"


def test_transformer_cli_override():
    """Test that CLI options override config file values."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"fast_model": "gpt-4o-mini", "summarize_threshold": 500}
            yaml.dump(config_data, f)
            f.flush()

            try:
                config = Config.load_from_file(
                    Path(f.name), fast_model="gpt-3.5-turbo", summarize_threshold=1500
                )
                assert config.fast_model == "gpt-3.5-turbo"
                assert config.summarize_threshold == 1500
            finally:
                os.unlink(f.name)


def test_transformer_backward_compatibility():
    """Test that existing configs without transformer fields still work."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

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
                assert config.summarize_threshold == 1000
            finally:
                os.unlink(f.name)


def test_transformer_env_vars_in_load_from_env_list():
    """Test that the new environment variables are included in the load_from_env field list."""
    # This tests the code change we made to the load_from_env method
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config
        import inspect

        # Get the source code of load_from_env method
        source = inspect.getsource(Config.load_from_env)

        # Verify our new fields are in the field list
        assert '"fast_model"' in source
        assert '"summarize_threshold"' in source


def test_auto_generate_transformers_with_fast_model():
    """Test that transformers are auto-generated when fast_model is provided."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        # Test with fast_model provided
        config = Config(fast_model="gpt-4o-mini", summarize_threshold=500)

        # Should auto-generate transformers
        assert config.transformers is not None
        assert len(config.transformers) == 1
        assert "llm_summarize" in config.transformers[0]
        assert config.transformers[0]["llm_summarize"]["fast_model"] == "gpt-4o-mini"
        assert config.transformers[0]["llm_summarize"]["input_threshold"] == 500


def test_auto_generate_transformers_without_fast_model():
    """Test that transformers are not auto-generated when fast_model is not provided."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        # Test without fast_model
        config = Config(summarize_threshold=500)

        # Should not auto-generate transformers
        assert config.transformers is None


def test_auto_generate_transformers_respects_existing_configs():
    """Test that existing transformers are not overridden by auto-generation."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        # Test with existing transformers
        existing_configs = [{"custom_transformer": {"param": "value"}}]
        config = Config(fast_model="gpt-4o-mini", transformers=existing_configs)

        # Should preserve existing transformers
        assert config.transformers == existing_configs


def test_auto_generate_transformers_cli_override():
    """Test that CLI fast_model parameter auto-generates transformers."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        # Test CLI override case (similar to holmes ask --fast-model)
        config = Config.load_from_file(
            None,  # No config file
            fast_model="azure/gpt-4.1",
            summarize_threshold=2000,
        )

        # Should auto-generate transformers from CLI parameters
        assert config.transformers is not None
        assert len(config.transformers) == 1
        assert config.transformers[0]["llm_summarize"]["fast_model"] == "azure/gpt-4.1"
        assert config.transformers[0]["llm_summarize"]["input_threshold"] == 2000


def test_auto_generate_transformers_default_threshold():
    """Test that auto-generation uses default threshold when not specified."""
    with patch("holmes.__init__.get_version", return_value="1.0.0"), patch(
        "holmes.clients.robusta_client.fetch_holmes_info", return_value=None
    ), patch("holmes.config.parse_models_file", return_value={}), patch(
        "holmes.common.env_vars.ROBUSTA_AI", False
    ):
        from holmes.config import Config

        # Test with fast_model but default threshold
        config = Config(fast_model="gpt-4o-mini")

        # Should use default summarize_threshold (1000)
        assert config.transformers[0]["llm_summarize"]["input_threshold"] == 1000
