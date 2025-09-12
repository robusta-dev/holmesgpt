from pathlib import Path
from typing import Optional
import pytest
import yaml

from holmes.config import Config

DEFAULT_ROBUSTA_MODEL = "Robusta/gpt-5-mini preview (minimal reasoning)"
ROBUSTA_SONNET_4_MODEL = "Robusta/sonnet-4 preview"
ROBUSTA_MODELS = [
    ROBUSTA_SONNET_4_MODEL,
    "Robusta/gpt-5-mini preview (minimal reasoning)",
    "Robusta/gpt-5 preview (minimal reasoning)",
    "Robusta/gpt-4o",
]


@pytest.fixture(autouse=True, scope="function")
def clear_all_caches():
    """Clear all function caches that may affect test isolation."""
    try:
        import holmes.clients.robusta_client as rc

        rc.fetch_robusta_models.cache_clear()
        rc.fetch_holmes_info.cache_clear()
    except Exception:
        pass


@pytest.fixture(autouse=False)
def server_config(tmp_path, monkeypatch, responses):
    responses.post(
        "https://api.robusta.dev/api/llm/models",
        json={
            "models": ROBUSTA_MODELS,
            "default_model": DEFAULT_ROBUSTA_MODEL,
        },
    )
    temp_config_file = tmp_path / "custom_toolset.yaml"
    data = {
        "our_local_model": {
            "model": "bedrock/custom_ai_model",
            "api_key": "existing_api_key",
        },
    }

    temp_config_file.write_text(yaml.dump(data))
    monkeypatch.setattr(
        "holmes.core.llm.MODEL_LIST_FILE_LOCATION", str(temp_config_file)
    )
    monkeypatch.setattr("holmes.core.llm.ROBUSTA_AI", True)
    monkeypatch.setenv("CLUSTER_NAME", "test-cluster")

    return Config.load_from_env()


@pytest.fixture(autouse=False)
def cli_config():
    return get_cli_config()


def get_cli_config(config_file: Optional[Path] = None, **kwargs):
    return Config.load_from_file(config_file, **kwargs)
