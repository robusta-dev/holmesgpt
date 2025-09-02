import pytest
from holmes.plugins.toolsets.prometheus.prometheus import (
    filter_metrics_by_name,
    filter_metrics_by_type,
    adjust_step_for_max_points,
)


@pytest.mark.parametrize(
    "metrics, expected_type, expected_result",
    [
        (
            {
                "metric1": {"type": "counter"},
                "metric2": {"type": "gauge"},
                "metric3": {"type": "counter"},
            },
            "counter",
            {"metric1": {"type": "counter"}, "metric3": {"type": "counter"}},
        ),
        # Test case 2: Empty result when type doesn't exist
        (
            {"metric1": {"type": "counter"}, "metric2": {"type": "gauge"}},
            "histogram",
            {},
        ),
        # Test case 3: Empty input dictionary
        ({}, "counter", {}),
        # Test case 4: Metrics with missing type field
        (
            {
                "metric1": {"type": "counter"},
                "metric2": {},
                "metric3": {"type": "counter"},
            },
            "counter",
            {"metric1": {"type": "counter"}, "metric3": {"type": "counter"}},
        ),
        # Test case 4: Metrics with missing type field
        (
            {
                "metric1": {"type": "counter"},
                "metric2": {"type": "?"},
            },
            "counter",
            {"metric1": {"type": "counter"}, "metric2": {"type": "?"}},
        ),
    ],
)
def test_filter_metrics_by_type(metrics, expected_type, expected_result):
    print(f"metrics={metrics}")
    print(f"expected_type={expected_type}")
    print(f"expected_result={expected_result}")
    result = filter_metrics_by_type(metrics, expected_type)
    assert result == expected_result


@pytest.mark.parametrize(
    "metrics, pattern, expected",
    [
        (
            {
                "node_memory_Active_bytes": {"type": "gauge"},
                "node_cpu_seconds_total": {"type": "counter"},
                "process_start_time": {"type": "gauge"},
            },
            "node_.*",  # Pattern to match metrics starting with "node_"
            {
                "node_memory_Active_bytes": {"type": "gauge"},
                "node_cpu_seconds_total": {"type": "counter"},
            },
        ),
        (
            {
                "node_memory_Active_bytes": {"type": "gauge"},
                "node_memory_Cached_bytes": {"type": "gauge"},
                "process_cpu_seconds": {"type": "counter"},
            },
            "memory",
            {
                "node_memory_Active_bytes": {"type": "gauge"},
                "node_memory_Cached_bytes": {"type": "gauge"},
            },
        ),
        (
            {
                "node_memory_Active_bytes": {"type": "gauge"},
                "node_memory_Cached_bytes": {"type": "gauge"},
                "process_cpu_seconds": {"type": "counter"},
            },
            ".*memory.*",  # Pattern to match metrics containing "memory"
            {
                "node_memory_Active_bytes": {"type": "gauge"},
                "node_memory_Cached_bytes": {"type": "gauge"},
            },
        ),
        (
            {
                "node_memory_Active_bytes": {"type": "gauge"},
                "process_cpu_seconds": {"type": "counter"},
            },
            "nonexistent.*",  # Pattern that matches nothing
            {},
        ),
        (
            {},
            ".*",  # Pattern that matches everything, but empty input
            {},
        ),
    ],
)
def test_filter_metrics_by_name(metrics, pattern, expected):
    result = filter_metrics_by_name(metrics, pattern)
    assert result == expected


@pytest.mark.parametrize(
    "start_timestamp, end_timestamp, step, max_points_value, expected_step",
    [
        # Test case 1: Points within limit, no adjustment needed
        (
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",  # 1 hour = 3600 seconds
            60,  # 60 second step = 60 points (within 300 limit)
            300,
            60,  # No adjustment needed
        ),
        # Test case 2: Points exceed limit, adjustment needed
        (
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",  # 1 hour = 3600 seconds
            10,  # 10 second step = 360 points (exceeds 300 limit)
            300,
            12.0,  # Adjusted to 3600/300 = 12 seconds
        ),
        # Test case 3: Exactly at limit
        (
            "2024-01-01T00:00:00Z",
            "2024-01-01T05:00:00Z",  # 5 hours = 18000 seconds
            60,  # 60 second step = 300 points (exactly at limit)
            300,
            60,  # No adjustment needed
        ),
        # Test case 4: Large time range requiring significant adjustment
        (
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z",  # 24 hours = 86400 seconds
            60,  # 60 second step = 1440 points (way over 300 limit)
            300,
            288.0,  # Adjusted to 86400/300 = 288 seconds
        ),
        # Test case 5: Custom max_points limit
        (
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:30:00Z",  # 30 minutes = 1800 seconds
            10,  # 10 second step = 180 points
            100,  # Lower max_points limit
            18.0,  # Adjusted to 1800/100 = 18 seconds
        ),
    ],
)
def test_adjust_step_for_max_points(
    monkeypatch, start_timestamp, end_timestamp, step, max_points_value, expected_step
):
    # Mock the MAX_GRAPH_POINTS constant directly in the prometheus module
    import holmes.plugins.toolsets.prometheus.prometheus as prom_module

    monkeypatch.setattr(prom_module, "MAX_GRAPH_POINTS", max_points_value)

    result = adjust_step_for_max_points(start_timestamp, end_timestamp, step)
    assert result == expected_step
