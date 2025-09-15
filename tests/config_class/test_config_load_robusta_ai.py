from unittest.mock import patch
from holmes.config import Config
from holmes.clients.robusta_client import RobustaModelsResponse


ROBUSTA_TEST_MODELS = RobustaModelsResponse(models=["Robusta/test"], default_model=None)


@patch("holmes.core.llm.ROBUSTA_AI", True)
def test_cli_not_loading_robusta_ai(*, monkeypatch):
    config = Config.load_from_file(None)
    assert "Robusta" not in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", True)
@patch("holmes.core.llm.fetch_robusta_models", return_value=ROBUSTA_TEST_MODELS)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_loads_robusta_ai_when_true(mock_cluster, mock_fetch, *, monkeypatch):
    config = Config.load_from_env()
    assert "Robusta/test" in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", None)
@patch("holmes.core.llm.fetch_robusta_models", return_value=ROBUSTA_TEST_MODELS)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_loads_robusta_ai_when_not_exists_and_not_other_models(
    mock_cluster, mock_fetch, *, monkeypatch
):
    config = Config.load_from_env()
    assert "Robusta/test" in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", False)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_not_loads_robusta_ai_when_false(mock_cluster, *, monkeypatch):
    config = Config.load_from_env()
    assert "Robusta" not in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", True)
@patch("holmes.core.llm.fetch_robusta_models", return_value=ROBUSTA_TEST_MODELS)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
@patch(
    "holmes.core.llm.LLMModelRegistry._parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_loads_robusta_ai_when_true_and_model_list_exists(
    mock_parse, mock_cluster, mock_fetch, *, monkeypatch
):
    config = Config.load_from_env()
    assert "existing_model" in config.llm_model_registry.models
    assert "Robusta/test" in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", False)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
@patch(
    "holmes.core.llm.LLMModelRegistry._parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_not_loads_robusta_ai_when_false_and_model_list_exists(
    mock_parse, mock_cluster, *, monkeypatch
):
    config = Config.load_from_env()
    assert "existing_model" in config.llm_model_registry.models
    assert "Robusta" not in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", None)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
@patch(
    "holmes.core.llm.LLMModelRegistry._parse_models_file",
    return_value={"existing_model": {"base_url": "http://foo"}},
)
def test_server_not_loads_robusta_ai_when_no_env_var_and_model_list_exists(
    mock_parse, mock_cluster, *, monkeypatch
):
    config = Config.load_from_env()
    assert "existing_model" in config.llm_model_registry.models
    assert "Robusta" not in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", True)
@patch("holmes.core.llm.fetch_robusta_models", return_value=ROBUSTA_TEST_MODELS)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_loads_robusta_ai_when_model_var_exists(
    mock_cluster, mock_fetch, *, monkeypatch
):
    monkeypatch.setenv("MODEL", "some_model")

    config = Config.load_from_env()
    assert "Robusta/test" in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", None)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_not_loads_robusta_ai_when_model_var_exists_and_no_env_var(
    mock_cluster, *, monkeypatch
):
    monkeypatch.setenv("MODEL", "some_model")
    config = Config.load_from_env()
    assert "Robusta" not in config.llm_model_registry.models


@patch("holmes.core.llm.ROBUSTA_AI", False)
@patch("holmes.config.Config._Config__get_cluster_name", return_value="test")
def test_server_not_loads_robusta_ai_when_model_var_exists_and_false_env_var(
    mock_cluster, *, monkeypatch
):
    monkeypatch.setenv("MODEL", "some_model")
    config = Config.load_from_env()
    assert "Robusta" not in config.llm_model_registry.models
