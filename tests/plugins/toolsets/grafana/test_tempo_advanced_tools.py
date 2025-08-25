from unittest.mock import patch

import pytest
import yaml

from holmes.core.tools import ToolResultStatus
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import (
    AnalyzeTracesByAttributes,
    CompareTracePeriods,
    FindSlowOperations,
    GrafanaTempoConfig,
    GrafanaTempoToolset,
)


@pytest.fixture
def tempo_toolset():
    """Create a GrafanaTempoToolset with mock config"""
    toolset = GrafanaTempoToolset()
    toolset._grafana_config = GrafanaTempoConfig(
        api_key="test-api-key",
        url="http://grafana:3000",
        grafana_datasource_uid="tempo-uid",
    )
    return toolset


class TestAnalyzeTracesByAttributes:
    def test_analyze_traces_basic(self, tempo_toolset):
        tool = AnalyzeTracesByAttributes(toolset=tempo_toolset)

        # Mock trace data
        mock_traces = [
            {"traceID": "trace1", "duration": 1500},
            {"traceID": "trace2", "duration": 2000},
            {"traceID": "trace3", "duration": 1800},
        ]

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
            return_value=mock_traces,
        ) as mock_query:
            result = tool._invoke(
                {
                    "service_name": "api-service",
                    "group_by_attributes": ["http.method", "http.status_code"],
                    "min_duration": "500ms",
                    "start_datetime": "-1h",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify query was called with correct parameters
            mock_query.assert_called_once()
            call_args = mock_query.call_args
            assert 'resource.service.name="api-service"' in call_args[1]["query"]
            assert "duration>500ms" in call_args[1]["query"]

            # Check that result contains grouped analysis
            result_data = yaml.safe_load(result.data)
            assert isinstance(result_data, dict)

    def test_analyze_without_service_filter(self, tempo_toolset):
        tool = AnalyzeTracesByAttributes(toolset=tempo_toolset)

        mock_traces = []

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
            return_value=mock_traces,
        ) as mock_query:
            result = tool._invoke(
                {
                    "group_by_attributes": ["user.id", "tenant.id"],
                    "min_duration": "1s",
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify service filter was not included
            call_args = mock_query.call_args
            assert "resource.service.name" not in call_args[1]["query"]
            assert "duration>1s" in call_args[1]["query"]

    def test_custom_limit(self, tempo_toolset):
        tool = AnalyzeTracesByAttributes(toolset=tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
            return_value=[],
        ) as mock_query:
            result = tool._invoke(
                {
                    "group_by_attributes": ["endpoint"],
                    "limit": 500,
                }
            )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify custom limit was used
            call_args = mock_query.call_args
            assert call_args[1]["limit"] == 500

    def test_error_handling(self, tempo_toolset):
        tool = AnalyzeTracesByAttributes(toolset=tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
            side_effect=Exception("API error"),
        ):
            result = tool._invoke(
                {
                    "group_by_attributes": ["test"],
                }
            )

            assert result.status == ToolResultStatus.ERROR
            assert "API error" in result.error


class TestFindSlowOperations:
    def test_find_slow_operations(self, tempo_toolset):
        tool = FindSlowOperations(toolset=tempo_toolset)

        mock_traces = [
            {"traceID": "slow1", "duration": 5000},
            {"traceID": "slow2", "duration": 6000},
        ]

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
            return_value=mock_traces,
        ) as mock_query:
            with patch(
                "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.format_traces_list",
                return_value="formatted_traces",
            ) as mock_format:
                result = tool._invoke(
                    {
                        "service_name": "backend",
                        "min_duration": "2s",
                        "start_datetime": "-30m",
                    }
                )

                assert result.status == ToolResultStatus.SUCCESS
                assert result.data == "formatted_traces"

                # Verify query construction
                call_args = mock_query.call_args
                assert "duration>2s" in call_args[1]["query"]
                assert 'resource.service.name="backend"' in call_args[1]["query"]

                # Verify formatting was called
                mock_format.assert_called_once_with(mock_traces)

    def test_find_slow_operations_without_service(self, tempo_toolset):
        tool = FindSlowOperations(toolset=tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
            return_value=[],
        ) as mock_query:
            with patch(
                "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.format_traces_list",
                return_value="formatted_traces",
            ):
                result = tool._invoke(
                    {
                        "min_duration": "500ms",
                    }
                )

                assert result.status == ToolResultStatus.SUCCESS

            # Verify only duration filter was applied
            call_args = mock_query.call_args
            query = call_args[1]["query"]
            assert "duration>500ms" in query
            assert "resource.service.name" not in query

    def test_missing_required_parameter(self, tempo_toolset):
        tool = FindSlowOperations(toolset=tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.get_param_or_raise",
            side_effect=ValueError("min_duration is required"),
        ):
            result = tool._invoke({})

            assert result.status == ToolResultStatus.ERROR
            assert "min_duration is required" in result.error


class TestCompareTracePeriods:
    def test_compare_periods(self, tempo_toolset):
        tool = CompareTracePeriods(toolset=tempo_toolset)

        baseline_traces = [
            {"traceID": "b1", "duration": 1000},
            {"traceID": "b2", "duration": 1200},
        ]

        comparison_traces = [
            {"traceID": "c1", "duration": 1500},
            {"traceID": "c2", "duration": 1600},
            {"traceID": "c3", "duration": 1700},
        ]

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.process_timestamps_to_int",
            side_effect=[(1234567800, 1234567860), (1234567900, 1234567960)],
        ):
            with patch(
                "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
                side_effect=[baseline_traces, comparison_traces],
            ) as mock_query:
                with patch(
                    "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.get_base_url",
                    return_value="http://grafana:3000",
                ):
                    result = tool._invoke(
                        {
                            "service_name": "api",
                            "baseline_start": "-25h",
                            "baseline_end": "-24h",
                            "comparison_start": "-1h",
                            "comparison_end": "now",
                        }
                    )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify two queries were made
            assert mock_query.call_count == 2

            # Check result contains comparison data
            result_data = yaml.safe_load(result.data)
            assert result_data["baseline_count"] == 2
            assert result_data["comparison_count"] == 3
            assert "baseline_period" in result_data
            assert "comparison_period" in result_data

    def test_compare_with_attributes(self, tempo_toolset):
        tool = CompareTracePeriods(toolset=tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.process_timestamps_to_int",
            side_effect=[(1234567800, 1234567860), (1234567900, 1234567960)],
        ):
            with patch(
                "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.get_base_url",
                return_value="http://grafana:3000",
            ):
                with patch(
                    "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
                    return_value=[],
                ) as mock_query:
                    result = tool._invoke(
                        {
                            "service_name": "frontend",
                            "baseline_start": "-48h",
                            "baseline_end": "-47h",
                            "comparison_start": "-2h",
                            "comparison_end": "-1h",
                            "attributes_to_compare": [
                                "http.method",
                                "http.status_code",
                            ],
                        }
                    )

            assert result.status == ToolResultStatus.SUCCESS

            # Verify both queries used same service filter
            calls = mock_query.call_args_list
            for call in calls:
                assert 'resource.service.name="frontend"' in call[1]["query"]

    def test_missing_service_name(self, tempo_toolset):
        tool = CompareTracePeriods(toolset=tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.get_param_or_raise",
            side_effect=ValueError("service_name is required"),
        ):
            result = tool._invoke(
                {
                    "baseline_start": "-2h",
                    "baseline_end": "-1h",
                    "comparison_start": "-1h",
                    "comparison_end": "now",
                }
            )

            assert result.status == ToolResultStatus.ERROR
            assert "service_name is required" in result.error


class TestToolIntegration:
    """Test that tools are properly integrated into the toolset"""

    def test_tools_in_toolset(self):
        toolset = GrafanaTempoToolset()
        tool_names = [tool.name for tool in toolset.tools]

        # Original tools
        assert "fetch_tempo_traces" in tool_names
        assert "fetch_tempo_trace_by_id" in tool_names
        assert "fetch_tempo_tags" in tool_names

        # New advanced tools
        assert "analyze_traces_by_attributes" in tool_names
        assert "find_slow_operations" in tool_names
        assert "compare_trace_periods" in tool_names

    def test_tool_one_liners(self, tempo_toolset):
        # Test that each tool generates appropriate one-liner descriptions
        tools = [
            AnalyzeTracesByAttributes(toolset=tempo_toolset),
            FindSlowOperations(toolset=tempo_toolset),
            CompareTracePeriods(toolset=tempo_toolset),
        ]

        for tool in tools:
            one_liner = tool.get_parameterized_one_liner({})
            assert "Grafana" in one_liner or "grafana" in one_liner


class TestTimeProcessing:
    """Test time processing utilities"""

    def test_process_timestamps(self, tempo_toolset):
        tool = FindSlowOperations(toolset=tempo_toolset)

        with patch(
            "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.process_timestamps_to_int",
            return_value=(1234567890, 1234567900),
        ) as mock_process:
            with patch(
                "holmes.plugins.toolsets.grafana.toolset_grafana_tempo.query_tempo_traces",
                return_value=[],
            ):
                tool._invoke(
                    {
                        "min_duration": "1s",
                        "start_datetime": "-1h",
                        "end_datetime": "now",
                    }
                )

                # Verify time processing was called
                mock_process.assert_called_once()
                call_args = mock_process.call_args
                assert call_args[0][0] == "-1h"
                assert call_args[0][1] == "now"
