import json

import pytest

from holmes.plugins.destinations.webhook import (
    InvalidWebhookHeadersError,
    resolve_webhook_headers,
)
from holmes.plugins.destinations.webhook.utils import resolve_webhook_headers as resolve_direct


def test_configured_headers_are_returned_unchanged():
    headers = {"X-Custom": "value", "Authorization": "Bearer token"}
    assert resolve_webhook_headers(headers, None) == headers


def test_configured_headers_take_precedence_over_env():
    assert resolve_webhook_headers(
        {"from": "config"}, '{"from": "env"}'
    ) == {"from": "config"}


def test_empty_configured_headers_fall_back_to_env():
    assert resolve_webhook_headers({}, '{"from": "env"}') == {"from": "env"}


def test_none_configured_headers_parse_valid_env_json():
    assert resolve_webhook_headers(None, '{"X-Test": "value"}') == {
        "X-Test": "value"
    }


def test_none_configured_and_none_env_returns_empty_dict():
    assert resolve_webhook_headers(None, None) == {}


def test_none_configured_and_empty_env_returns_empty_dict():
    assert resolve_webhook_headers(None, "") == {}


def test_env_headers_support_nested_json_values():
    env = json.dumps({"headers": {"X": "Y"}, "count": 3})
    assert resolve_webhook_headers(None, env) == {
        "headers": {"X": "Y"},
        "count": 3,
    }


def test_invalid_env_json_raises_invalid_headers_error():
    with pytest.raises(InvalidWebhookHeadersError):
        resolve_webhook_headers(None, "{not valid json")


def test_env_json_non_object_raises_invalid_headers_error():
    with pytest.raises(InvalidWebhookHeadersError):
        resolve_webhook_headers(None, '["not", "an", "object"]')


def test_env_json_scalar_raises_invalid_headers_error():
    with pytest.raises(InvalidWebhookHeadersError):
        resolve_webhook_headers(None, '"just a string"')


def test_configured_non_mapping_raises_invalid_headers_error():
    with pytest.raises(InvalidWebhookHeadersError):
        resolve_webhook_headers("not-a-dict", None)


def test_configured_list_raises_invalid_headers_error():
    with pytest.raises(InvalidWebhookHeadersError):
        resolve_webhook_headers(["X: value"], None)


def test_result_is_not_the_same_object_as_configured_headers():
    configured = {"X": "value"}
    result = resolve_webhook_headers(configured, None)
    result["X"] = "mutated"
    assert configured == {"X": "value"}


def test_resolved_headers_can_be_passed_to_webhook_destination():
    from holmes.plugins.destinations.webhook.plugin import WebhookDestination

    headers = resolve_webhook_headers(None, '{"X-Test": "value"}')
    destination = WebhookDestination(
        method="POST",
        webhook_url="https://hooks.example.com/holmes/checks",
        headers=headers,
    )
    assert destination.headers["X-Test"] == "value"
    assert destination.headers["Content-Type"] == "application/json"


def test_direct_module_import_matches_package_export():
    assert resolve_direct is resolve_webhook_headers