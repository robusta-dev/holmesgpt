"""Tests for alert proxy models."""

from datetime import datetime
from holmes.alert_proxy.models import (
    Alert,
    AlertStatus,
    AlertmanagerWebhook,
    AIEnrichment,
    EnrichedAlert,
    ProxyConfig,
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
        summary="Database connection pool exhausted",
        business_impact="Checkout service degraded for 500 users",
        root_cause="Memory leak in connection handler",
        suggested_action="Restart database pod",
        priority_score=8.5,
        affected_services=["checkout", "payment"],
    )

    assert enrichment.priority_score == 8.5
    assert "checkout" in enrichment.affected_services
    assert enrichment.business_impact is not None


def test_enriched_alert_to_slack_blocks():
    """Test conversion of enriched alert to Slack blocks."""
    alert = Alert(
        status=AlertStatus.FIRING,
        labels={"alertname": "HighMemory", "severity": "critical"},
        annotations={"description": "Memory usage above 90%"},
        startsAt=datetime.utcnow(),
    )

    enrichment = AIEnrichment(
        summary="Memory leak detected in API service",
        business_impact="API response times degraded by 2s",
        root_cause="Unclosed database connections",
        suggested_action="Restart API pods",
        priority_score=9.0,
        affected_services=["api", "database"],
    )

    enriched = EnrichedAlert(original=alert, enrichment=enrichment)
    blocks = enriched.to_slack_blocks()

    # Check structure
    assert len(blocks) > 0
    assert blocks[0]["type"] == "header"
    assert "🔴" in blocks[0]["text"]["text"]  # Critical severity emoji

    # Check summary section
    summary_block = next(
        b
        for b in blocks
        if b["type"] == "section" and "Summary" in b.get("text", {}).get("text", "")
    )
    assert "Memory leak detected" in summary_block["text"]["text"]

    # Check fields section exists
    fields_block = next(
        (b for b in blocks if b["type"] == "section" and "fields" in b), None
    )
    assert fields_block is not None
    assert len(fields_block["fields"]) > 0

    # Check context section
    context_block = next((b for b in blocks if b["type"] == "context"), None)
    assert context_block is not None


def test_proxy_config():
    """Test ProxyConfig model with defaults."""
    config = ProxyConfig()

    assert config.port == 8080
    assert config.host == "0.0.0.0"
    assert config.model == "gpt-4o-mini"
    assert config.enable_enrichment is True
    assert config.enable_caching is True
    assert config.cache_ttl == 300
    assert config.severity_filter == ["critical", "warning"]

    # Test with custom values
    config2 = ProxyConfig(
        port=9090,
        model="gpt-4",
        slack_webhook_url="https://hooks.slack.com/test",
        severity_filter=["critical"],
    )

    assert config2.port == 9090
    assert config2.model == "gpt-4"
    assert config2.slack_webhook_url == "https://hooks.slack.com/test"
    assert config2.severity_filter == ["critical"]
