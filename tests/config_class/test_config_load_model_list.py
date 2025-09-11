import yaml

from holmes.common.env_vars import ROBUSTA_API_ENDPOINT
from holmes.config import Config


def test_load_custom_toolsets_config_valid(monkeypatch, tmp_path):
    temp_config_file = tmp_path / "custom_toolset.yaml"
    data = {
        "model1": {"model": "abc", "api-key": "asd"},
        "azure": {"model": "{{ env.TEST }}", "api-key": "ddd"},
        "bedrock": {"model": "bbbb", "api-key": "asfffd"},
    }
    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )
    monkeypatch.setenv("TEST", "test-value")

    config = Config()
    assert isinstance(config.llm_model_registry.models, dict)
    assert len(list(config.llm_model_registry.models.keys())) == 3
    az = config.llm_model_registry.models.get("azure")
    assert az.get("model") == "test-value"


def test_config_load_model_list_valid_with_robusta_ai(server_config: Config):
    assert isinstance(server_config.llm_model_registry.models, dict)
    assert len(list(server_config.llm_model_registry.models.keys())) == 5
    assert (
        server_config.llm_model_registry.models["our_local_model"]["model"]
        == "bedrock/custom_ai_model"
    )

    sonnet_model = server_config.llm_model_registry.models["Robusta/sonnet-4 preview"]

    assert (
        sonnet_model.get("base_url")
        == f"{ROBUSTA_API_ENDPOINT}/llm/Robusta/sonnet-4 preview"
    )
    assert sonnet_model.get("name") == "Robusta/sonnet-4 preview"
    assert sonnet_model.get("is_robusta_model")

    assert (
        server_config.llm_model_registry.default_robusta_model
        == "Robusta/gpt-5-mini preview (minimal reasoning)"
    )
