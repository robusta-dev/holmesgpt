"""Tests for the Grafana Tempo API wrapper."""

import pytest
from unittest.mock import MagicMock, patch
from requests.exceptions import RequestException, HTTPError  # type: ignore

from holmes.plugins.toolsets.grafana.grafana_tempo_api import GrafanaTempoAPI
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import GrafanaTempoConfig


class TestGrafanaTempoAPI:
    """Test the GrafanaTempoAPI wrapper class."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return GrafanaTempoConfig(
            url="https://grafana.example.com",
            api_key="test-api-key",
            grafana_datasource_uid="tempo-uid",
        )

    @pytest.fixture
    def api_get(self, config):
        """Create API instance with GET method (default)."""
        return GrafanaTempoAPI(config, use_post=False)

    @pytest.fixture
    def api_post(self, config):
        """Create API instance with POST method."""
        return GrafanaTempoAPI(config, use_post=True)

    def test_initialization(self, config):
        """Test API initialization with config."""
        api = GrafanaTempoAPI(config)
        assert api.config == config
        assert api.use_post is False
        assert (
            api.base_url
            == "https://grafana.example.com/api/datasources/proxy/uid/tempo-uid"
        )
        assert "Authorization" in api.headers
        assert api.headers["Authorization"] == "Bearer test-api-key"

    def test_initialization_with_post(self, config):
        """Test API initialization with POST enabled."""
        api = GrafanaTempoAPI(config, use_post=True)
        assert api.use_post is True

    @patch("requests.get")
    def test_query_echo_endpoint_get(self, mock_get, api_get):
        """Test query_echo_endpoint with GET method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.query_echo_endpoint()

        assert result == {"status": "ok"}
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/echo",
            headers=api_get.headers,
            params=None,
            timeout=30,
        )

    @patch("requests.post")
    def test_query_echo_endpoint_post(self, mock_post, api_post):
        """Test query_echo_endpoint with POST method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = api_post.query_echo_endpoint()

        assert result == {"status": "ok"}
        mock_post.assert_called_once_with(
            f"{api_post.base_url}/api/echo",
            headers=api_post.headers,
            json={},
            timeout=30,
        )

    @patch("requests.get")
    def test_query_trace_by_id_v2(self, mock_get, api_get):
        """Test query_trace_by_id_v2 method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"traceID": "123abc"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.query_trace_by_id_v2("123abc", start=1000, end=2000)

        assert result == {"traceID": "123abc"}
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/v2/traces/123abc",
            headers=api_get.headers,
            params={"start": 1000, "end": 2000},
            timeout=30,
        )

    @patch("requests.get")
    def test_query_trace_by_id_v2_no_time_params(self, mock_get, api_get):
        """Test query_trace_by_id_v2 without time parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"traceID": "123abc"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.query_trace_by_id_v2("123abc")

        assert result == {"traceID": "123abc"}
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/v2/traces/123abc",
            headers=api_get.headers,
            params={},
            timeout=30,
        )

    @patch("requests.get")
    def test_search_traces_by_tags(self, mock_get, api_get):
        """Test search_traces_by_tags method with all parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"traces": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.search_traces_by_tags(
            tags="service=api",
            min_duration="5s",
            max_duration="30s",
            limit=100,
            start=1000,
            end=2000,
            spss=5,
        )

        assert result == {"traces": []}
        expected_params = {
            "tags": "service=api",
            "minDuration": "5s",
            "maxDuration": "30s",
            "limit": 100,
            "start": 1000,
            "end": 2000,
            "spss": 5,
        }
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/search",
            headers=api_get.headers,
            params=expected_params,
            timeout=30,
        )

    @patch("requests.get")
    def test_search_traces_by_query(self, mock_get, api_get):
        """Test search_traces_by_query method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"traces": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.search_traces_by_query(
            q='{service="api"}',
            limit=100,
            start=1000,
            end=2000,
            spss=5,
        )

        assert result == {"traces": []}
        expected_params = {
            "q": '{service="api"}',
            "limit": 100,
            "start": 1000,
            "end": 2000,
            "spss": 5,
        }
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/search",
            headers=api_get.headers,
            params=expected_params,
            timeout=30,
        )

    @patch("requests.get")
    def test_search_tag_names_v2(self, mock_get, api_get):
        """Test search_tag_names_v2 method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"scopes": {"resource": ["service.name"]}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.search_tag_names_v2(
            scope="resource",
            q='{service="api"}',
            start=1000,
            end=2000,
            limit=50,
            max_stale_values=100,
        )

        assert result == {"scopes": {"resource": ["service.name"]}}
        expected_params = {
            "scope": "resource",
            "q": '{service="api"}',
            "start": 1000,
            "end": 2000,
            "limit": 50,
            "maxStaleValues": 100,
        }
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/v2/search/tags",
            headers=api_get.headers,
            params=expected_params,
            timeout=30,
        )

    @patch("requests.get")
    def test_search_tag_values_v2(self, mock_get, api_get):
        """Test search_tag_values_v2 method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"tagValues": ["api", "web", "db"]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.search_tag_values_v2(
            tag="service.name",
            q='{resource.cluster="us-east-1"}',
            start=1000,
            end=2000,
            limit=50,
            max_stale_values=100,
        )

        assert result == {"tagValues": ["api", "web", "db"]}
        expected_params = {
            "q": '{resource.cluster="us-east-1"}',
            "start": 1000,
            "end": 2000,
            "limit": 50,
            "maxStaleValues": 100,
        }
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/v2/search/tag/service.name/values",
            headers=api_get.headers,
            params=expected_params,
            timeout=30,
        )

    @patch("requests.get")
    def test_query_metrics_instant(self, mock_get, api_get):
        """Test query_metrics_instant method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"metrics": {"value": 123}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.query_metrics_instant(
            q="{status=error} | count_over_time() by (resource.service.name)",
            start=1000,
            end=2000,
            since="1h",
        )

        assert result == {"metrics": {"value": 123}}
        expected_params = {
            "q": "{status=error} | count_over_time() by (resource.service.name)",
            "start": 1000,
            "end": 2000,
            "since": "1h",
        }
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/metrics/query",
            headers=api_get.headers,
            params=expected_params,
            timeout=30,
        )

    @patch("requests.get")
    def test_query_metrics_range(self, mock_get, api_get):
        """Test query_metrics_range method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "series": [{"timestamps": [1000, 2000], "values": [10, 20]}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.query_metrics_range(
            q='{resource.service.name="myservice"} | rate()',
            step="1m",
            start=1000,
            end=2000,
            since="3h",
            exemplars=100,
        )

        assert result == {"series": [{"timestamps": [1000, 2000], "values": [10, 20]}]}
        expected_params = {
            "q": '{resource.service.name="myservice"} | rate()',
            "step": "1m",
            "start": 1000,
            "end": 2000,
            "since": "3h",
            "exemplars": 100,
        }
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/metrics/query_range",
            headers=api_get.headers,
            params=expected_params,
            timeout=30,
        )

    @patch("requests.get")
    def test_query_metrics_instant_required_only(self, mock_get, api_get):
        """Test query_metrics_instant with only required parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"metrics": {"value": 123}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api_get.query_metrics_instant(q='{service="api"} | count()')

        assert result == {"metrics": {"value": 123}}
        expected_params = {"q": '{service="api"} | count()'}
        mock_get.assert_called_once_with(
            f"{api_get.base_url}/api/metrics/query",
            headers=api_get.headers,
            params=expected_params,
            timeout=30,
        )

    @patch("requests.get")
    def test_error_handling(self, mock_get, api_get):
        """Test error handling for failed requests."""
        mock_get.side_effect = RequestException("Connection error")

        with pytest.raises(Exception) as exc_info:
            api_get.query_echo_endpoint()

        assert "Failed to query Tempo API" in str(exc_info.value)

    @patch("requests.get")
    def test_http_error_handling(self, mock_get, api_get):
        """Test handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            api_get.query_trace_by_id_v2("nonexistent")

        assert "Failed to query Tempo API" in str(exc_info.value)

    @patch("requests.get")
    def test_special_characters_in_path_params(self, mock_get, api_get):
        """Test handling of special characters in path parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"tagValues": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Tag with special characters that need encoding
        api_get.search_tag_values_v2(tag="service/name:test")

        # Check that the URL was properly encoded
        expected_url = f"{api_get.base_url}/api/search/tag/service%2Fname%3Atest/values"
        mock_get.assert_called_once_with(
            expected_url,
            headers=api_get.headers,
            params={},
            timeout=30,
        )


@pytest.mark.integration
class TestGrafanaTempoAPIIntegration:
    """Integration tests for Grafana Tempo API (requires real Tempo instance)."""

    @pytest.fixture
    def config(self):
        """Create configuration for integration tests."""
        # These would be loaded from environment variables in real tests
        return GrafanaTempoConfig(
            url="http://localhost:3000",  # Grafana URL
            api_key="test-key",
            grafana_datasource_uid="tempo-datasource",
        )

    @pytest.mark.skip(reason="Requires actual Tempo instance")
    def test_echo_endpoint_integration(self, config):
        """Test echo endpoint against real Tempo."""
        api = GrafanaTempoAPI(config)
        result = api.query_echo_endpoint()
        assert "echo" in result or "status" in result

    @pytest.mark.skip(reason="Requires actual Tempo instance")
    def test_search_traces_by_tags_integration(self, config):
        """Test tag-based trace search against real Tempo."""
        api = GrafanaTempoAPI(config)
        result = api.search_traces_by_tags(tags="service.name=frontend", limit=10)
        assert "traces" in result

    @pytest.mark.skip(reason="Requires actual Tempo instance")
    def test_search_traces_by_query_integration(self, config):
        """Test TraceQL trace search against real Tempo."""
        api = GrafanaTempoAPI(config)
        result = api.search_traces_by_query(q='{service.name="frontend"}', limit=10)
        assert "traces" in result

    @pytest.mark.skip(reason="Requires actual Tempo instance")
    def test_search_tag_names_integration(self, config):
        """Test tag name search against real Tempo."""
        api = GrafanaTempoAPI(config)
        result = api.search_tag_names_v2()
        assert "scopes" in result or "tagNames" in result
