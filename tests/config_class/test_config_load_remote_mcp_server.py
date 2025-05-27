import yaml
import pytest
import os
from holmes.config import load_toolsets_definitions


# class DummyToolsetYamlFromConfig to bypass actual validations and test only load_custom_toolsets_config
class DummyToolsetYamlFromConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.config = kwargs.get("config", None)

    def set_path(self, path):
        self.path = path


@pytest.fixture(autouse=True)
def patch_toolset_yaml(monkeypatch):
    monkeypatch.setattr(
        "holmes.config.ToolsetYamlFromConfig", DummyToolsetYamlFromConfig
    )


toolsets_config_str = """
  mcp_test:
    url: "http://0.0.0.0:3005"
    icon_url: "https://registry.npmmirror.com/@lobehub/icons-static-png/1.46.0/files/light/mcp.png"
    description: "Roi test mcp that calculates BMI"
    config:
        headers:
            api_key: "{{env.API_KEY}}"
            header2: "test-headers2"
"""

env_vars = {
    "API_KEY": "glsa_sdj1q2o3prujpqfd",
}


def test_load_mcp_toolsets_definition():
    original_env = os.environ.copy()

    try:
        for key, value in env_vars.items():
            os.environ[key] = value

        toolsets_config = yaml.safe_load(toolsets_config_str)
        assert isinstance(toolsets_config, dict)
        definitions = load_toolsets_definitions(toolsets=toolsets_config, path="env")
        assert len(definitions) == 1
        mcp_test = definitions[0]
        config = mcp_test.config
        assert config
        assert config.get("headers", {}).get("api_key") == "glsa_sdj1q2o3prujpqfd"

    finally:
        os.environ.clear()
        os.environ.update(original_env)
