"""Unified alert management: storage, tracking, and polling."""

import logging
from typing import Dict, List, Optional, Set
from holmes.alert_proxy.models import (
    Alert,
    AlertManagerInstance,
    InteractiveModeConfig,
    EnrichedAlert,
    EnrichmentStatus,
)
from holmes.alert_proxy.alert_fetcher import AlertFetcher
from holmes.alert_proxy.discovery import AlertManagerDiscovery

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alerts: fetching, storing, and tracking what's new.

    This combines the responsibilities of AlertManagerPoller and AlertRepository
    into a single cohesive component that:
    - Discovers AlertManager instances
    - Polls them for alerts using AlertFetcher
    - Stores alerts and tracks what's been seen
    - Provides deduplication for pull mode
    - Maintains display order for UI
    """

    def __init__(
        self,
        alert_config: InteractiveModeConfig,
        fetcher: Optional[AlertFetcher] = None,
    ):
        """Initialize the alert manager.

        Args:
            alert_config: Alert processing configuration
            fetcher: Optional AlertFetcher instance (will create if not provided)
        """
        self.alert_config = alert_config
        self.fetcher = fetcher
        self.discovery = AlertManagerDiscovery()
        self.alertmanager_instances: List[AlertManagerInstance] = []

        # Storage: alerts by fingerprint
        self._alerts: Dict[str, EnrichedAlert] = {}
        self._display_order: List[str] = []  # Ordered list of fingerprints

        # Tracking: what each source has seen (for deduplication)
        self._seen_by_source: Dict[str, Set[str]] = {}

    # ========== Discovery Methods ==========

    def discover_alertmanagers(self) -> List[AlertManagerInstance]:
        """Discover AlertManager instances.

        Returns:
            List of discovered AlertManager instances
        """
        logger.info("Discovering AlertManager instances...")

        if self.alert_config.auto_discover:
            discovered = self.discovery.discover_all()
        elif self.alert_config.alertmanager_url:
            # Use manually configured URL
            discovered = [
                AlertManagerInstance(
                    name="configured",
                    namespace="unknown",
                    url=self.alert_config.alertmanager_url,
                    source="config",
                    use_proxy=False,
                )
            ]
        else:
            logger.warning("No AlertManager configured and auto-discovery disabled")
            discovered = []

        self.alertmanager_instances = discovered
        logger.info(f"Found {len(discovered)} AlertManager instance(s)")
        return discovered

    # ========== Polling Methods ==========

    def poll_alertmanager(
        self, alertmanager: AlertManagerInstance, deduplicate: bool = True
    ) -> List[Alert]:
        """Poll a single AlertManager instance for alerts.

        Args:
            alertmanager: AlertManager instance to poll
            deduplicate: If True, only return new alerts not seen before

        Returns:
            List of alerts (new only if deduplicate=True, all if False)
        """
        if not self.fetcher:
            raise RuntimeError("AlertFetcher not initialized")

        name = alertmanager.name
        source_key = self._get_source_key(alertmanager)

        try:
            # Fetch alerts using the stateless fetcher
            alerts = self.fetcher.fetch_alerts(alertmanager)

            if not alerts:
                logger.debug(f"No alerts from {name}")
                # Mark source as empty
                self._seen_by_source[source_key] = set()
                self._cleanup_stale_alerts()
                return []

            logger.info(f"Found {len(alerts)} alerts from {name}")

            if deduplicate:
                # Filter for new alerts only
                new_alerts = self._get_new_alerts(alerts, source_key)
                if new_alerts:
                    logger.info(f"Found {len(new_alerts)} new alerts from {name}")
                    # Mark as seen
                    self._mark_alerts_seen(new_alerts, source_key)
                return new_alerts
            else:
                # Return all alerts (for interactive mode)
                return alerts

        except Exception as e:
            logger.error(f"Error polling {name}: {e}")
            return []

    def poll_all(self, deduplicate: bool = True) -> List[Alert]:
        """Poll all discovered AlertManager instances.

        Args:
            deduplicate: If True, only return new alerts

        Returns:
            Combined list of alerts from all instances
        """
        if not self.alertmanager_instances:
            self.discover_alertmanagers()

        all_alerts = []
        for am in self.alertmanager_instances:
            alerts = self.poll_alertmanager(am, deduplicate)
            all_alerts.extend(alerts)

        return all_alerts

    # ========== Storage Methods ==========

    def update_alerts(
        self, alerts: List[Alert], source_key: Optional[str] = None
    ) -> List[str]:
        """Update stored alerts from a source.

        Args:
            alerts: List of Alert objects
            source_key: Optional source identifier for tracking

        Returns:
            List of fingerprints for newly added alerts
        """
        if not source_key:
            source_key = "default"

        if not alerts:
            # Source has no alerts - mark it as empty
            self._seen_by_source[source_key] = set()
            self._cleanup_stale_alerts()
            return []

        current_fingerprints = set()
        new_fingerprints = []

        for alert in alerts:
            if not alert.fingerprint:
                logger.warning(f"Alert missing fingerprint: {alert.labels}")
                continue

            fingerprint = alert.fingerprint
            current_fingerprints.add(fingerprint)

            if fingerprint in self._alerts:
                # Update existing alert but preserve enrichment
                self._alerts[fingerprint].original = alert
            else:
                # New alert
                enriched = EnrichedAlert(
                    original=alert,
                    enrichment=None,
                    enrichment_status=EnrichmentStatus.READY,
                )
                self._alerts[fingerprint] = enriched
                self._display_order.append(fingerprint)
                new_fingerprints.append(fingerprint)

        # Track what this source currently has
        self._seen_by_source[source_key] = current_fingerprints

        # Remove alerts no longer present from ANY source
        self._cleanup_stale_alerts()

        return new_fingerprints

    def get_all_alerts(self) -> List[EnrichedAlert]:
        """Get all stored alerts in display order.

        Returns:
            List of EnrichedAlert objects
        """
        return [self._alerts[fp] for fp in self._display_order if fp in self._alerts]

    def get_alert(self, fingerprint: str) -> Optional[EnrichedAlert]:
        """Get a specific alert by fingerprint.

        Args:
            fingerprint: Alert fingerprint

        Returns:
            EnrichedAlert or None if not found
        """
        return self._alerts.get(fingerprint)

    def get_alert_at_position(self, position: int) -> Optional[EnrichedAlert]:
        """Get alert at a specific position in display order.

        Args:
            position: Position in the ordered list

        Returns:
            EnrichedAlert or None if invalid position
        """
        if 0 <= position < len(self._display_order):
            fingerprint = self._display_order[position]
            return self._alerts.get(fingerprint)
        return None

    def count(self) -> int:
        """Get the total number of stored alerts."""
        return len(self._alerts)

    # ========== Private Methods ==========

    def _get_source_key(self, alertmanager: AlertManagerInstance) -> str:
        """Get a unique key for an AlertManager source."""
        return alertmanager.url or f"{alertmanager.namespace}/{alertmanager.name}"

    def _get_new_alerts(self, alerts: List[Alert], source_key: str) -> List[Alert]:
        """Filter alerts to only include ones not seen from this source.

        Args:
            alerts: List of alerts to filter
            source_key: Source identifier

        Returns:
            List of new alerts
        """
        if source_key not in self._seen_by_source:
            self._seen_by_source[source_key] = set()

        seen = self._seen_by_source[source_key]
        return [a for a in alerts if a.fingerprint and a.fingerprint not in seen]

    def _mark_alerts_seen(self, alerts: List[Alert], source_key: str):
        """Mark alerts as seen from a source.

        Args:
            alerts: Alerts to mark as seen
            source_key: Source identifier
        """
        if source_key not in self._seen_by_source:
            self._seen_by_source[source_key] = set()

        for alert in alerts:
            if alert.fingerprint:
                self._seen_by_source[source_key].add(alert.fingerprint)

        # Limit memory usage per source
        if len(self._seen_by_source[source_key]) > 1000:
            # Keep the most recent 900
            fingerprints = list(self._seen_by_source[source_key])
            self._seen_by_source[source_key] = set(fingerprints[-900:])

    def _cleanup_stale_alerts(self):
        """Remove alerts that are no longer present from any source."""
        # Collect all fingerprints still present from any source
        all_current = set()
        for fingerprints in self._seen_by_source.values():
            all_current.update(fingerprints)

        # Remove alerts not in any source
        stale = []
        for fingerprint in self._alerts.keys():
            if fingerprint not in all_current:
                stale.append(fingerprint)

        for fingerprint in stale:
            del self._alerts[fingerprint]
            if fingerprint in self._display_order:
                self._display_order.remove(fingerprint)
