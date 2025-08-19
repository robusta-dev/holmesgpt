"""Tests for alert proxy models."""

from datetime import datetime
from holmes.alert_proxy.models import (
    Alert,
    AlertStatus,
    AlertmanagerWebhook,
    AIEnrichment,
    AlertEnrichmentConfig,
    InteractiveModeConfig,
    WebhookModeConfig,
)


def test_alert_model():
    """Test Alert model creation and validation."""
    alert = Alert(
        status=AlertStatus.FIRING,
        labels={"alertname": "HighCPU", "severity": "warning"},
        annotations={"description": "CPU usage is high"},
        startsAt=datetime.utcnow(),
    )

    assert alert.status == AlertStatus.FIRING
    assert alert.labels["alertname"] == "HighCPU"
    assert alert.annotations["description"] == "CPU usage is high"


def test_alertmanager_webhook():
    """Test AlertmanagerWebhook model."""
    webhook = AlertmanagerWebhook(
        receiver="default",
        status=AlertStatus.FIRING,
        alerts=[
            Alert(
                status=AlertStatus.FIRING,
                labels={"alertname": "Test"},
                annotations={},
                startsAt=datetime.utcnow(),
            )
        ],
        groupLabels={},
        commonLabels={"severity": "warning"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
    )

    assert webhook.receiver == "default"
    assert len(webhook.alerts) == 1
    assert webhook.commonLabels["severity"] == "warning"


def test_ai_enrichment():
    """Test AIEnrichment model."""
    enrichment = AIEnrichment(
        business_impact="Checkout service degraded for 500 users",
        root_cause="Memory leak in connection handler",
        suggested_action="Restart database pod",
        affected_services=["checkout", "payment"],
    )

    assert "checkout" in enrichment.affected_services
    assert enrichment.business_impact is not None


def test_enrichment_config():
    """Test AlertEnrichmentConfig model with defaults."""
    config = AlertEnrichmentConfig()

    assert config.model == "gpt-4o-mini"
    assert config.enable_enrichment is True
    assert config.enable_caching is True
    assert config.cache_ttl == 300
    assert config.severity_filter == ["critical", "warning"]

    # Test with custom values
    config2 = AlertEnrichmentConfig(
        model="gpt-4",
        severity_filter=["critical"],
        enable_enrichment=False,
    )

    assert config2.model == "gpt-4"
    assert config2.enable_enrichment is False
    assert config2.severity_filter == ["critical"]


def test_interactive_mode_config():
    """Test InteractiveModeConfig model."""
    config = InteractiveModeConfig()

    assert config.poll_interval == 30
    assert config.auto_discover is True
    assert config.enrichment.model == "gpt-4o-mini"


def test_webhook_mode_config():
    """Test WebhookModeConfig model."""
    config = WebhookModeConfig(
        port=9090,
        slack_webhook_url="https://hooks.slack.com/test",
    )

    assert config.port == 9090
    assert config.host == "0.0.0.0"
    assert config.slack_webhook_url == "https://hooks.slack.com/test"
    assert config.enrichment.model == "gpt-4o-mini"
