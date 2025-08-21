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


def test_config_get_llm_with_api_base_version():
    """Test that Config._get_llm passes api_base and api_version to DefaultLLM."""
    config = Config(
        model="test-model",
        api_key="test-key",
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
        assert call_args[1].get_secret_value() == "test-key"  # api_key is SecretStr
        assert call_args[2] == "https://test.api.base"
        assert call_args[3] == "2023-12-01"
        assert call_args[4] is None  # tracer
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
    monkeypatch.setattr("holmes.config.MODEL_LIST_FILE_LOCATION", str(temp_config_file))

    config = Config(model="test-model")

    with patch("holmes.config.DefaultLLM") as mock_default_llm:
        mock_llm_instance = MagicMock()
        mock_default_llm.return_value = mock_llm_instance

        result = config._get_llm("test-model")

        mock_default_llm.assert_called_once_with(
            "azure/gpt-4o",
            "model-key",
            "https://model.api.base",
            "2024-02-01",
            None,  # tracer
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
    monkeypatch.setattr("holmes.config.MODEL_LIST_FILE_LOCATION", str(temp_config_file))

    config = Config(
        model="test-model", api_base="https://config.api.base", api_version="2023-01-01"
    )

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
            None,  # tracer
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
    monkeypatch.setattr("holmes.config.MODEL_LIST_FILE_LOCATION", str(temp_config_file))

    config = Config(
        model="test-model", api_base="https://config.api.base", api_version="2023-01-01"
    )

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
            None,  # tracer
        )
