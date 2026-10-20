"""ROB-1544: the HolmesStatus heartbeat must reach PostgREST with metadata as a
JSON object. The column is jsonb, so a JSON string there stays a string and
`metadata->>'key'` reads NULL.

Drives the real SupabaseDal + supabase client against the in-process fake from
test_supabase_dal_jwt_retry.
"""

import base64
import inspect
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from postgrest._sync.request_builder import (
    SyncQueryRequestBuilder,
    SyncSingleRequestBuilder,
)

import holmes.core.supabase_dal as supabase_dal
from holmes.core.supabase_dal import SupabaseDal
from holmes.utils.holmes_status import (
    refresh_holmes_status,
    update_holmes_status_in_db,
)
from tests.core.test_supabase_dal_jwt_retry import ANON_KEY, STORE_URL, FakeSupabase


class RecordingSupabase(FakeSupabase):
    def __init__(self):
        super().__init__()
        self.upserts: list = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/v1/HolmesStatus":
            self.upserts.append((request, json.loads(request.content)))
        return super().handle(request)


@pytest.fixture
def fake():
    return RecordingSupabase()


@pytest.fixture
def dal(fake, monkeypatch):
    monkeypatch.setattr(
        supabase_dal,
        "SupabaseRetryTransport",
        lambda **_: httpx.MockTransport(fake.handle),
    )
    monkeypatch.setattr(supabase_dal, "fetch_supabase_api_key", lambda *_: None)
    monkeypatch.setattr(supabase_dal, "KEY_CACHE", {})
    for builder in (SyncQueryRequestBuilder, SyncSingleRequestBuilder):
        monkeypatch.setattr(builder, "execute", inspect.unwrap(builder.execute))
    bundle = {
        "store_url": STORE_URL,
        "api_key": ANON_KEY,
        "account_id": "acc-1",
        "email": "svc@example.com",
        "password": "pw",
    }
    monkeypatch.setenv(
        "ROBUSTA_UI_TOKEN", base64.b64encode(json.dumps(bundle).encode()).decode()
    )
    d = SupabaseDal(cluster="test-cluster")
    yield d
    timer = d.client.auth._refresh_token_timer
    if timer:
        timer.cancel()


def _config():
    config = MagicMock()
    config.cluster_name = "test-cluster"
    config.should_try_robusta_ai = True
    config.get_models_list.return_value = ["gpt-4.1", "sonnet"]
    config.llm_model_registry.reads_robusta_catalog.return_value = True
    return config


@pytest.mark.parametrize("realtime_available", [True, False])
def test_heartbeat_sends_metadata_as_a_json_object(dal, fake, realtime_available):
    with patch("holmes.utils.holmes_status.ENABLE_CONVERSATION_WORKER", True), patch(
        "holmes.utils.holmes_status._detect_runner_namespace", return_value="ns"
    ):
        update_holmes_status_in_db(
            dal, _config(), realtime_available=realtime_available
        )

    ((request, body),) = fake.upserts
    assert request.method == "POST"
    assert request.url.params["on_conflict"] == "account_id, cluster_id"
    assert isinstance(body["metadata"], dict)
    assert body["metadata"]["supports_realtime_conversations"] is realtime_available
    assert body["metadata"]["namespace"] == "ns"
    # model is a text column holding a JSON list; it stays a string.
    assert json.loads(body["model"]) == ["gpt-4.1", "sonnet"]
    assert body["account_id"] == "acc-1"
    assert body["cluster_id"] == "test-cluster"


def test_periodic_heartbeat_keeps_metadata_an_object(dal, fake):
    with patch("holmes.utils.holmes_status.ENABLE_CONVERSATION_WORKER", True), patch(
        "holmes.utils.holmes_status._detect_runner_namespace", return_value=None
    ):
        update_holmes_status_in_db(dal, _config(), realtime_available=True)
        refresh_holmes_status(dal, _config())

    first, refreshed = (body["metadata"] for _, body in fake.upserts)
    assert isinstance(refreshed, dict)
    assert refreshed == first
    assert refreshed["supports_realtime_conversations"] is True


def test_heartbeat_without_cluster_name_writes_nothing(dal, fake):
    config = _config()
    config.cluster_name = None

    with pytest.raises(Exception, match="Cluster name is missing"):
        update_holmes_status_in_db(dal, config)
    assert fake.upserts == []
