from unittest.mock import patch
from holmes.config import Config


@patch("holmes.config.ROBUSTA_AI", True)
def test_cli_not_loading_robusta_ai(monkeypatch):
    config = Config.load_from_file(None)
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", True)
def test_server_loads_robusta_ai_when_true(monkeypatch):
    config = Config.load_from_env()
    assert "Robusta" in config._model_list


@patch("holmes.config.ROBUSTA_AI", None)
def test_server_loads_robusta_ai_when_not_exists_and_not_other_models(monkeypatch):
    config = Config.load_from_env()
    assert len(config._model_list) == 1
    assert "Robusta" in config._model_list


@patch("holmes.config.ROBUSTA_AI", False)
def test_server_not_loads_robusta_ai_when_false(monkeypatch):
    config = Config.load_from_env()
    assert len(config._model_list) == 0
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", True)
@patch(
    "holmes.config.parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_loads_robusta_ai_when_true_and_model_list_exists(monkeypatch):
    config = Config.load_from_env()
    assert "existing_model" in config._model_list
    assert "Robusta" in config._model_list


@patch("holmes.config.ROBUSTA_AI", False)
@patch(
    "holmes.config.parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_not_loads_robusta_ai_when_false_and_model_list_exists(monkeypatch):
    config = Config.load_from_env()
    assert "existing_model" in config._model_list
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", None)
@patch(
    "holmes.config.parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_not_loads_robusta_ai_when_no_env_var_and_model_list_exists(monkeypatch):
    config = Config.load_from_env()
    assert "existing_model" in config._model_list
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", True)
def test_server_loads_robusta_ai_when_model_var_exists(monkeypatch):
    monkeypatch.setenv("MODEL", "some_model")
    config = Config.load_from_env()
    assert "Robusta" in config._model_list


@patch("holmes.config.ROBUSTA_AI", None)
def test_server_not_loads_robusta_ai_when_model_var_exists_and_no_env_var(monkeypatch):
    monkeypatch.setenv("MODEL", "some_model")
    config = Config.load_from_env()
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", False)
def test_server_not_loads_robusta_ai_when_model_var_exists_and_false_env_var(
    monkeypatch,
):
    monkeypatch.setenv("MODEL", "some_model")
    config = Config.load_from_env()
    assert "Robusta" not in config._model_list
