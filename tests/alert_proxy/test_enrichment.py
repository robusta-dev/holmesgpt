"""Tests for alert enrichment logic."""

from datetime import datetime
from unittest.mock import patch
import pytest

from holmes.config import Config
from holmes.alert_proxy.enrichment import AlertCache, AlertEnricher
from holmes.alert_proxy.models import (
    Alert,
    AlertStatus,
    AIEnrichment,
    ProxyConfig,
)


def test_alert_cache():
    """Test alert caching functionality."""
    cache = AlertCache(ttl=300)

    alert = Alert(
        status=AlertStatus.FIRING,
        labels={"alertname": "Test", "severity": "warning"},
        annotations={"description": "Test alert"},
        startsAt=datetime.utcnow(),
    )

    enrichment = AIEnrichment(
        summary="Test summary",
        priority_score=5.0,
    )

    # Test cache miss
    assert cache.get(alert) is None

    # Test cache set and hit
    cache.set(alert, enrichment)
    cached = cache.get(alert)
    assert cached is not None
    assert cached.summary == "Test summary"

    # Test cache key generation is consistent
    key1 = cache.get_key(alert)
    key2 = cache.get_key(alert)
    assert key1 == key2

    # Test different alerts have different keys
    alert2 = Alert(
        status=AlertStatus.FIRING,
        labels={"alertname": "Different", "severity": "critical"},
        annotations={"description": "Different alert"},
        startsAt=datetime.utcnow(),
    )
    key3 = cache.get_key(alert2)
    assert key1 != key3


@pytest.mark.asyncio
async def test_alert_enricher_should_enrich():
    """Test the should_enrich logic."""
    config = Config(model="gpt-4o-mini", api_key="test-key")
    proxy_config = ProxyConfig(
        enable_enrichment=True,
        enrich_only_firing=True,
        severity_filter=["critical", "warning"],
    )

    with patch("holmes.alert_proxy.enrichment.LLM"):
        enricher = AlertEnricher(config, proxy_config)

        # Should enrich: firing + warning
        alert1 = Alert(
            status=AlertStatus.FIRING,
            labels={"severity": "warning"},
            annotations={},
            startsAt=datetime.utcnow(),
        )
        assert enricher._should_enrich(alert1) is True

        # Should not enrich: resolved
        alert2 = Alert(
            status=AlertStatus.RESOLVED,
            labels={"severity": "warning"},
            annotations={},
            startsAt=datetime.utcnow(),
        )
        assert enricher._should_enrich(alert2) is False

        # Should not enrich: info severity
        alert3 = Alert(
            status=AlertStatus.FIRING,
            labels={"severity": "info"},
            annotations={},
            startsAt=datetime.utcnow(),
        )
        assert enricher._should_enrich(alert3) is False

        # Should enrich: critical
        alert4 = Alert(
            status=AlertStatus.FIRING,
            labels={"severity": "critical"},
            annotations={},
            startsAt=datetime.utcnow(),
        )
        assert enricher._should_enrich(alert4) is True


@pytest.mark.asyncio
async def test_default_enrichment():
    """Test default enrichment when LLM is not used."""
    config = Config(model="gpt-4o-mini", api_key="test-key")
    proxy_config = ProxyConfig(enable_enrichment=False)

    with patch("holmes.alert_proxy.enrichment.LLM"):
        enricher = AlertEnricher(config, proxy_config)

        alert = Alert(
            status=AlertStatus.FIRING,
            labels={"alertname": "TestAlert"},
            annotations={"description": "Test description"},
            startsAt=datetime.utcnow(),
        )

        enriched = await enricher.enrich_alert(alert)

        assert enriched.original == alert
        assert enriched.enrichment.summary == "Test description"
        assert enriched.enrichment.enrichment_metadata.get("enriched") is False


@pytest.mark.asyncio
async def test_parse_llm_response():
    """Test parsing of LLM responses."""
    config = Config(model="gpt-4o-mini", api_key="test-key")
    proxy_config = ProxyConfig()

    with patch("holmes.alert_proxy.enrichment.LLM"):
        enricher = AlertEnricher(config, proxy_config)

        alert = Alert(
            status=AlertStatus.FIRING,
            labels={},
            annotations={},
            startsAt=datetime.utcnow(),
        )

        # Test valid JSON response
        response = """
        {
            "summary": "Database is down",
            "business_impact": "All services affected",
            "priority_score": 9.5,
            "affected_services": ["api", "web"]
        }
        """

        enrichment = enricher._parse_llm_response(response, alert)
        assert enrichment.summary == "Database is down"
        assert enrichment.business_impact == "All services affected"
        assert enrichment.priority_score == 9.5
        assert "api" in enrichment.affected_services

        # Test response with extra text
        response2 = """
        Here's the analysis:
        {
            "summary": "CPU spike detected",
            "priority_score": 7.0
        }
        Additional notes...
        """

        enrichment2 = enricher._parse_llm_response(response2, alert)
        assert enrichment2.summary == "CPU spike detected"
        assert enrichment2.priority_score == 7.0

        # Test invalid response
        response3 = "This is not JSON"
        enrichment3 = enricher._parse_llm_response(response3, alert)
        assert enrichment3.summary == "Alert triggered"  # Fallback
        assert "error" in enrichment3.enrichment_metadata


@pytest.mark.asyncio
async def test_group_related_alerts():
    """Test alert grouping logic."""
    config = Config(model="gpt-4o-mini", api_key="test-key")
    proxy_config = ProxyConfig(enable_grouping=True)

    with patch("holmes.alert_proxy.enrichment.LLM"):
        enricher = AlertEnricher(config, proxy_config)

        # Create alerts in same namespace
        alert1 = Alert(
            status=AlertStatus.FIRING,
            labels={"namespace": "production"},
            annotations={},
            startsAt=datetime.utcnow(),
            fingerprint="alert1",
        )

        alert2 = Alert(
            status=AlertStatus.FIRING,
            labels={"namespace": "production"},
            annotations={},
            startsAt=datetime.utcnow(),
            fingerprint="alert2",
        )

        # Create alert3 with a different timestamp to avoid time-based grouping
        from datetime import timedelta

        alert3 = Alert(
            status=AlertStatus.FIRING,
            labels={"namespace": "staging"},
            annotations={},
            startsAt=datetime.utcnow() - timedelta(minutes=10),
            fingerprint="alert3",
        )

        from holmes.alert_proxy.models import EnrichedAlert

        enriched1 = EnrichedAlert(
            original=alert1,
            enrichment=AIEnrichment(summary="Alert 1", affected_services=["api"]),
        )
        enriched2 = EnrichedAlert(
            original=alert2,
            enrichment=AIEnrichment(summary="Alert 2", affected_services=["api"]),
        )
        enriched3 = EnrichedAlert(
            original=alert3,
            enrichment=AIEnrichment(summary="Alert 3", affected_services=["web"]),
        )

        alerts = [enriched1, enriched2, enriched3]
        enricher._group_related_alerts(alerts)

        # Alert 1 and 2 should be related (same namespace and service)
        assert "alert2" in enriched1.enrichment.related_alerts
        assert "alert1" in enriched2.enrichment.related_alerts

        # Alert 3 should not be related to others
        assert len(enriched3.enrichment.related_alerts) == 0
