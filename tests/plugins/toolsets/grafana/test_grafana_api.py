import pytest
from unittest.mock import Mock, patch
import requests  # type: ignore

from holmes.plugins.toolsets.grafana.common import GrafanaConfig
from holmes.plugins.toolsets.grafana.grafana_api import grafana_health_check


@pytest.fixture
def mock_requests_get():
    """Fixture to mock requests.get"""
    with patch("holmes.plugins.toolsets.grafana.grafana_api.requests.get") as mock:
        yield mock


class TestGrafanaHealthCheck:
    """Test cases for grafana_health_check function"""

    def test_first_url_succeeds(self, mock_requests_get):
        """Test that function returns True when first URL succeeds"""
        config = GrafanaConfig(
            url="http://grafana:3000",
            healthcheck_url="http://custom-health:8080/health",
            grafana_datasource_uid="loki-uid",
        )

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        success, error = grafana_health_check(config)

        assert success is True
        assert error == ""
        assert mock_requests_get.call_count == 1

    def test_second_url_succeeds_after_first_fails(self, mock_requests_get):
        """Test that function tries second URL when first fails"""
        config = GrafanaConfig(
            url="http://grafana:3000",
            healthcheck_url="http://custom-health:8080/health",
            grafana_datasource_uid="loki-uid",
        )

        mock_requests_get.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(raise_for_status=Mock()),
        ]

        success, error = grafana_health_check(config)
        assert success is True
        assert error == ""
        assert mock_requests_get.call_count == 2

    def test_all_urls_fail(self, mock_requests_get):
        """Test that function returns False with error when all URLs fail"""
        config = GrafanaConfig(
            url="http://grafana:3000",
            healthcheck_url="http://custom-health:8080/health",
            grafana_datasource_uid="loki-uid",
        )

        mock_requests_get.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.Timeout("Timeout"),
            requests.exceptions.Timeout("Timeout"),
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.ConnectionError("Connection failed"),
        ]

        success, error = grafana_health_check(config)

        assert success is False
        assert "Failed to fetch grafana health status" in error
        assert mock_requests_get.call_count == 6

    def test_http_500_error_retried(self, mock_requests_get):
        """Test that 5xx errors are retried by backoff decorator"""
        config = GrafanaConfig(url="http://grafana:3000")

        error_response = Mock()
        error_response.status_code = 500
        http_error = requests.exceptions.HTTPError()
        http_error.response = error_response

        mock_requests_get.side_effect = http_error

        success, _ = grafana_health_check(config)

        assert success is False
        assert mock_requests_get.call_count == 2

    def test_http_4xx_error_not_retried(self, mock_requests_get):
        """Test that 4xx errors are not retried (giveup condition)"""
        config = GrafanaConfig(url="http://grafana:3000")

        error_response = Mock()
        error_response.status_code = 404
        http_error = requests.exceptions.HTTPError()
        http_error.response = error_response

        mock_requests_get.side_effect = http_error

        success, _ = grafana_health_check(config)

        assert success is False
        # Should only try once due to giveup condition
        assert mock_requests_get.call_count == 1
