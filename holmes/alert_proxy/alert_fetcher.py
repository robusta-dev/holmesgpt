"""Centralized alert fetching logic for AlertManager."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin  # type: ignore

import requests  # type:ignore
from holmes.alert_proxy.models import (
    Alert,
    AlertStatus,
    AlertManagerInstance,
)
from holmes.alert_proxy.kube_proxy import KubeProxy

logger = logging.getLogger(__name__)


class AlertFetcher:
    """
    Centralized fetcher for AlertManager alerts.
    """

    def __init__(
        self,
        max_alerts: Optional[int] = None,
        enrich_only_firing: bool = True,
        kube_proxy: Optional[KubeProxy] = None,
        session: Optional[requests.Session] = None,
    ):
        """Initialize the alert fetcher.

        Args:
            max_alerts: Maximum number of alerts to fetch per poll
            enrich_only_firing: Only return firing alerts (filter out resolved)
            kube_proxy: Optional Kubernetes proxy for accessing services
            session: Optional requests session for HTTP requests
        """
        self.max_alerts = max_alerts
        self.enrich_only_firing = enrich_only_firing
        self.kube_proxy = kube_proxy or KubeProxy()
        self.session = session or requests.Session()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.session:
            self.session.close()

    def fetch_alerts(self, alertmanager: AlertManagerInstance) -> List[Alert]:
        """Fetch alerts from an AlertManager instance.

        Args:
            alertmanager: AlertManager instance to fetch from

        Returns:
            List of Alert objects
        """
        logger.info(
            f"Attempting to fetch from {alertmanager.name} (namespace={alertmanager.namespace}, use_proxy={alertmanager.use_proxy}, url={alertmanager.url})"
        )
        try:
            # Use proxy if available and configured
            if alertmanager.use_proxy and self.kube_proxy and self.kube_proxy.available:
                logger.info(f"Using Kubernetes API proxy for {alertmanager.name}")
                data = self.kube_proxy.get_alertmanager_alerts(
                    alertmanager.name,
                    alertmanager.namespace,
                    alertmanager.port,
                    subpath=getattr(
                        alertmanager, "subpath", ""
                    ),  # Pass subpath if available
                )
                # Check for empty dict or None
                if not data or data == {}:
                    logger.debug(
                        f"No alerts fetched from {alertmanager.name} via proxy"
                    )
                    return []
            else:
                # Direct URL access - v2 API only
                if not alertmanager.url:
                    logger.error(
                        f"No URL configured for AlertManager {alertmanager.name}"
                    )
                    return []

                # Log why we're not using proxy
                if alertmanager.use_proxy:
                    if not self.kube_proxy:
                        logger.warning(
                            f"Proxy requested but KubeProxy not initialized for {alertmanager.name}"
                        )
                    elif not self.kube_proxy.available:
                        logger.warning(
                            f"Proxy requested but not available for {alertmanager.name}"
                        )
                else:
                    logger.info(f"Direct connection (no proxy) for {alertmanager.name}")

                # Use urljoin to properly handle subpaths (e.g., /alertmanager for Mimir)
                # Ensure base URL ends with / for proper path joining
                base_url = alertmanager.url
                if not base_url.endswith("/"):
                    base_url += "/"
                url = urljoin(base_url, "api/v2/alerts")

                logger.info(f"Making direct HTTP request to: {url}")

                if not self.session:
                    logger.error("No session available for AlertManager fetch")
                    return []
                response = self.session.get(url, timeout=10)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch alerts: {response.status_code}")
                    return []
                data = response.json()

            alerts = []

            # v2 API returns a list directly
            alerts_list = data if isinstance(data, list) else []
            logger.debug(f"Got {len(alerts_list)} alerts from {alertmanager.name}")

            # Apply max_alerts limit if specified
            if self.max_alerts and len(alerts_list) > self.max_alerts:
                logger.info(
                    f"Limiting alerts from {len(alerts_list)} to {self.max_alerts}"
                )
                alerts_list = alerts_list[: self.max_alerts]

            for alert_data in alerts_list:
                # Convert to our Alert model
                labels = alert_data.get("labels", {}).copy()

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
                            "startsAt", datetime.now(timezone.utc).isoformat()
                        ).replace("Z", "+00:00")
                    ),
                    endsAt=datetime.fromisoformat(
                        alert_data.get(
                            "endsAt", datetime.now(timezone.utc).isoformat()
                        ).replace("Z", "+00:00")
                    )
                    if alert_data.get("endsAt")
                    else None,
                    generatorURL=alert_data.get("generatorURL"),
                    fingerprint=alert_data.get("fingerprint"),
                )

                # Skip alerts without fingerprints (shouldn't happen with AlertManager v2)
                if not alert.fingerprint:
                    logger.warning(f"Alert missing fingerprint: {labels}")
                    continue

                # Apply filtering based on configuration
                if self.enrich_only_firing and alert.status != AlertStatus.FIRING:
                    continue

                alerts.append(alert)

            logger.debug(
                f"Successfully processed {len(alerts)} alerts from {alertmanager.name}"
            )
            return alerts

        except requests.Timeout:
            logger.error(f"Timeout fetching alerts from {alertmanager.name}")
            if not alertmanager.use_proxy:
                logger.info(f"  Timeout on direct connection to: {alertmanager.url}")
                logger.info(
                    "  This might indicate the service is not accessible from outside the cluster"
                )
                logger.info(
                    "  Consider using kubectl proxy or port-forward to access the service"
                )
            return []
        except requests.ConnectionError as e:
            logger.error(
                f"Connection error fetching alerts from {alertmanager.name}: {e}"
            )
            if not alertmanager.use_proxy and ".svc.cluster.local" in (
                alertmanager.url or ""
            ):
                logger.error(
                    "  ERROR: Trying to connect to cluster-internal URL from outside the cluster"
                )
                logger.error(f"  URL: {alertmanager.url}")
                logger.error(
                    "  This URL is only accessible from within the Kubernetes cluster"
                )
                logger.error("  Solutions:")
                logger.error("    1. Run Holmes inside the cluster")
                logger.error("    2. Use kubectl port-forward to access the service")
                logger.error(
                    "    3. Configure AlertManager auto-discovery (it will use kube proxy)"
                )
            return []
        except Exception as e:
            error_msg = f"Error fetching alerts from {alertmanager.name}: {e}"

            # Add helpful message if this is from environment variable
            if alertmanager.name == "ALERTMANAGER_URL-env-var":
                error_msg += f"\n  Note: This AlertManager URL ({alertmanager.url}) comes from the ALERTMANAGER_URL environment variable."
                error_msg += "\n  To fix: Either unset ALERTMANAGER_URL or set it to a valid AlertManager URL"

            logger.error(error_msg)
            import traceback

            logger.debug(f"Traceback: {traceback.format_exc()}")
            return []

    def fetch_from_all(self, alertmanagers: List[AlertManagerInstance]) -> List[Alert]:
        """Fetch alerts from all AlertManager instances.

        Args:
            alertmanagers: List of AlertManager instances

        Returns:
            Combined list of alerts from all instances
        """
        all_alerts = []

        # Fetch from all AlertManagers sequentially
        for am in alertmanagers:
            try:
                logger.info(
                    f"Fetching alerts from {am.name} ({am.namespace or 'default'})..."
                )
                result = self.fetch_alerts(am)
                if result:
                    logger.info(f"Fetched {len(result)} alerts from {am.name}")
                    all_alerts.extend(result)
            except Exception as e:
                logger.error(f"Failed to fetch from {am.name}: {e}")

        return all_alerts
