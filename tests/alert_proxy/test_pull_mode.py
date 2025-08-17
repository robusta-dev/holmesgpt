"""Tests for pull mode functionality."""

import pytest
from unittest.mock import patch
from datetime import datetime

from holmes.config import Config
from holmes.alert_proxy.models import ProxyConfig, ProxyMode, Alert, AlertStatus
from holmes.alert_proxy.discovery import AlertManagerDiscovery
from holmes.alert_proxy.poller import AlertManagerPoller


def test_proxy_mode_enum():
    """Test ProxyMode enum values."""
    assert ProxyMode.WEBHOOK.value == "webhook"
    assert ProxyMode.PULL.value == "pull"
    assert ProxyMode.AUTO.value == "auto"


def test_proxy_config_with_pull_mode():
    """Test ProxyConfig with pull mode settings."""
    config = ProxyConfig(
        mode=ProxyMode.PULL,
        poll_interval=60,
        auto_discover=True,
        alertmanager_url="http://alertmanager:9093",
    )

    assert config.mode == ProxyMode.PULL
    assert config.poll_interval == 60
    assert config.auto_discover is True
    assert config.alertmanager_url == "http://alertmanager:9093"


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
    assert not discovery._is_alertmanager_workload("prometheus")
    assert not discovery._is_alertmanager_workload("grafana")


@pytest.mark.asyncio
async def test_alertmanager_discovery_via_env():
    """Test discovery via environment variables."""
    with patch.dict("os.environ", {"ALERTMANAGER_URL": "http://test-am:9093"}):
        discovery = AlertManagerDiscovery()
        found = discovery.discover_via_env()

        assert len(found) == 1
        assert found[0]["url"] == "http://test-am:9093"
        assert found[0]["source"] == "environment"


def test_poller_fingerprint_generation():
    """Test alert fingerprint generation."""
    config = Config(model="gpt-4o-mini", api_key="test")
    proxy_config = ProxyConfig(mode=ProxyMode.PULL)

    poller = AlertManagerPoller(config, proxy_config)

    alert_data = {
        "labels": {
            "alertname": "TestAlert",
            "severity": "warning",
            "namespace": "default",
        }
    }

    fingerprint1 = poller.generate_fingerprint(alert_data)
    fingerprint2 = poller.generate_fingerprint(alert_data)

    # Same data should generate same fingerprint
    assert fingerprint1 == fingerprint2

    # Different data should generate different fingerprint
    alert_data["labels"]["severity"] = "critical"
    fingerprint3 = poller.generate_fingerprint(alert_data)
    assert fingerprint1 != fingerprint3


def test_poller_filter_new_alerts():
    """Test filtering of new alerts."""
    config = Config(model="gpt-4o-mini", api_key="test")
    proxy_config = ProxyConfig(
        mode=ProxyMode.PULL,
        enrich_only_firing=True,
    )

    poller = AlertManagerPoller(config, proxy_config)

    # Create test alerts
    alert1 = Alert(
        status=AlertStatus.FIRING,
        labels={"alertname": "Test1"},
        annotations={},
        startsAt=datetime.utcnow(),
        fingerprint="alert1",
    )

    alert2 = Alert(
        status=AlertStatus.RESOLVED,
        labels={"alertname": "Test2"},
        annotations={},
        startsAt=datetime.utcnow(),
        fingerprint="alert2",
    )

    alert3 = Alert(
        status=AlertStatus.FIRING,
        labels={"alertname": "Test3"},
        annotations={},
        startsAt=datetime.utcnow(),
        fingerprint="alert3",
    )

    alertmanager_url = "http://test-am:9093"

    # First call - all firing alerts are new
    new_alerts = poller.filter_new_alerts(alertmanager_url, [alert1, alert2, alert3])
    assert len(new_alerts) == 2  # Only firing alerts (alert1, alert3)
    assert alert1 in new_alerts
    assert alert3 in new_alerts
    assert alert2 not in new_alerts  # Resolved, filtered out

    # Mark alerts as seen
    poller.mark_alerts_seen(alertmanager_url, new_alerts)

    # Second call - no new alerts
    new_alerts = poller.filter_new_alerts(alertmanager_url, [alert1, alert3])
    assert len(new_alerts) == 0  # Already seen

    # Add a new alert
    alert4 = Alert(
        status=AlertStatus.FIRING,
        labels={"alertname": "Test4"},
        annotations={},
        startsAt=datetime.utcnow(),
        fingerprint="alert4",
    )

    new_alerts = poller.filter_new_alerts(alertmanager_url, [alert1, alert3, alert4])
    assert len(new_alerts) == 1  # Only alert4 is new
    assert alert4 in new_alerts


@pytest.mark.asyncio
async def test_poller_create_webhook_payload():
    """Test creation of webhook payload from alerts."""
    config = Config(model="gpt-4o-mini", api_key="test")
    proxy_config = ProxyConfig(mode=ProxyMode.PULL)

    poller = AlertManagerPoller(config, proxy_config)

    alerts = [
        Alert(
            status=AlertStatus.FIRING,
            labels={
                "namespace": "default",
                "severity": "warning",
                "alertname": "Test1",
            },
            annotations={"summary": "Test alert 1"},
            startsAt=datetime.utcnow(),
        ),
        Alert(
            status=AlertStatus.FIRING,
            labels={
                "namespace": "default",
                "severity": "critical",
                "alertname": "Test2",
            },
            annotations={"summary": "Test alert 2"},
            startsAt=datetime.utcnow(),
        ),
    ]

    alertmanager = {
        "name": "test-am",
        "namespace": "monitoring",
        "url": "http://test-am:9093",
    }

    webhook = poller.create_webhook_payload(alerts, alertmanager)

    assert webhook.receiver == "pull-mode"
    assert webhook.status == AlertStatus.FIRING
    assert len(webhook.alerts) == 2
    assert webhook.commonLabels["namespace"] == "default"  # Common to both alerts
    assert "severity" not in webhook.commonLabels  # Different values, not common
    assert webhook.externalURL == "http://test-am:9093"


@pytest.mark.asyncio
async def test_poller_stats():
    """Test poller statistics tracking."""
    config = Config(model="gpt-4o-mini", api_key="test")
    proxy_config = ProxyConfig(mode=ProxyMode.PULL)

    poller = AlertManagerPoller(config, proxy_config)

    # Initial stats
    stats = poller.get_stats()
    assert stats["polls"] == 0
    assert stats["alerts_found"] == 0
    assert stats["alerts_enriched"] == 0
    assert stats["errors"] == 0
    assert stats["alertmanagers"] == 0

    # Add some alertmanagers
    poller.alertmanager_instances = [
        {"name": "am1", "url": "http://am1:9093"},
        {"name": "am2", "url": "http://am2:9093"},
    ]

    stats = poller.get_stats()
    assert stats["alertmanagers"] == 2
    assert "am1" in stats["alertmanager_names"]
    assert "am2" in stats["alertmanager_names"]
