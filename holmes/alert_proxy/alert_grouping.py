"""Alert grouping logic for identifying related alerts."""

import logging
from typing import List

from holmes.alert_proxy.models import EnrichedAlert

logger = logging.getLogger(__name__)


class AlertGrouper:
    """Groups related alerts based on various criteria."""

    @staticmethod
    def group_related_alerts(alerts: List[EnrichedAlert]) -> None:
        """
        Identify and mark related alerts.

        Updates the related_alerts field in enrichments to link alerts that are related.

        Args:
            alerts: List of enriched alerts to analyze for relationships
        """
        for i, alert1 in enumerate(alerts):
            for alert2 in alerts[i + 1 :]:
                if AlertGrouper._are_related(alert1, alert2):
                    # Add fingerprints to related_alerts (if enrichment exists)
                    if alert1.enrichment and alert2.original.fingerprint:
                        alert1.enrichment.related_alerts.append(
                            alert2.original.fingerprint
                        )
                    if alert2.enrichment and alert1.original.fingerprint:
                        alert2.enrichment.related_alerts.append(
                            alert1.original.fingerprint
                        )

    @staticmethod
    def _are_related(alert1: EnrichedAlert, alert2: EnrichedAlert) -> bool:
        """
        Check if two alerts are related based on various criteria.

        Args:
            alert1: First alert to compare
            alert2: Second alert to compare

        Returns:
            True if alerts are related, False otherwise
        """
        # Same namespace indicates relationship
        if alert1.original.labels.get("namespace") == alert2.original.labels.get(
            "namespace"
        ):
            return True

        # Similar affected services
        if alert1.enrichment and alert2.enrichment:
            services1 = set(alert1.enrichment.affected_services)
            services2 = set(alert2.enrichment.affected_services)
            if services1 and services2 and services1.intersection(services2):
                return True

        # Time proximity (within 5 minutes)
        time_diff = abs(
            (alert1.original.startsAt - alert2.original.startsAt).total_seconds()
        )
        if time_diff < 300:
            return True

        return False
