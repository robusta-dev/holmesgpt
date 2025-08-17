"""Pull-based alert polling for AlertManager."""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

import aiohttp
import requests
from holmes.config import Config
from holmes.alert_proxy.discovery import AlertManagerDiscovery
from holmes.alert_proxy.kube_proxy import KubeProxy
from holmes.alert_proxy.enrichment import AlertEnricher
from holmes.alert_proxy.models import (
    Alert,
    AlertmanagerWebhook,
    AlertStatus,
    ProxyConfig,
)
from holmes.alert_proxy.destinations import DestinationManager

logger = logging.getLogger(__name__)


class AlertManagerPoller:
    """Polls AlertManager instances for alerts and enriches them."""

    def __init__(
        self,
        config: Config,
        proxy_config: ProxyConfig,
        enricher=None,
        destinations=None,
    ):
        self.config = config
        self.proxy_config = proxy_config
        # Use provided enricher or create new one if enrichment is enabled
        self.enricher = (
            enricher
            if enricher
            else (
                AlertEnricher(config, proxy_config)
                if proxy_config.enable_enrichment
                else None
            )
        )
        # Use provided destinations or create new one
        self.destinations = (
            destinations if destinations else DestinationManager(config, proxy_config)
        )
        self.discovery = AlertManagerDiscovery()
        self.kube_proxy = KubeProxy()

        # Track seen alerts to avoid duplicates
        self.seen_alerts: Dict[
            str, Set[str]
        ] = {}  # alertmanager_url -> set of fingerprints
        self.alertmanager_instances: List[Dict[str, str]] = []
        self.session: Optional[aiohttp.ClientSession] = None

        self._stats = {
            "polls": 0,
            "alerts_found": 0,
            "alerts_enriched": 0,
            "errors": 0,
        }

    async def start(self):
        """Start the polling loop."""
        logger.info("Starting AlertManager poller in pull mode")

        # Create aiohttp session
        self.session = aiohttp.ClientSession()

        try:
            # Discover AlertManager instances
            if self.proxy_config.auto_discover:
                await self.discover_alertmanagers()
            elif self.proxy_config.alertmanager_url:
                # Use manually configured URL
                self.alertmanager_instances = [
                    {
                        "name": "configured",
                        "namespace": "unknown",
                        "url": self.proxy_config.alertmanager_url,
                        "source": "config",
                        "use_proxy": False,
                    }
                ]
            else:
                logger.error(
                    "No AlertManager URL configured and auto-discovery is disabled"
                )
                return

            if not self.alertmanager_instances:
                logger.warning("No AlertManager instances found")
                return

            logger.info(
                f"Polling {len(self.alertmanager_instances)} AlertManager instance(s)"
            )

            # Start polling loop
            await self.poll_loop()

        finally:
            await self.cleanup()

    async def discover_alertmanagers(self):
        """Discover AlertManager instances."""
        logger.info("Discovering AlertManager instances...")

        discovered = await self.discovery.discover_all()

        # Verify each discovered instance
        verified = []
        for am in discovered:
            # Check if we can access via proxy
            if am.get("use_proxy") and self.kube_proxy and self.kube_proxy.available:
                if await self.kube_proxy.verify_alertmanager(
                    am["name"], am["namespace"], am.get("port", 9093)
                ):
                    verified.append(am)
                    logger.info(
                        f"✓ Verified AlertManager: {am['name']} in {am['namespace']} (via API proxy)"
                    )
                else:
                    logger.debug(f"✗ Could not verify: {am['name']} via proxy")
            elif "url" in am:
                # Direct URL access (for configured or in-cluster)
                try:
                    response = requests.get(f"{am['url']}/api/v2/status", timeout=5)
                    if response.status_code == 200:
                        verified.append(am)
                        logger.info(
                            f"✓ Verified AlertManager: {am['name']} at {am['url']}"
                        )
                except Exception:
                    logger.debug(f"✗ Could not verify: {am.get('url')}")

        self.alertmanager_instances = verified

        if not verified and discovered:
            logger.warning(
                f"Found {len(discovered)} AlertManager instances but none were accessible"
            )
            # Use discovered anyway in case verification failed
            self.alertmanager_instances = discovered

    async def poll_loop(self):
        """Main polling loop."""
        poll_interval = self.proxy_config.poll_interval

        while True:
            try:
                # Poll all AlertManager instances
                for am in self.alertmanager_instances:
                    await self.poll_alertmanager(am)

                self._stats["polls"] += 1

                # Log stats periodically
                if self._stats["polls"] % 10 == 0:
                    logger.info(f"Poll stats: {self._stats}")

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                self._stats["errors"] += 1

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    async def poll_alertmanager(self, alertmanager: Dict[str, str]):
        """Poll a single AlertManager instance."""
        name = alertmanager["name"]

        try:
            # Get alerts from AlertManager API
            alerts = await self.fetch_alerts(alertmanager)

            if not alerts:
                logger.debug(f"No alerts from {name}")
                return

            logger.info(f"Found {len(alerts)} alerts from {name}")
            self._stats["alerts_found"] += len(alerts)

            # Filter for new alerts
            am_key = alertmanager.get(
                "url", f"{alertmanager['namespace']}/{alertmanager['name']}"
            )
            new_alerts = self.filter_new_alerts(am_key, alerts)

            if not new_alerts:
                logger.debug(f"No new alerts from {name}")
                return

            logger.info(f"Processing {len(new_alerts)} new alerts from {name}")

            # Create webhook payload for compatibility
            webhook = self.create_webhook_payload(new_alerts, alertmanager)

            # Enrich alerts
            if self.enricher:
                enriched_alerts = await self.enricher.enrich_webhook(webhook)
            else:
                from holmes.alert_proxy.models import EnrichedAlert

                enriched_alerts = [
                    EnrichedAlert(original=alert, enrichment=None)
                    for alert in webhook.alerts
                ]
            self._stats["alerts_enriched"] += len(enriched_alerts)

            # Forward to destinations
            await self.destinations.forward_alerts(enriched_alerts, webhook)

            # Mark alerts as seen
            am_key = alertmanager.get(
                "url", f"{alertmanager['namespace']}/{alertmanager['name']}"
            )
            self.mark_alerts_seen(am_key, new_alerts)

        except Exception as e:
            logger.error(f"Error polling {name}: {e}")
            self._stats["errors"] += 1

    async def fetch_alerts(self, alertmanager: Dict[str, str]) -> List[Alert]:
        """Fetch alerts from AlertManager API."""
        try:
            # Use proxy if available and configured
            if (
                alertmanager.get("use_proxy")
                and self.kube_proxy
                and self.kube_proxy.available
            ):
                port = alertmanager.get("port", 9093)
                data = await self.kube_proxy.get_alertmanager_alerts(
                    alertmanager["name"],
                    alertmanager["namespace"],
                    int(port) if isinstance(port, str) else port,
                )
                if not data:
                    return []
            else:
                # Direct URL access - v2 API only
                url = f"{alertmanager['url']}/api/v2/alerts"
                if not self.session:
                    logger.error("No session available for AlertManager fetch")
                    return []
                async with self.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch alerts: {response.status}")
                        return []
                    data = await response.json()

            alerts = []

            # v2 API returns a list directly
            alerts_list = data if isinstance(data, list) else []

            # Apply max_alerts limit if specified
            if (
                self.proxy_config.max_alerts
                and len(alerts_list) > self.proxy_config.max_alerts
            ):
                logger.info(
                    f"Limiting alerts from {len(alerts_list)} to {self.proxy_config.max_alerts}"
                )
                alerts_list = alerts_list[: self.proxy_config.max_alerts]

            for alert_data in alerts_list:
                # Convert to our Alert model
                labels = alert_data.get("labels", {}).copy()

                # Apply custom columns if specified
                for custom_col in self.proxy_config.custom_columns:
                    if "=" in custom_col:
                        key, value = custom_col.split("=", 1)
                        labels[key] = value

                # v2 API status format
                state = alert_data.get("status", {}).get("state", "active")

                alert = Alert(
                    status=AlertStatus.FIRING
                    if state in ["active", "firing"]
                    else AlertStatus.RESOLVED,
                    labels=labels,
                    annotations=alert_data.get("annotations", {}),
                    startsAt=datetime.fromisoformat(
                        alert_data.get(
                            "startsAt", datetime.utcnow().isoformat()
                        ).replace("Z", "+00:00")
                    ),
                    endsAt=datetime.fromisoformat(
                        alert_data.get("endsAt", datetime.utcnow().isoformat()).replace(
                            "Z", "+00:00"
                        )
                    )
                    if alert_data.get("endsAt")
                    else None,
                    generatorURL=alert_data.get("generatorURL"),
                    fingerprint=alert_data.get(
                        "fingerprint", self.generate_fingerprint(alert_data)
                    ),
                )
                alerts.append(alert)

            return alerts

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching alerts from {alertmanager['name']}")
            return []
        except Exception as e:
            logger.error(f"Error fetching alerts from {alertmanager['name']}: {e}")
            return []

    def filter_new_alerts(
        self, alertmanager_key: str, alerts: List[Alert]
    ) -> List[Alert]:
        """Filter alerts to only include new ones we haven't seen."""
        if alertmanager_key not in self.seen_alerts:
            self.seen_alerts[alertmanager_key] = set()

        seen = self.seen_alerts[alertmanager_key]
        new_alerts = []

        for alert in alerts:
            # Only process firing alerts (unless configured otherwise)
            if (
                self.proxy_config.enrich_only_firing
                and alert.status != AlertStatus.FIRING
            ):
                continue

            # Check if we've seen this alert
            fingerprint = alert.fingerprint or self.generate_fingerprint_from_alert(
                alert
            )
            if fingerprint not in seen:
                new_alerts.append(alert)

        return new_alerts

    def mark_alerts_seen(self, alertmanager_url: str, alerts: List[Alert]):
        """Mark alerts as seen to avoid reprocessing."""
        if alertmanager_url not in self.seen_alerts:
            self.seen_alerts[alertmanager_url] = set()

        for alert in alerts:
            fingerprint = alert.fingerprint or self.generate_fingerprint_from_alert(
                alert
            )
            self.seen_alerts[alertmanager_url].add(fingerprint)

        # Clean up old fingerprints (keep last 1000)
        if len(self.seen_alerts[alertmanager_url]) > 1000:
            # Keep the most recent 900 to avoid thrashing
            fingerprints = list(self.seen_alerts[alertmanager_url])
            self.seen_alerts[alertmanager_url] = set(fingerprints[-900:])

    def create_webhook_payload(
        self, alerts: List[Alert], alertmanager: Dict[str, str]
    ) -> AlertmanagerWebhook:
        """Create a webhook payload from alerts for compatibility."""
        # Group alerts by common labels
        common_labels = {}
        if alerts:
            # Find common labels across all alerts
            common_labels = alerts[0].labels.copy()
            for alert in alerts[1:]:
                common_labels = {
                    k: v for k, v in common_labels.items() if alert.labels.get(k) == v
                }

        webhook = AlertmanagerWebhook(
            receiver="pull-mode",
            status=AlertStatus.FIRING
            if any(a.status == AlertStatus.FIRING for a in alerts)
            else AlertStatus.RESOLVED,
            alerts=alerts,
            groupLabels=common_labels,
            commonLabels=common_labels,
            commonAnnotations={},
            externalURL=alertmanager.get(
                "url",
                f"http://{alertmanager['name']}.{alertmanager['namespace']}.svc.cluster.local",
            ),
            version="4",
            groupKey=f"pull:{alertmanager['name']}",
        )

        return webhook

    def generate_fingerprint(self, alert_data: dict) -> str:
        """Generate a fingerprint for an alert."""
        # Create a unique identifier based on labels
        labels = alert_data.get("labels", {})
        key_parts = []
        for k in sorted(labels.keys()):
            key_parts.append(f"{k}={labels[k]}")
        key = ":".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()

    def generate_fingerprint_from_alert(self, alert: Alert) -> str:
        """Generate a fingerprint from an Alert object."""
        key_parts = []
        for k in sorted(alert.labels.keys()):
            key_parts.append(f"{k}={alert.labels[k]}")
        key = ":".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()

    async def cleanup(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()
        if self.destinations.session:
            await self.destinations.close()

    def get_stats(self) -> dict:
        """Get polling statistics."""
        return {
            **self._stats,
            "alertmanagers": len(self.alertmanager_instances),
            "alertmanager_names": [am["name"] for am in self.alertmanager_instances],
        }
