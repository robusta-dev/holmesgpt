from unittest.mock import patch, ANY

import pytest

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.grafana.common import GrafanaTempoConfig
from holmes.plugins.toolsets.grafana.grafana_tempo_api import TempoAPIError
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import (
    GrafanaTempoToolset,
    SearchTracesByQuery,
    SearchTracesByTags,
    QueryTraceById,
    SearchTagNames,
    SearchTagValues,
    QueryMetricsInstant,
    QueryMetricsRange,
)


@pytest.fixture
def tempo_config():
    """Create a test Tempo configuration."""
    return GrafanaTempoConfig(
        api_key="test_key",
        url="http://localhost:3000",
        grafana_datasource_uid="tempo_uid",
    )


@pytest.fixture
def tempo_toolset(tempo_config):
    """Create a GrafanaTempoToolset instance with test config."""
    toolset = GrafanaTempoToolset()
    toolset._grafana_config = tempo_config
    return toolset


class TestSearchTracesByQuery:
    def test_search_traces_by_query_success(self, tempo_toolset):
        """Test successful trace search using TraceQL."""
        tool = SearchTracesByQuery(tempo_toolset)

        mock_response = {
            "traces": [
                {"traceID": "123", "durationMs": 100},
                {"traceID": "456", "durationMs": 200},
            ]
        }

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_traces_by_query"
        ) as mock_search:
            mock_search.return_value = mock_response

            result = tool._invoke(
                {
                    "q": '{resource.service.name="api"}',
                    "limit": 10,
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            assert "traces" in result.data
            mock_search.assert_called_once_with(
                q='{resource.service.name="api"}',
                limit=10,
                start=ANY,
                end=ANY,
                spss=None,
            )

    def test_search_traces_by_query_error(self, tempo_toolset):
        """Test error handling in trace search."""
        tool = SearchTracesByQuery(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_traces_by_query"
        ) as mock_search:
            mock_search.side_effect = Exception("API Error")

            result = tool._invoke({"q": "{invalid}"})

            assert result.status == ToolResultStatus.ERROR
            assert "API Error" in result.error

    def test_search_traces_by_query_tempo_api_error(self, tempo_toolset):
        """Test that Tempo API errors are properly propagated with details."""
        tool = SearchTracesByQuery(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_traces_by_query"
        ) as mock_search:
            # Simulate a Tempo API error with detailed message
            mock_search.side_effect = TempoAPIError(
                status_code=400,
                response_text='{"error": "invalid TraceQL query: unexpected token"}',
                url="http://tempo/api/search",
            )

            result = tool._invoke({"q": "{invalid syntax}"})

            assert result.status == ToolResultStatus.ERROR
            assert "invalid TraceQL query: unexpected token" in result.error
            assert "400" in result.error


class TestSearchTracesByTags:
    def test_search_traces_by_tags_success(self, tempo_toolset):
        """Test successful trace search using tags."""
        tool = SearchTracesByTags(tempo_toolset)

        mock_response = {"traces": [{"traceID": "789"}]}

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_traces_by_tags"
        ) as mock_search:
            mock_search.return_value = mock_response

            result = tool._invoke(
                {
                    "tags": 'service.name="api" http.status_code="500"',
                    "min_duration": "100ms",
                    "max_duration": "5s",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            mock_search.assert_called_once_with(
                tags='service.name="api" http.status_code="500"',
                min_duration="100ms",
                max_duration="5s",
                limit=None,
                start=ANY,
                end=ANY,
                spss=None,
            )


class TestQueryTraceById:
    def test_query_trace_by_id_success(self, tempo_toolset):
        """Test successful trace retrieval by ID."""
        tool = QueryTraceById(tempo_toolset)

        mock_trace_data = {
            "batches": [{"resource": {"attributes": []}, "scopeSpans": []}]
        }

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_trace_by_id_v2"
        ) as mock_query:
            mock_query.return_value = mock_trace_data

            result = tool._invoke({"trace_id": "abc123"})

            assert result.status == ToolResultStatus.SUCCESS
            mock_query.assert_called_once_with(
                trace_id="abc123",
                start=ANY,
                end=ANY,
            )

    def test_query_trace_by_id_with_time_range(self, tempo_toolset):
        """Test trace retrieval with time range."""
        tool = QueryTraceById(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_trace_by_id_v2"
        ) as mock_query:
            mock_query.return_value = {"batches": []}

            result = tool._invoke(
                {
                    "trace_id": "abc123",
                    "start": 1234567890,
                    "end": 1234567900,
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            mock_query.assert_called_once_with(
                trace_id="abc123",
                start=1234567890,
                end=1234567900,
            )


class TestSearchTagNames:
    def test_search_tag_names_success(self, tempo_toolset):
        """Test successful tag name discovery."""
        tool = SearchTagNames(tempo_toolset)

        mock_response = {
            "scopes": {
                "resource": ["service.name", "cluster"],
                "span": ["http.status_code", "http.method"],
                "intrinsic": ["duration", "name"],
            }
        }

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_tag_names_v2"
        ) as mock_search:
            mock_search.return_value = mock_response

            result = tool._invoke({})

            assert result.status == ToolResultStatus.SUCCESS
            assert "scopes" in result.data

    def test_search_tag_names_with_filters(self, tempo_toolset):
        """Test tag name discovery with filters."""
        tool = SearchTagNames(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_tag_names_v2"
        ) as mock_search:
            mock_search.return_value = {"scopes": {}}

            result = tool._invoke(
                {
                    "scope": "resource",
                    "q": '{resource.cluster="prod"}',
                    "limit": 50,
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            mock_search.assert_called_once_with(
                scope="resource",
                q='{resource.cluster="prod"}',
                start=ANY,
                end=ANY,
                limit=50,
                max_stale_values=None,
            )


class TestSearchTagValues:
    def test_search_tag_values_success(self, tempo_toolset):
        """Test successful tag value discovery."""
        tool = SearchTagValues(tempo_toolset)

        mock_response = {
            "tagValues": [
                {"type": "string", "value": "api-service"},
                {"type": "string", "value": "web-service"},
            ]
        }

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_tag_values_v2"
        ) as mock_search:
            mock_search.return_value = mock_response

            result = tool._invoke({"tag": "service.name"})

            assert result.status == ToolResultStatus.SUCCESS
            assert "tagValues" in result.data

    def test_search_tag_values_error(self, tempo_toolset):
        """Test error handling in tag value search."""
        tool = SearchTagValues(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_tag_values_v2"
        ) as mock_search:
            mock_search.side_effect = Exception("Tag not found")

            result = tool._invoke({"tag": "invalid.tag"})

            assert result.status == ToolResultStatus.ERROR
            assert "Tag not found" in result.error


class TestQueryMetricsInstant:
    def test_query_metrics_instant_success(self, tempo_toolset):
        """Test successful instant metric query."""
        tool = QueryMetricsInstant(tempo_toolset)

        mock_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [{"metric": {}, "value": [1234567890, "0.95"]}],
            },
        }

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_metrics_instant"
        ) as mock_query:
            mock_query.return_value = mock_response

            result = tool._invoke(
                {
                    "q": "{ } | histogram_quantile(.95)",
                    "since": "1h",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            mock_query.assert_called_once_with(
                q="{ } | histogram_quantile(.95)",
                start=ANY,
                end=ANY,
                since="1h",
            )


class TestQueryMetricsRange:
    def test_query_metrics_range_success(self, tempo_toolset):
        """Test successful range metric query."""
        tool = QueryMetricsRange(tempo_toolset)

        mock_response = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"service.name": "api"},
                        "values": [[1234567890, "10"], [1234567900, "15"]],
                    }
                ],
            },
        }

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_metrics_range"
        ) as mock_query:
            mock_query.return_value = mock_response

            result = tool._invoke(
                {
                    "q": '{ service.name="api" } | rate()',
                    "step": "5m",
                    "since": "3h",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            assert "result" in result.data
            mock_query.assert_called_once_with(
                q='{ service.name="api" } | rate()',
                step="5m",
                start=ANY,
                end=ANY,
                since="3h",
                exemplars=None,
            )

    def test_query_metrics_range_with_exemplars(self, tempo_toolset):
        """Test range metric query with exemplars."""
        tool = QueryMetricsRange(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_metrics_range"
        ) as mock_query:
            mock_query.return_value = {"status": "success", "data": {}}

            result = tool._invoke(
                {
                    "q": "{ } | rate()",
                    "exemplars": 100,
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            mock_query.assert_called_once_with(
                q="{ } | rate()",
                step=None,
                start=ANY,
                end=ANY,
                since=None,
                exemplars=100,
            )


class TestNegativeTimestamps:
    """Test handling of negative timestamps across all tools."""

    def test_search_traces_with_negative_start(self, tempo_toolset):
        """Test search with negative start time (relative to end)."""
        tool = SearchTracesByQuery(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_traces_by_query"
        ) as mock_search:
            mock_search.return_value = {"traces": []}

            # Use negative start (-3600 = 1 hour before end)
            result = tool._invoke(
                {"q": '{resource.service.name="api"}', "start": "-3600"}
            )

            assert result.status == ToolResultStatus.SUCCESS
            # Verify start was converted to a positive timestamp
            args, kwargs = mock_search.call_args
            assert kwargs["start"] > 0
            assert kwargs["end"] > kwargs["start"]
            # Start should be exactly 3600 seconds before end
            assert kwargs["end"] - kwargs["start"] == 3600

    def test_query_trace_with_negative_timestamps(self, tempo_toolset):
        """Test trace query with both negative start and end."""
        tool = QueryTraceById(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_trace_by_id_v2"
        ) as mock_query:
            mock_query.return_value = {"batches": []}

            # Both negative: end relative to now, start relative to end
            result = tool._invoke(
                {
                    "trace_id": "test123",
                    "start": "-7200",  # 2 hours before end
                    "end": "-3600",  # 1 hour before now
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            args, kwargs = mock_query.call_args
            # Both should be positive timestamps
            assert kwargs["start"] > 0
            assert kwargs["end"] > 0
            # Start should be before end
            assert kwargs["start"] < kwargs["end"]
            # Time span should be 7200 seconds (2 hours)
            assert kwargs["end"] - kwargs["start"] == 7200

    def test_metrics_with_inverted_timestamps(self, tempo_toolset):
        """Test that start/end are automatically inverted if start > end."""
        tool = QueryMetricsInstant(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_metrics_instant"
        ) as mock_query:
            mock_query.return_value = {"status": "success", "data": {}}

            # Provide timestamps in wrong order
            now = 1234567890
            result = tool._invoke(
                {
                    "q": "{ } | rate()",
                    "start": now + 3600,  # 1 hour after "end"
                    "end": now,
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            args, kwargs = mock_query.call_args
            # Timestamps should be inverted
            assert kwargs["start"] == now
            assert kwargs["end"] == now + 3600

    def test_tag_search_with_rfc3339_and_negative(self, tempo_toolset):
        """Test mixing RFC3339 and negative timestamps."""
        tool = SearchTagNames(tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.search_tag_names_v2"
        ) as mock_search:
            mock_search.return_value = {"scopes": {}}

            result = tool._invoke(
                {
                    "start": "-3600",  # Negative (relative)
                    "end": "2024-01-01T12:00:00Z",  # RFC3339
                }
            )

            assert result.status == ToolResultStatus.SUCCESS
            args, kwargs = mock_search.call_args
            # Start should be 3600 seconds before the RFC3339 end time
            assert kwargs["start"] > 0
            assert kwargs["end"] > 0
            assert kwargs["end"] - kwargs["start"] == 3600

    def test_all_tools_handle_negative_start(self, tempo_toolset):
        """Test that all tools correctly handle negative start values."""
        test_cases = [
            (SearchTracesByQuery(tempo_toolset), {"q": "{}", "start": "-1800"}),
            (
                SearchTracesByTags(tempo_toolset),
                {"tags": "test=value", "start": "-1800"},
            ),
            (QueryTraceById(tempo_toolset), {"trace_id": "123", "start": "-1800"}),
            (SearchTagNames(tempo_toolset), {"start": "-1800"}),
            (SearchTagValues(tempo_toolset), {"tag": "service.name", "start": "-1800"}),
            (
                QueryMetricsInstant(tempo_toolset),
                {"q": "{ } | rate()", "start": "-1800"},
            ),
            (QueryMetricsRange(tempo_toolset), {"q": "{ } | rate()", "start": "-1800"}),
        ]

        for tool, params in test_cases:
            # Patch the specific API method for each tool
            api_method = tool._invoke.__qualname__.split(".")[0].lower()
            if "fetch" in api_method:
                api_method = "search_traces_by_query"
            elif "searchtracesbyquery" in api_method:
                api_method = "search_traces_by_query"
            elif "searchtracesbytags" in api_method:
                api_method = "search_traces_by_tags"
            elif "querytracebyid" in api_method:
                api_method = "query_trace_by_id_v2"
            elif "searchtagnames" in api_method:
                api_method = "search_tag_names_v2"
            elif "searchtagvalues" in api_method:
                api_method = "search_tag_values_v2"
            elif "querymetricsinstant" in api_method:
                api_method = "query_metrics_instant"
            elif "querymetricsrange" in api_method:
                api_method = "query_metrics_range"

            with patch(
                f"holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.{api_method}"
            ) as mock_method:
                mock_method.return_value = {"status": "success"}

                result = tool._invoke(params)
                assert result.status == ToolResultStatus.SUCCESS

                # Verify the negative start was converted properly
                if mock_method.called:
                    args, kwargs = mock_method.call_args
                    if "start" in kwargs:
                        assert (
                            kwargs["start"] > 0
                        )  # Should be converted to positive timestamp


class TestGrafanaTempoToolset:
    def test_toolset_has_all_tools(self):
        """Test that the toolset includes all new tools."""
        toolset = GrafanaTempoToolset()

        tool_names = [tool.name for tool in toolset.tools]

        expected_tools = [
            "search_traces_by_query",
            "search_traces_by_tags",
            "query_trace_by_id",
            "search_tag_names",
            "search_tag_values",
            "query_metrics_instant",
            "query_metrics_range",
        ]

        for expected in expected_tools:
            assert expected in tool_names

    def test_prerequisites_success(self, tempo_config):
        """Test successful prerequisites check."""
        toolset = GrafanaTempoToolset()

        config_dict = tempo_config.model_dump()

        with patch(
            "holmes.plugins.toolsets.grafana.base_grafana_toolset.grafana_health_check"
        ) as mock_health:
            mock_health.return_value = (True, "Success")

            with patch(
                "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_echo_endpoint"
            ) as mock_echo:
                mock_echo.return_value = True

                success, message = toolset.prerequisites_callable(config_dict)

                assert success is True
                assert "Successfully connected to Tempo" in message

    def test_prerequisites_echo_failure(self, tempo_config):
        """Test prerequisites failure on echo endpoint."""
        toolset = GrafanaTempoToolset()

        config_dict = tempo_config.model_dump()

        with patch(
            "holmes.plugins.toolsets.grafana.base_grafana_toolset.grafana_health_check"
        ) as mock_health:
            mock_health.return_value = (True, "Success")

            with patch(
                "holmes.plugins.toolsets.grafana.grafana_tempo_api.GrafanaTempoAPI.query_echo_endpoint"
            ) as mock_echo:
                mock_echo.return_value = False

                success, message = toolset.prerequisites_callable(config_dict)

                assert success is False
                assert "Failed to connect to Tempo echo endpoint" in message
