import yaml

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
