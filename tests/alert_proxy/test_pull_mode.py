"""Tests for pull mode functionality."""

import pytest

from holmes.alert_proxy.discovery import AlertManagerDiscovery


@pytest.mark.skip(reason="Tests need update for new architecture")
def test_proxy_config_with_pull_mode():
    """Test config with pull mode settings - needs update."""
    pass


@pytest.mark.asyncio
async def test_alertmanager_discovery_patterns():
    """Test AlertManager discovery patterns."""
    discovery = AlertManagerDiscovery()

    # Test pattern matching
    assert discovery._is_alertmanager_workload("alertmanager")
    assert discovery._is_alertmanager_workload("prometheus-alertmanager")
    assert discovery._is_alertmanager_workload("kube-prometheus-st-alertmanager")
    assert discovery._is_alertmanager_workload(
        "robusta-kube-prometheus-st-alertmanager"
    )

    # Test non-matching patterns
    assert not discovery._is_alertmanager_workload("prometheus-server")
    assert not discovery._is_alertmanager_workload("grafana")
    assert not discovery._is_alertmanager_workload("nginx")
