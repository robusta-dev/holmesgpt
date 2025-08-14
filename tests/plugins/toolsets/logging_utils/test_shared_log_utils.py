from datetime import datetime, timezone, timedelta
from holmes.plugins.toolsets.logging_utils.shared_log_utils import (
    StructuredLog,
    filter_logs,
    format_relative_time,
    format_logs_with_containers,
    add_log_metadata,
)
from holmes.plugins.toolsets.logging_utils.logging_api import FetchPodLogsParams


class TestFilterLogs:
    """Test the filter_logs function"""

    def test_filter_logs_no_filters(self):
        """Test filtering with no filters applied"""
        logs = [
            StructuredLog(timestamp_ms=1000, content="Log 1", container="app"),
            StructuredLog(timestamp_ms=2000, content="Log 2", container="app"),
        ]
        params = FetchPodLogsParams(namespace="test", pod_name="test-pod")

        (
            filtered,
            count_before_limit,
            substr_fallback,
            exclude_substr_fallback,
            removed_by_include,
            removed_by_exclude,
        ) = filter_logs(logs, params)

        assert len(filtered) == 2
        assert count_before_limit == 2
        assert not substr_fallback
        assert not exclude_substr_fallback
        assert removed_by_include == 0
        assert removed_by_exclude == 0

    def test_filter_logs_regex_include(self):
        """Test filtering with regex include filter"""
        logs = [
            StructuredLog(
                timestamp_ms=1000, content="ERROR: Something failed", container="app"
            ),
            StructuredLog(timestamp_ms=2000, content="INFO: All good", container="app"),
            StructuredLog(
                timestamp_ms=3000, content="WARN: Be careful", container="app"
            ),
        ]
        params = FetchPodLogsParams(
            namespace="test", pod_name="test-pod", filter="ERROR|WARN"
        )

        (
            filtered,
            count_before_limit,
            substr_fallback,
            exclude_substr_fallback,
            removed_by_include,
            removed_by_exclude,
        ) = filter_logs(logs, params)

        assert len(filtered) == 2
        assert filtered[0].content == "ERROR: Something failed"
        assert filtered[1].content == "WARN: Be careful"
        assert not substr_fallback
        assert removed_by_include == 1
        assert removed_by_exclude == 0

    def test_filter_logs_substring_fallback(self):
        """Test filtering falls back to substring when regex is invalid"""
        logs = [
            StructuredLog(
                timestamp_ms=1000, content="ERROR: [unclosed bracket", container="app"
            ),
            StructuredLog(timestamp_ms=2000, content="INFO: All good", container="app"),
        ]
        params = FetchPodLogsParams(
            namespace="test",
            pod_name="test-pod",
            filter="[unclosed",  # Invalid regex
        )

        (
            filtered,
            count_before_limit,
            substr_fallback,
            exclude_substr_fallback,
            removed_by_include,
            removed_by_exclude,
        ) = filter_logs(logs, params)

        assert len(filtered) == 1
        assert filtered[0].content == "ERROR: [unclosed bracket"
        assert substr_fallback  # Should fall back to substring
        assert removed_by_include == 1

    def test_filter_logs_exclude_filter(self):
        """Test filtering with exclude filter"""
        logs = [
            StructuredLog(
                timestamp_ms=1000, content="ERROR: Something failed", container="app"
            ),
            StructuredLog(
                timestamp_ms=2000, content="INFO: Health check", container="app"
            ),
            StructuredLog(
                timestamp_ms=3000, content="INFO: Metrics update", container="app"
            ),
        ]
        params = FetchPodLogsParams(
            namespace="test", pod_name="test-pod", exclude_filter="health|metrics"
        )

        (
            filtered,
            count_before_limit,
            substr_fallback,
            exclude_substr_fallback,
            removed_by_include,
            removed_by_exclude,
        ) = filter_logs(logs, params)

        assert len(filtered) == 1
        assert filtered[0].content == "ERROR: Something failed"
        assert removed_by_exclude == 2

    def test_filter_logs_time_filter(self):
        """Test filtering with time range"""
        # Use epoch milliseconds: Jan 1, 2024 00:00:00 UTC = 1704067200000
        base_time_ms = 1704067200000
        logs = [
            StructuredLog(
                timestamp_ms=base_time_ms + 1000, content="Old log", container="app"
            ),  # +1 second
            StructuredLog(
                timestamp_ms=base_time_ms + 5000,
                content="In range log",
                container="app",
            ),  # +5 seconds
            StructuredLog(
                timestamp_ms=base_time_ms + 10000, content="Future log", container="app"
            ),  # +10 seconds
        ]
        params = FetchPodLogsParams(
            namespace="test",
            pod_name="test-pod",
            start_time="-7",  # 7 seconds before end
            end_time="2024-01-01T00:00:08Z",  # End at 8 seconds from base
        )

        (
            filtered,
            count_before_limit,
            substr_fallback,
            exclude_substr_fallback,
            removed_by_include,
            removed_by_exclude,
        ) = filter_logs(logs, params)

        # Only the log at 5 seconds should be in range (between 1-8 seconds)
        assert len(filtered) == 1
        assert filtered[0].content == "In range log"

    def test_filter_logs_limit(self):
        """Test filtering with limit"""
        logs = [
            StructuredLog(timestamp_ms=i * 1000, content=f"Log {i}", container="app")
            for i in range(10)
        ]
        params = FetchPodLogsParams(namespace="test", pod_name="test-pod", limit=3)

        (
            filtered,
            count_before_limit,
            substr_fallback,
            exclude_substr_fallback,
            removed_by_include,
            removed_by_exclude,
        ) = filter_logs(logs, params)

        assert len(filtered) == 3
        assert count_before_limit == 10
        # Should get the last 3 logs
        assert filtered[0].content == "Log 7"
        assert filtered[1].content == "Log 8"
        assert filtered[2].content == "Log 9"

    def test_filter_logs_combined_filters(self):
        """Test filtering with multiple filters combined"""
        logs = [
            StructuredLog(
                timestamp_ms=1000,
                content="ERROR: Database connection failed",
                container="app",
            ),
            StructuredLog(
                timestamp_ms=2000, content="INFO: Health check passed", container="app"
            ),
            StructuredLog(
                timestamp_ms=3000, content="ERROR: Health check failed", container="app"
            ),
            StructuredLog(
                timestamp_ms=4000, content="WARN: High memory usage", container="app"
            ),
        ]
        params = FetchPodLogsParams(
            namespace="test",
            pod_name="test-pod",
            filter="ERROR|WARN",
            exclude_filter="health",
        )

        (
            filtered,
            count_before_limit,
            substr_fallback,
            exclude_substr_fallback,
            removed_by_include,
            removed_by_exclude,
        ) = filter_logs(logs, params)

        assert len(filtered) == 2
        assert filtered[0].content == "ERROR: Database connection failed"
        assert filtered[1].content == "WARN: High memory usage"
        assert removed_by_include == 1  # INFO log
        assert removed_by_exclude == 1  # ERROR health check


class TestFormatRelativeTime:
    """Test the format_relative_time function"""

    def test_format_relative_time_negative_seconds(self):
        """Test formatting negative seconds (relative timestamps)"""
        current_time = datetime.now(timezone.utc)

        assert format_relative_time("-30", current_time) == "30 seconds before end time"
        assert format_relative_time("-90", current_time) == "1 minute before end time"
        assert format_relative_time("-3600", current_time) == "1 hour before end time"
        assert format_relative_time("-86400", current_time) == "1 day before end time"

    def test_format_relative_time_past(self):
        """Test formatting timestamps in the past"""
        current_time = datetime.now(timezone.utc)
        past_time = current_time - timedelta(hours=2, minutes=30)

        result = format_relative_time(
            past_time.strftime("%Y-%m-%dT%H:%M:%SZ"), current_time
        )
        assert "2 hours 30 minutes ago" == result

    def test_format_relative_time_future(self):
        """Test formatting timestamps in the future"""
        current_time = datetime.now(timezone.utc)
        future_time = current_time + timedelta(
            days=1, minutes=5
        )  # Slightly more than 1 day to ensure it rounds to "1 day"

        result = format_relative_time(
            future_time.strftime("%Y-%m-%dT%H:%M:%SZ"), current_time
        )
        assert "1 day from now" in result

    def test_format_relative_time_just_now(self):
        """Test formatting very recent timestamps"""
        current_time = datetime.now(timezone.utc)
        recent_time = current_time - timedelta(seconds=30)

        result = format_relative_time(
            recent_time.strftime("%Y-%m-%dT%H:%M:%SZ"), current_time
        )
        assert result == "just now"

    def test_format_relative_time_invalid(self):
        """Test formatting invalid timestamps"""
        current_time = datetime.now(timezone.utc)

        # Should return original string if can't parse
        assert (
            format_relative_time("invalid-timestamp", current_time)
            == "invalid-timestamp"
        )


class TestFormatLogsWithContainers:
    """Test the format_logs_with_containers function"""

    def test_format_logs_single_container(self):
        """Test formatting logs when single container (no prefix)"""
        logs = [
            StructuredLog(timestamp_ms=1000, content="Log 1", container="app"),
            StructuredLog(timestamp_ms=2000, content="Log 2", container="app"),
        ]

        result = format_logs_with_containers(logs, display_container_name=False)
        assert result == "Log 1\nLog 2"

    def test_format_logs_multiple_containers(self):
        """Test formatting logs with container names"""
        logs = [
            StructuredLog(timestamp_ms=1000, content="App log", container="app"),
            StructuredLog(
                timestamp_ms=2000, content="Sidecar log", container="sidecar"
            ),
            StructuredLog(
                timestamp_ms=3000, content="No container log", container=None
            ),
        ]

        result = format_logs_with_containers(logs, display_container_name=True)
        expected = "app: App log\nsidecar: Sidecar log\nN/A: No container log"
        assert result == expected


class TestAddLogMetadata:
    """Test the add_log_metadata function"""

    def test_add_metadata_basic(self):
        """Test basic metadata generation"""
        params = FetchPodLogsParams(namespace="test-ns", pod_name="test-pod")
        logs = [StructuredLog(timestamp_ms=1000, content="Log 1", container="app")]

        metadata = add_log_metadata(
            params=params,
            total_count=1,
            filtered_logs=logs,
            filtered_count_before_limit=1,
            used_substring_fallback=False,
            exclude_used_substring_fallback=False,
            removed_by_include_filter=0,
            removed_by_exclude_filter=0,
            has_multiple_containers=False,
            provider_name="Test Provider",
        )

        # Check key metadata elements
        metadata_str = "\n".join(metadata)
        assert "Pod: test-pod" in metadata_str
        assert "Namespace: test-ns" in metadata_str
        assert "Log provider: Test Provider" in metadata_str
        assert "Total logs found before filtering: 1" in metadata_str

    def test_add_metadata_with_filters(self):
        """Test metadata when filters are applied"""
        params = FetchPodLogsParams(
            namespace="test-ns",
            pod_name="test-pod",
            filter="ERROR",
            exclude_filter="health",
        )

        metadata = add_log_metadata(
            params=params,
            total_count=100,
            filtered_logs=[],
            filtered_count_before_limit=20,
            used_substring_fallback=True,
            exclude_used_substring_fallback=False,
            removed_by_include_filter=70,
            removed_by_exclude_filter=10,
            has_multiple_containers=False,
        )

        metadata_str = "\n".join(metadata)
        assert "Filter 'ERROR' is not valid regex" in metadata_str
        assert "Include filter: 'ERROR'" in metadata_str
        assert "Matched: 30 logs (30.0% of total)" in metadata_str
        assert "Exclude filter: 'health'" in metadata_str
        assert "Excluded: 10 logs" in metadata_str

    def test_add_metadata_no_logs_with_filter(self):
        """Test metadata suggestions when no logs match filter"""
        params = FetchPodLogsParams(
            namespace="test-ns", pod_name="test-pod", filter="SPECIFIC_ERROR"
        )

        metadata = add_log_metadata(
            params=params,
            total_count=100,
            filtered_logs=[],
            filtered_count_before_limit=0,
            used_substring_fallback=False,
            exclude_used_substring_fallback=False,
            removed_by_include_filter=100,
            removed_by_exclude_filter=0,
            has_multiple_containers=False,
        )

        metadata_str = "\n".join(metadata)
        assert "No logs matched your filters" in metadata_str
        assert "Try a broader filter pattern" in metadata_str
        assert "Remove the filter to see all 100 available logs" in metadata_str

    def test_add_metadata_hit_limit(self):
        """Test metadata when log limit is hit"""
        params = FetchPodLogsParams(namespace="test-ns", pod_name="test-pod", limit=100)
        logs = [
            StructuredLog(timestamp_ms=i, content=f"Log {i}", container="app")
            for i in range(100)
        ]

        metadata = add_log_metadata(
            params=params,
            total_count=1000,
            filtered_logs=logs,
            filtered_count_before_limit=500,
            used_substring_fallback=False,
            exclude_used_substring_fallback=False,
            removed_by_include_filter=0,
            removed_by_exclude_filter=0,
            has_multiple_containers=False,
        )

        metadata_str = "\n".join(metadata)
        assert "Showing latest 100 of 500 filtered logs (400 omitted)" in metadata_str
        assert "Hit display limit! Suggestions:" in metadata_str
        assert "Add exclude_filter to remove noise" in metadata_str

    def test_add_metadata_with_extra_info(self):
        """Test metadata with provider-specific extra info"""
        params = FetchPodLogsParams(namespace="test-ns", pod_name="test-pod")

        metadata = add_log_metadata(
            params=params,
            total_count=10,
            filtered_logs=[],
            filtered_count_before_limit=10,
            used_substring_fallback=False,
            exclude_used_substring_fallback=False,
            removed_by_include_filter=0,
            removed_by_exclude_filter=0,
            has_multiple_containers=False,
            extra_info="View in Datadog: https://app.datadoghq.com/logs?query=...",
        )

        metadata_str = "\n".join(metadata)
        assert (
            "View in Datadog: https://app.datadoghq.com/logs?query=..." in metadata_str
        )
