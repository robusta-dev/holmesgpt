
import os
import yaml
from holmes.config import load_toolsets_definitions

toolsets_config_str = """
grafana/loki:
    config:
        api_key: "{{env.GRAFANA_API_KEY}}"
        url: "{{env.GRAFANA_URL}}"
        grafana_datasource_uid: "my_grafana_datasource_uid"
"""

env_vars = {
    "GRAFANA_API_KEY": "glsa_sdj1q2o3prujpqfd",
    "GRAFANA_URL": "https://my-grafana.com/"
}

def test_load_toolsets_definition():
    original_env = os.environ.copy()

    try:
        for key, value in env_vars.items():
            os.environ[key] = value

        toolsets_config = yaml.safe_load(toolsets_config_str)
        assert isinstance(toolsets_config, dict)
        definitions = load_toolsets_definitions(toolsets=toolsets_config, path="env")
        assert len(definitions) == 1
        grafana_loki = definitions[0]
        config = grafana_loki.config
        assert config
        assert config.get("api_key") == "glsa_sdj1q2o3prujpqfd"
        assert config.get("url") == "https://my-grafana.com/"
        assert config.get("grafana_datasource_uid") == "my_grafana_datasource_uid"

    finally:
        os.environ.clear()
        os.environ.update(original_env)
