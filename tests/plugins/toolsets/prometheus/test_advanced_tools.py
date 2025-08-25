import json
from unittest.mock import MagicMock, patch

import pytest

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.prometheus.prometheus import (
    AnalyzeMetricByDimensions,
    CompareMetricPeriods,
    DetectMetricAnomalies,
    FindTopMetricValues,
    PrometheusConfig,
    PrometheusToolset,
)


@pytest.fixture
def prometheus_toolset():
    """Create a PrometheusToolset with mock config"""
    toolset = PrometheusToolset()
    toolset.config = PrometheusConfig(
        prometheus_url="http://prometheus:9090/",
        prometheus_ssl_enabled=False,
    )
    return toolset


class TestAnalyzeMetricByDimensions:
    def test_basic_metric_analysis(self, prometheus_toolset):
        tool = AnalyzeMetricByDimensions(toolset=prometheus_toolset)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "result": [
                    {
                        "metric": {"endpoint": "/api/users", "method": "GET"},
                        "value": [1234567890, "0.95"],
                    },
                    {
                        "metric": {"endpoint": "/api/products", "method": "POST"},
                        "value": [1234567890, "1.2"],
                    },
                ]
            }
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke(
                {
                    "metric_name": "http_request_duration_seconds",
                    "group_by": ["endpoint", "method"],
                    "filters": {"service": "api"},
                    "time_range": "1h",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            assert "result" in json.loads(result.data)

            # Verify the query was constructed correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "query" in call_args[1]["data"]
            query = call_args[1]["data"]["query"]
            assert "http_request_duration_seconds" in query
            assert 'service="api"' in query
            assert "endpoint" in query
            assert "method" in query

    def test_histogram_percentile_aggregation(self, prometheus_toolset):
        tool = AnalyzeMetricByDimensions(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"result": []}}

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke(
                {
                    "metric_name": "http_request_duration_seconds",
                    "aggregation": "p95",
                    "time_range": "5m",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify histogram_quantile was used
            call_args = mock_post.call_args
            query = call_args[1]["data"]["query"]
            assert "histogram_quantile(0.95" in query
            assert "_bucket" in query

    def test_missing_prometheus_url(self, prometheus_toolset):
        tool = AnalyzeMetricByDimensions(toolset=prometheus_toolset)
        prometheus_toolset.config = None

        result = tool._invoke({"metric_name": "test_metric"})

        assert result.status == ToolResultStatus.ERROR
        assert "Prometheus is not configured" in result.error


class TestFindTopMetricValues:
    def test_find_top_values(self, prometheus_toolset):
        tool = FindTopMetricValues(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "result": [
                    {"metric": {"endpoint": "/slow"}, "value": [1234567890, "2.5"]},
                    {"metric": {"endpoint": "/slower"}, "value": [1234567890, "3.1"]},
                ]
            }
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke(
                {
                    "metric_name": "request_duration",
                    "group_by_label": "endpoint",
                    "top_n": 5,
                    "time_range": "30m",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify topk was used
            call_args = mock_post.call_args
            query = call_args[1]["data"]["query"]
            assert "topk(5" in query
            assert "endpoint" in query

    def test_histogram_metric_top_values(self, prometheus_toolset):
        tool = FindTopMetricValues(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"result": []}}

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke(
                {
                    "metric_name": "latency_histogram",
                    "group_by_label": "service",
                    "percentile": 0.99,
                    "top_n": 10,
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify histogram_quantile was used for percentile
            call_args = mock_post.call_args
            query = call_args[1]["data"]["query"]
            assert "histogram_quantile(0.99" in query
            assert "topk(10" in query


class TestCompareMetricPeriods:
    def test_compare_periods(self, prometheus_toolset):
        tool = CompareMetricPeriods(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "result": [
                    {"metric": {"endpoint": "/api"}, "value": [1234567890, "15.5"]}
                ]
            }
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke(
                {
                    "metric_name": "errors_total",
                    "current_period": "1h",
                    "comparison_offset": "24h",
                    "group_by": ["endpoint"],
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify offset comparison query
            call_args = mock_post.call_args
            query = call_args[1]["data"]["query"]
            assert "offset 24h" in query
            assert "errors_total" in query
            assert "endpoint" in query
            # Should calculate percentage change
            assert "*" in query and "100" in query

    def test_compare_without_grouping(self, prometheus_toolset):
        tool = CompareMetricPeriods(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"result": []}}

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke(
                {
                    "metric_name": "cpu_usage",
                    "current_period": "5m",
                    "comparison_offset": "1h",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify no grouping clause
            call_args = mock_post.call_args
            query = call_args[1]["data"]["query"]
            assert "by (" not in query


class TestDetectMetricAnomalies:
    def test_anomaly_detection(self, prometheus_toolset):
        tool = DetectMetricAnomalies(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "result": [{"metric": {"pod": "pod-1"}, "value": [1234567890, "5.2"]}]
            }
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke(
                {
                    "metric_name": "response_time",
                    "sensitivity": 2.5,
                    "lookback_window": "6h",
                    "group_by": ["pod"],
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify z-score calculation
            call_args = mock_post.call_args
            query = call_args[1]["data"]["query"]
            assert "stddev_over_time" in query
            assert "avg_over_time" in query
            assert "response_time" in query
            assert "> 2.5" in query
            assert "6h" in query

    def test_default_sensitivity(self, prometheus_toolset):
        tool = DetectMetricAnomalies(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"result": []}}

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = tool._invoke({"metric_name": "error_rate"})

            assert result.status == ToolResultStatus.SUCCESS

            # Verify default sensitivity of 3
            call_args = mock_post.call_args
            query = call_args[1]["data"]["query"]
            assert "> 3" in query

    def test_query_failure(self, prometheus_toolset):
        tool = DetectMetricAnomalies(toolset=prometheus_toolset)

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad query"

        with patch("requests.post", return_value=mock_response):
            result = tool._invoke({"metric_name": "test_metric"})

            assert result.status == ToolResultStatus.ERROR
            assert "400" in result.error
            assert "Bad query" in result.error


class TestToolIntegration:
    """Test that tools are properly integrated into the toolset"""

    def test_tools_in_toolset(self):
        toolset = PrometheusToolset()
        tool_names = [tool.name for tool in toolset.tools]

        assert "analyze_metric_by_dimensions" in tool_names
        assert "find_top_metric_values" in tool_names
        assert "compare_metric_periods" in tool_names
        assert "detect_metric_anomalies" in tool_names

    def test_tool_one_liners(self, prometheus_toolset):
        # Test that each tool generates appropriate one-liner descriptions
        tools = [
            AnalyzeMetricByDimensions(toolset=prometheus_toolset),
            FindTopMetricValues(toolset=prometheus_toolset),
            CompareMetricPeriods(toolset=prometheus_toolset),
            DetectMetricAnomalies(toolset=prometheus_toolset),
        ]

        for tool in tools:
            one_liner = tool.get_parameterized_one_liner({"metric_name": "test_metric"})
            assert "Prometheus" in one_liner
            assert "test_metric" in one_liner
