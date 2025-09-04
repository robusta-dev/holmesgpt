import responses
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
    monkeypatch.setattr("holmes.config.MODEL_LIST_FILE_LOCATION", str(temp_config_file))
    monkeypatch.setenv("TEST", "test-value")

    config = Config()
    assert isinstance(config._model_list, dict)
    assert len(list(config._model_list.keys())) == 3
    az = config._model_list.get("azure")
    assert az.get("model") == "test-value"


@responses.activate
def test_load_custom_toolsets_config_valid_with_robusta_ai(monkeypatch, tmp_path):
    responses.post(
        "https://api.robusta.dev/api/llm/models",
        json={
            "models": [
                "Robusta/sonnet-4 preview",
                "Robusta/gpt-5-mini preview (minimal reasoning)",
                "Robusta/gpt-5 preview (minimal reasoning)",
                "Robusta/gpt-4o",
            ],
            "default_model": "Robusta/gpt-5-mini preview (minimal reasoning)",
        },
    )
    temp_config_file = tmp_path / "custom_toolset.yaml"
    data = {
        "bedrock": {"model": "bbbb", "api-key": "asfffd"},
    }

    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr("holmes.config.MODEL_LIST_FILE_LOCATION", str(temp_config_file))
    monkeypatch.setattr("holmes.config.ROBUSTA_AI", True)
    monkeypatch.setenv("CLUSTER_NAME", "test-cluster")

    config = Config.load_from_env()
    assert isinstance(config._model_list, dict)
    assert len(list(config._model_list.keys())) == 5
    assert config._model_list.get("bedrock").get("model") == "bbbb"

    sonnet_model = config._model_list["Robusta/sonnet-4 preview"]

    assert (
        sonnet_model.get("base_url")
        == f"{ROBUSTA_API_ENDPOINT}/llm/Robusta/sonnet-4 preview"
    )
    assert sonnet_model.get("name") == "Robusta/sonnet-4 preview"
    assert sonnet_model.get("is_robusta_model")

    assert (
        config._default_robusta_model
        == "Robusta/gpt-5-mini preview (minimal reasoning)"
    )
