from holmes.config import Config
from holmes.core.llm import DefaultLLM

from tests.conftest import DEFAULT_ROBUSTA_MODEL, ROBUSTA_SONNET_4_MODEL


def test_config_get_llm_no_model_key_returns_default_model(server_config: Config):
    llm: DefaultLLM = server_config._get_llm()
    assert llm.name == DEFAULT_ROBUSTA_MODEL
    assert llm.model == "gpt-4o"
    assert llm.api_base == f"https://api.robusta.dev/llm/{DEFAULT_ROBUSTA_MODEL}"


def test_confgi_get_llm_with_model_key_returns_model_from_config(
    server_config: Config, monkeypatch
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "access_key_id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_access_key")
    llm: DefaultLLM = server_config._get_llm(model_key="our_local_model")
    assert llm.name == "our_local_model"
    assert llm.model == "bedrock/custom_ai_model"
    assert llm.api_key == "existing_api_key"


def test_config_get_llm_unexisting_model_key_returns_default_model(
    server_config: Config,
):
    llm: DefaultLLM = server_config._get_llm(model_key="unexisting_model")
    assert llm.name == DEFAULT_ROBUSTA_MODEL
    assert llm.model == "gpt-4o"
    assert llm.api_base == f"https://api.robusta.dev/llm/{DEFAULT_ROBUSTA_MODEL}"


def test_config_get_llm_no_default_model_fallback_to_first_available_model(
    server_config: Config, monkeypatch
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "access_key_id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_access_key")
    server_config.llm_model_registry._default_robusta_model = None  # type: ignore
    llm: DefaultLLM = server_config._get_llm()
    assert llm.name == "bedrock/custom_ai_model"
    assert llm.model == "bedrock/custom_ai_model"
    assert llm.api_key == "existing_api_key"


def test_config_get_llm_with_robusta_model_returns_updated_api_key(
    server_config: Config, storage_dal_mock
):
    llm: DefaultLLM = server_config._get_llm(ROBUSTA_SONNET_4_MODEL)
    assert llm.name == ROBUSTA_SONNET_4_MODEL
    assert llm.api_key == "mock_account_id mock_session_token"

    storage_dal_mock.get_ai_credentials.return_value = (
        "mock_account_id",
        "new_session_token",
    )
    llm = server_config._get_llm(ROBUSTA_SONNET_4_MODEL)
    assert llm.api_key == "mock_account_id new_session_token"
