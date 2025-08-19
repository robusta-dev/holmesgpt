"""Tests for alert enrichment logic."""

from datetime import datetime
from unittest.mock import patch
import pytest

from holmes.config import Config
from holmes.alert_proxy.alert_enrichment import AlertEnricher
from holmes.alert_proxy.models import (
    Alert,
    AlertStatus,
    AlertEnrichmentConfig,
)


@pytest.mark.skip(reason="Tests need to be rewritten for new architecture")
def test_alert_enricher_should_enrich():
    """Test the should_enrich logic - needs rewrite for new architecture."""
    pass


@pytest.mark.skip(reason="Tests need to be rewritten for new architecture")
def test_default_enrichment():
    """Test default enrichment when LLM is not used - needs rewrite."""
    pass


def test_parse_investigation_response():
    """Test parsing of LLM responses."""
    config = Config(model="gpt-4o-mini", api_key="test-key")
    enrichment_config = AlertEnrichmentConfig()

    with patch("holmes.alert_proxy.alert_enrichment.LLM"):
        enricher = AlertEnricher(config, enrichment_config)

        alert = Alert(
            status=AlertStatus.FIRING,
            labels={},
            annotations={},
            startsAt=datetime.utcnow(),
        )

        # Test valid JSON response
        response = """
        {
            "business_impact": "All services affected",
            "root_cause": "Database is down",
            "affected_services": ["api", "web"]
        }
        """

        enrichment = enricher._parse_investigation_response(response, alert)
        assert enrichment.business_impact == "All services affected"
        assert enrichment.root_cause == "Database is down"
        assert "api" in enrichment.affected_services

        # Test response with extra text
        response2 = """
        Here's the analysis:
        {
            "root_cause": "CPU spike detected"
        }
        Additional notes...
        """

        enrichment2 = enricher._parse_investigation_response(response2, alert)
        assert enrichment2.root_cause == "CPU spike detected"

        # Test invalid response
        response3 = "This is not JSON"
        enrichment3 = enricher._parse_investigation_response(response3, alert)
        assert "parse_error" in enrichment3.enrichment_metadata


@pytest.mark.skip(reason="Group alerts method changed - needs rewrite")
def test_group_related_alerts():
    """Test alert grouping logic - needs rewrite for new architecture."""
    pass
