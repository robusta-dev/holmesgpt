import yaml
from unittest.mock import patch, MagicMock

from holmes.config import Config


def test_config_api_base_api_version_defaults():
    """Test that api_base and api_version default to None in Config."""
    config = Config()
    assert config.api_base is None
    assert config.api_version is None


def test_config_api_base_api_version_set():
    """Test that api_base and api_version can be set in Config."""
    config = Config(api_base="https://custom.api.base", api_version="2023-12-01")
    assert config.api_base == "https://custom.api.base"
    assert config.api_version == "2023-12-01"


def test_config_load_from_env_includes_api_base_version(monkeypatch):
    """Test that api_base and api_version are loaded from env vars."""
    monkeypatch.setenv("API_BASE", "https://env.api.base")
    monkeypatch.setenv("API_VERSION", "2024-01-01")
    monkeypatch.setenv("MODEL", "test-model")

    config = Config.load_from_env()

    assert config.api_base == "https://env.api.base"
    assert config.api_version == "2024-01-01"
    assert config.model == "test-model"


def test_config_get_llm_with_api_base_version():
    """Test that Config._get_llm passes api_base and api_version to DefaultLLM."""
    config = Config(
        model="test-model",
        api_base="https://test.api.base",
        api_version="2023-12-01",
    )

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        result = config._get_llm()

        # Check that DefaultLLM was called with the right positional arguments
        call_args = mock_default_llm.call_args[0]
        assert call_args[0] == "test-model"
        assert call_args[1] is None
        assert call_args[2] == "https://test.api.base"
        assert call_args[3] == "2023-12-01"
        assert call_args[4] == {}
        assert call_args[5] is None  # tracer
        assert result == mock_llm_instance


def test_config_get_llm_with_model_list_api_base_version(monkeypatch, tmp_path):
    """Test that api_base and api_version from model list are passed to DefaultLLM."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "test-model": {
            "model": "azure/gpt-4o",
            "api_key": "model-key",
            "api_base": "https://model.api.base",
            "api_version": "2024-02-01",
        }
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config()

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance
        result = config._get_llm("test-model")

        mock_default_llm.assert_called_once_with(
            "azure/gpt-4o",
            "model-key",
            "https://model.api.base",
            "2024-02-01",
            {},
            None,  # tracer,
            "test-model",
        )
        assert result == mock_llm_instance


def test_config_get_llm_model_list_overrides_config_values(monkeypatch, tmp_path):
    """Test that model list values override config values for api_base and api_version."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "test-model": {
            "model": "azure/gpt-4o",
            "api_key": "model-key",
            "api_base": "https://override.api.base",
            "api_version": "2024-03-01",
        }
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config(api_base="https://config.api.base", api_version="2023-01-01")

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        config._get_llm("test-model")

        # Should use values from model list, not config
        mock_default_llm.assert_called_once_with(
            "azure/gpt-4o",
            "model-key",
            "https://override.api.base",  # from model list
            "2024-03-01",  # from model list
            {},
            None,  # tracer
            "test-model",
        )


def test_config_get_llm_model_list_defaults_to_config_values(monkeypatch, tmp_path):
    """Test that missing api_base/api_version in model list fall back to config values."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "test-model": {
            "model": "azure/gpt-4o",
            "api_key": "model-key",
            # api_base and api_version not specified
        }
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config(api_base="https://config.api.base", api_version="2023-01-01")

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        config._get_llm("test-model")

        # Should use config values as fallback
        mock_default_llm.assert_called_once_with(
            "azure/gpt-4o",
            "model-key",
            "https://config.api.base",  # from config
            "2023-01-01",  # from config
            {},
            None,  # tracer
            "test-model",
        )


def test_config_get_llm_with_non_none_model_list_first_model_fallback(
    monkeypatch, tmp_path
):
    """Test that when _model_list is not None and no model_key is provided, it uses first model."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "first-model": {
            "model": "gpt-4",
            "api_key": "first-key",
            "api_base": "https://first.api.base",
            "api_version": "2024-01-01",
        },
        "second-model": {
            "model": "gpt-3.5-turbo",
            "api_key": "second-key",
            "api_base": "https://second.api.base",
            "api_version": "2024-02-01",
        },
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config()

    # Verify _model_list is not None after initialization
    assert config.llm_model_registry is not None
    assert len(config.llm_model_registry.models) == 2

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        # Call _get_llm without model_key - should use first model in dict
        config._get_llm()

        # Should use the first model's values (iteration order in Python dicts is insertion order)
        mock_default_llm.assert_called_once_with(
            "gpt-4",  # from first model
            "first-key",  # from first model
            "https://first.api.base",  # from first model
            "2024-01-01",  # from first model
            {},
            None,  # tracer
            "gpt-4",
        )


def test_config_get_llm_with_specific_model_from_model_list(monkeypatch, tmp_path):
    """Test that when _get_llm is called with a specific model_key, it uses that model's config."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "azure-gpt4": {
            "model": "azure/gpt-4",
            "api_key": "azure-key",
            "api_base": "https://azure.api.base",
            "api_version": "2024-03-01",
        },
        "openai-gpt35": {
            "model": "gpt-3.5-turbo",
            "api_key": "openai-key",
            "api_base": "https://openai.api.base",
            "api_version": "2024-04-01",
        },
        "anthropic-claude": {
            "model": "claude-3-sonnet",
            "api_key": "anthropic-key",
            "api_base": "https://anthropic.api.base",
            "api_version": "2024-05-01",
        },
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config(
        api_base="https://config.default.base",
        api_version="2023-01-01",
    )

    # Verify _model_list is not None after initialization
    assert config.llm_model_registry is not None
    assert len(config.llm_model_registry.models) == 3

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        # Call _get_llm with specific model_key - should use that model's config
        config._get_llm("openai-gpt35")

        # Should use the specified model's values, not the first or config defaults
        mock_default_llm.assert_called_once_with(
            "gpt-3.5-turbo",  # from openai-gpt35 model
            "openai-key",  # from openai-gpt35 model
            "https://openai.api.base",  # from openai-gpt35 model
            "2024-04-01",  # from openai-gpt35 model
            {},
            None,  # tracer,
            "openai-gpt35",
        )


def test_config_get_llm_with_base_url_only(monkeypatch, tmp_path):
    """Test that base_url is used when only base_url is provided in model list."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "test-model": {
            "model": "gpt-4",
            "api_key": "test-key",
            "base_url": "https://base.url.only",
            "api_version": "2024-01-01",
        }
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config()

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        config._get_llm("test-model")

        # Should use base_url value as api_base
        mock_default_llm.assert_called_once_with(
            "gpt-4",
            "test-key",
            "https://base.url.only",  # base_url used as api_base
            "2024-01-01",
            {},
            None,  # tracer
            "test-model",
        )


def test_config_get_llm_api_base_overrides_base_url(monkeypatch, tmp_path):
    """Test that api_base takes precedence over base_url when both are provided."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "test-model": {
            "model": "gpt-4",
            "api_key": "test-key",
            "api_base": "https://api.base.wins",
            "base_url": "https://base.url.loses",
            "api_version": "2024-01-01",
        }
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config()

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        config._get_llm("test-model")

        # Should use api_base value, not base_url
        mock_default_llm.assert_called_once_with(
            "gpt-4",
            "test-key",
            "https://api.base.wins",  # api_base takes precedence
            "2024-01-01",
            {},
            None,  # tracer
            "test-model",
        )


def test_config_get_llm_neither_api_base_nor_base_url_uses_config(
    monkeypatch, tmp_path
):
    """Test that config api_base is used when neither api_base nor base_url are in model list."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "test-model": {
            "model": "gpt-4",
            "api_key": "test-key",
            "api_version": "2024-01-01",
            # Neither api_base nor base_url provided
        }
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config(api_base="https://config.fallback.base")

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        config._get_llm("test-model")

        # Should use config api_base as fallback
        mock_default_llm.assert_called_once_with(
            "gpt-4",
            "test-key",
            "https://config.fallback.base",  # config api_base used as fallback
            "2024-01-01",
            {},
            None,  # tracer
            "test-model",
        )


def test_config_get_llm_both_params_popped_from_model_params(monkeypatch, tmp_path):
    """Test that both api_base and base_url are removed from model_params before passing to DefaultLLM."""
    temp_config_file = tmp_path / "model_list.yaml"
    data = {
        "test-model": {
            "model": "gpt-4",
            "api_key": "test-key",
            "api_base": "https://api.base.value",
            "base_url": "https://base.url.value",
            "api_version": "2024-01-01",
            "custom_param": "should_remain",
        }
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )

    config = Config()

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        config._get_llm("test-model")

        # Verify that model_params only contains custom_param, not api_base or base_url
        call_args = mock_default_llm.call_args[0]
        model_params = call_args[4]
        assert "api_base" not in model_params
        assert "base_url" not in model_params
        assert "custom_param" in model_params
        assert model_params["custom_param"] == "should_remain"
