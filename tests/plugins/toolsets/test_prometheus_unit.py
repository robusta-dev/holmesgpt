import pytest
from holmes.plugins.toolsets.prometheus.prometheus import (
    filter_metrics_by_name,
    filter_metrics_by_type,
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
