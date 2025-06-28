from http import HTTPStatus
from unittest import mock
from holmes.config import Config
from holmes.clients.robusta_client import fetch_holmes_info
import responses


@responses.activate
def test_config_load_version_matches_latest():
    fetch_holmes_info.cache_clear()
    with mock.patch("holmes.config.get_version", return_value="1.0.0"):
        responses.add(
            responses.GET,
            "https://api.robusta.dev/api/holmes/get_info",
            json={"latest_version": "1.0.0"},
        )
        config = Config.load_from_env()
        assert config.is_latest_version


@responses.activate
def test_config_load_version_matches_latest_on_branch():
    fetch_holmes_info.cache_clear()
    with mock.patch("holmes.config.get_version", return_value="1.0.0-dev"):
        responses.add(
            responses.GET,
            "https://api.robusta.dev/api/holmes/get_info",
            json={"latest_version": "1.0.0"},
        )
        config = Config.load_from_env()
        assert config.is_latest_version


@responses.activate
def test_config_load_version_old():
    fetch_holmes_info.cache_clear()
    with mock.patch("holmes.config.get_version", return_value="0.9.0"):
        responses.add(
            responses.GET,
            "https://api.robusta.dev/api/holmes/get_info",
            json={"latest_version": "1.0.0"},
        )
        config = Config.load_from_env()
        assert not config.is_latest_version


@responses.activate
def test_config_load_failed_fetch_version():
    fetch_holmes_info.cache_clear()
    responses.add(
        responses.GET,
        "https://api.robusta.dev/api/holmes/get_info",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )
    config = Config.load_from_env()
    assert config._holmes_info is None
    assert config.is_latest_version
