from unittest.mock import patch
from pydantic import SecretStr
from holmes.config import Config


def fake_load_robusta_api_key(config, _):
    config.account_id = "mock-account"
    config.session_token = SecretStr("mock-token")
    config.api_key = SecretStr("mock-token")


@patch("holmes.config.ROBUSTA_AI", True)
def test_cli_not_loading_robusta_ai(*, monkeypatch):
    config = Config.load_from_file(None)
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", True)
@patch("holmes.config.fetch_robusta_models", return_value=["Robusta/test"])
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_loads_robusta_ai_when_true(mock_cluster, mock_fetch, *, monkeypatch):
    def fake_loader(self, dal):
        self.account_id = "mock-account"
        self.session_token = SecretStr("mock-token")
        self.api_key = SecretStr("mock-token")

    monkeypatch.setattr(Config, "load_robusta_api_key", fake_loader)
    config = Config.load_from_env()
    assert "Robusta/test" in config._model_list


@patch("holmes.config.ROBUSTA_AI", None)
@patch("holmes.config.fetch_robusta_models", return_value=["Robusta/test"])
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_loads_robusta_ai_when_not_exists_and_not_other_models(
    mock_cluster, mock_fetch, *, monkeypatch
):
    def fake_loader(self, dal):
        self.account_id = "mock-account"
        self.session_token = SecretStr("mock-token")
        self.api_key = SecretStr("mock-token")

    monkeypatch.setattr(Config, "load_robusta_api_key", fake_loader)
    config = Config.load_from_env()
    assert "Robusta/test" in config._model_list


@patch("holmes.config.ROBUSTA_AI", False)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_not_loads_robusta_ai_when_false(mock_cluster, *, monkeypatch):
    config = Config.load_from_env()
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", True)
@patch("holmes.config.fetch_robusta_models", return_value=["Robusta/test"])
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
@patch(
    "holmes.config.parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_loads_robusta_ai_when_true_and_model_list_exists(
    mock_parse, mock_cluster, mock_fetch, *, monkeypatch
):
    def fake_loader(self, dal):
        self.account_id = "mock-account"
        self.session_token = SecretStr("mock-token")
        self.api_key = SecretStr("mock-token")

    monkeypatch.setattr(Config, "load_robusta_api_key", fake_loader)
    config = Config.load_from_env()
    assert "existing_model" in config._model_list
    assert "Robusta/test" in config._model_list


@patch("holmes.config.ROBUSTA_AI", False)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
@patch(
    "holmes.config.parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_not_loads_robusta_ai_when_false_and_model_list_exists(
    mock_parse, mock_cluster, *, monkeypatch
):
    config = Config.load_from_env()
    assert "existing_model" in config._model_list
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", None)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
@patch(
    "holmes.config.parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_not_loads_robusta_ai_when_no_env_var_and_model_list_exists(
    mock_parse, mock_cluster, *, monkeypatch
):
    config = Config.load_from_env()
    assert "existing_model" in config._model_list
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", True)
@patch("holmes.config.fetch_robusta_models", return_value=["Robusta/test"])
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_loads_robusta_ai_when_model_var_exists(
    mock_cluster, mock_fetch, *, monkeypatch
):
    monkeypatch.setenv("MODEL", "some_model")

    def fake_loader(self, dal):
        self.account_id = "mock-account"
        self.session_token = SecretStr("mock-token")
        self.api_key = SecretStr("mock-token")

    monkeypatch.setattr(Config, "load_robusta_api_key", fake_loader)
    config = Config.load_from_env()
    assert "Robusta/test" in config._model_list


@patch("holmes.config.ROBUSTA_AI", None)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_not_loads_robusta_ai_when_model_var_exists_and_no_env_var(
    mock_cluster, *, monkeypatch
):
    monkeypatch.setenv("MODEL", "some_model")
    config = Config.load_from_env()
    assert "Robusta" not in config._model_list


@patch("holmes.config.ROBUSTA_AI", False)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_not_loads_robusta_ai_when_model_var_exists_and_false_env_var(
    mock_cluster, *, monkeypatch
):
    monkeypatch.setenv("MODEL", "some_model")
    config = Config.load_from_env()
    assert "Robusta" not in config._model_list
