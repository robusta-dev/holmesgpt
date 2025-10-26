import os

import yaml

from holmes.config import Config

toolsets_config_str = """
  mcp_test:
    type: "mcp"
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
    # TODO: don't mock env var that way.
    original_env = os.environ.copy()

    try:
        for key, value in env_vars.items():
            os.environ[key] = value

        toolsets_config = yaml.safe_load(toolsets_config_str)
        assert isinstance(toolsets_config, dict)
        config = Config(mcp_servers=toolsets_config)
        mcp_servers = config.toolset_manager._mcp_servers
        assert len(mcp_servers) == 1

        toolsets = config.toolset_manager._load_toolsets_definitions()
        mcp_test = config.toolset_manager._toolset_definitions_by_name["mcp_test"]
        assert mcp_test.config
        assert (
            mcp_test.config.get("headers", {}).get("api_key") == "glsa_sdj1q2o3prujpqfd"
        )

    finally:
        os.environ.clear()
        os.environ.update(original_env)
