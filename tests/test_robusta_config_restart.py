import base64
import json
import os
import signal
import threading

import pytest
import yaml

import server
from holmes.clients.robusta_client import MODELS_URL
from holmes.config import Config
from holmes.core.supabase_dal import SupabaseDal


def _token(password: str = "secret") -> str:
    fields = {
        "store_url": "https://store.example.com",
        "api_key": "api-key",
        "account_id": "account",
        "email": "holmes@example.com",
        "password": password,
    }
    return base64.b64encode(json.dumps(fields).encode()).decode()


def _write_config(path, cluster_name="prod", token=None, **global_config):
    sinks = [{"slack_sink": {"name": "alerts", "api_key": "xoxb"}}]
    if token is not None:
        sinks.append({"robusta_sink": {"name": "robusta_ui_sink", "token": token}})
    content = {
        "global_config": {"cluster_name": cluster_name, **global_config},
        "sinks_config": sinks,
        "active_playbooks": [],
    }
    path.write_text(yaml.safe_dump(content))


@pytest.fixture
def robusta_config(tmp_path, monkeypatch, responses):
    path = tmp_path / "active_playbooks.yaml"
    monkeypatch.setattr("holmes.common.env_vars.ROBUSTA_CONFIG_PATH", str(path))
    monkeypatch.setattr("holmes.core.supabase_dal.ROBUSTA_CONFIG_PATH", str(path))
    # load_from_env exports CLUSTER_NAME itself, which monkeypatch would not undo.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv("CLUSTER_NAME", raising=False)
    monkeypatch.delenv("ROBUSTA_UI_TOKEN", raising=False)
    # A connected DAL would reach the platform and patch postgrest globally.
    monkeypatch.setattr(
        SupabaseDal, "_SupabaseDal__connect", lambda self, options: None
    )
    monkeypatch.setattr(SupabaseDal, "patch_postgrest_execute", lambda self: None)
    # Startup fetches the model catalog when it finds platform credentials.
    responses.assert_all_requests_are_fired = False
    responses.post(MODELS_URL, json={"models": {}})
    return path


@pytest.fixture
def sigterms(monkeypatch):
    sent = []
    monkeypatch.setattr(
        os, "kill", lambda pid, sig: sent.append(sig) if pid == os.getpid() else None
    )
    return sent


def _start_holmes(monkeypatch):
    config = Config.load_from_env()
    dal = SupabaseDal(
        config.cluster_name
    )  # holmes.config.SupabaseDal is mocked session-wide
    monkeypatch.setattr(server, "config", config)
    monkeypatch.setattr(server, "dal", dal)
    return config


def test_cluster_rename_restarts_holmes(robusta_config, monkeypatch, sigterms):
    _write_config(robusta_config, cluster_name="prod")
    assert _start_holmes(monkeypatch).cluster_name == "prod"
    assert server._restart_if_robusta_identity_changed() is False

    _write_config(robusta_config, cluster_name="prod-v2")
    monkeypatch.setattr(server, "TOOLSET_STATUS_REFRESH_INTERVAL_SECONDS", 1)
    running = set(threading.enumerate())
    server._toolset_status_refresh_loop()
    (refresh,) = {
        t for t in set(threading.enumerate()) - running if t.name == "toolset-refresh"
    }
    refresh.join(timeout=30)

    assert not refresh.is_alive()
    assert sigterms == [signal.SIGTERM]


def test_declared_cluster_name_ignores_the_mounted_config(
    robusta_config, monkeypatch, sigterms
):
    monkeypatch.setenv("CLUSTER_NAME", "from-env")
    _write_config(robusta_config, cluster_name="prod")
    assert _start_holmes(monkeypatch).cluster_name == "from-env"

    _write_config(robusta_config, cluster_name="prod-v2")
    assert server._restart_if_robusta_identity_changed() is False
    assert sigterms == []


def test_config_mounted_after_startup_restarts_holmes(
    robusta_config, monkeypatch, sigterms
):
    assert _start_holmes(monkeypatch).cluster_name is None

    _write_config(robusta_config, cluster_name="prod")
    assert server._restart_if_robusta_identity_changed() is True
    assert sigterms == [signal.SIGTERM]


def test_removed_config_keeps_holmes_running(robusta_config, monkeypatch, sigterms):
    _write_config(robusta_config, token=_token())
    _start_holmes(monkeypatch)

    robusta_config.unlink()
    assert server._restart_if_robusta_identity_changed() is False
    assert sigterms == []


def test_token_rotation_restarts_holmes(robusta_config, monkeypatch, sigterms):
    _write_config(robusta_config, token=_token("old"))
    _start_holmes(monkeypatch)
    assert server.dal.enabled

    _write_config(robusta_config, token=_token("new"))
    assert server._restart_if_robusta_identity_changed() is True
    assert sigterms == [signal.SIGTERM]


def test_runner_only_changes_keep_holmes_running(robusta_config, monkeypatch, sigterms):
    _write_config(robusta_config, token=_token())
    _start_holmes(monkeypatch)

    _write_config(robusta_config, token=_token(), grafana_api_key="rotated")
    assert server._restart_if_robusta_identity_changed() is False
    assert sigterms == []


def test_invalid_new_token_keeps_holmes_running(robusta_config, monkeypatch, sigterms):
    _write_config(robusta_config, token=_token())
    _start_holmes(monkeypatch)

    _write_config(robusta_config, token="not base64!")
    assert server._restart_if_robusta_identity_changed() is False
    assert sigterms == []
