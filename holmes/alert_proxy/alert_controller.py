"""Alert UI Controller - handles data and business logic for alert viewing."""

import logging
import threading
import time
from typing import Optional, List, Set
import queue

from holmes.config import Config
from holmes.alert_proxy.models import (
    InteractiveModeConfig,
    EnrichedAlert,
    AlertmanagerWebhook,
    EnrichmentStatus,
)
from holmes.alert_proxy.alert_enrichment import AlertEnricher
from holmes.alert_proxy.interactive_view import AlertUIView, LogInterceptor
from holmes.alert_proxy.alert_manager import AlertManager
from holmes.alert_proxy.alert_fetcher import AlertFetcher

# Use default logging instead of named logger for better console capture
# logger = logging.getLogger(__name__)


class AlertUIController:
    """Controller for the alert UI - manages data and business logic."""

    def __init__(
        self,
        config: Config,
        alert_config: InteractiveModeConfig,
        enricher: Optional[AlertEnricher] = None,
    ):
        """Initialize alert controller.

        Args:
            config: Application configuration
            alert_config: Interactive mode configuration
            enricher: Optional enricher for AI analysis
        """
        self.config = config
        self.alert_config = alert_config
        self.enricher = enricher
        self.view = None

        # Alert manager handles storage and polling
        self.alert_manager: Optional[AlertManager] = None

        # Enrichment management
        self.enrichment_queue: queue.Queue[Optional[EnrichedAlert]] = queue.Queue()
        self.enrichment_thread = None
        self.enriching_fingerprints: Set[str] = set()  # Track what's being enriched
        self.stop_enrichment = threading.Event()
        self.stop_polling = threading.Event()
        self.polling_thread = None

    def start_enrichment_worker(self):
        """Start the background enrichment worker thread."""
        if self.enrichment_thread and self.enrichment_thread.is_alive():
            return

        def worker():
            """Worker thread that processes enrichment requests."""
            while not self.stop_enrichment.is_set():
                try:
                    # Get next alert to enrich (with timeout to check stop flag)
                    alert = self.enrichment_queue.get(timeout=0.5)
                    if alert is None:  # Poison pill
                        break

                    # Run enrichment synchronously
                    self._enrich_single_alert(alert)
                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f"Enrichment worker error: {e}")
                    if self.view:
                        self.view.add_console_line(f"❌ Enrichment error: {str(e)}")

        self.enrichment_thread = threading.Thread(
            target=worker, daemon=True, name="EnrichmentWorker"
        )
        self.enrichment_thread.start()

    def stop_enrichment_worker(self):
        """Stop the enrichment worker thread."""
        if self.enrichment_thread:
            self.stop_enrichment.set()
            self.enrichment_queue.put(None)  # Poison pill
            self.enrichment_thread.join(timeout=2)

    def _enrich_single_alert(self, alert: EnrichedAlert):
        """Enrich a single alert."""
        fingerprint = alert.original.fingerprint
        alert_name = alert.original.labels.get("alertname", "Unknown")

        logging.info(
            f"[ENRICH] Starting enrichment for alert: {alert_name} (fingerprint: {fingerprint})"
        )

        try:
            # Update status
            alert.enrichment_status = EnrichmentStatus.IN_PROGRESS
            logging.info(f"[ENRICH] Set status to IN_PROGRESS for {alert_name}")

            if self.view:
                self.view.add_console_line(f"🔮 Starting enrichment: {alert_name}")
                logging.info(f"[ENRICH] Requesting UI refresh for {alert_name} start")
                self.view.request_refresh()

            # Create webhook for enrichment
            webhook = AlertmanagerWebhook(
                receiver="interactive-ui",
                status=alert.original.status,
                alerts=[alert.original],
                groupLabels=alert.original.labels,
                commonLabels=alert.original.labels,
                commonAnnotations=alert.original.annotations,
                externalURL="http://localhost",
                version="4",
                groupKey=f"alert:{fingerprint}",
            )

            # Run enrichment (now synchronous)
            if not self.enricher:
                logging.error("[ENRICH] Enricher not initialized")
                alert.enrichment_status = EnrichmentStatus.FAILED
                return

            logging.info(f"[ENRICH] Calling enricher.enrich_webhook for {alert_name}")
            enriched_alerts = self.enricher.enrich_webhook(webhook)
            logging.info(
                f"[ENRICH] Enricher returned {len(enriched_alerts) if enriched_alerts else 0} enriched alerts"
            )

            if enriched_alerts and enriched_alerts[0].enrichment:
                enrichment = enriched_alerts[0].enrichment

                # Check if enrichment actually has content (not just metadata)
                has_content = (
                    enrichment.business_impact
                    or enrichment.root_cause
                    or enrichment.root_cause_analysis
                    or enrichment.suggested_action
                    or enrichment.affected_services
                    or enrichment.custom_columns
                )

                # Check for error in metadata
                has_error = (
                    enrichment.enrichment_metadata.get("error")
                    or enrichment.enrichment_metadata.get("enriched") is False
                )

                if has_content and not has_error:
                    # Update the alert with enrichment
                    alert.enrichment = enrichment
                    alert.enriched_at = enriched_alerts[0].enriched_at
                    alert.enrichment_status = EnrichmentStatus.COMPLETED

                    logging.info(f"[ENRICH] Successfully enriched {alert_name}")
                    logging.info(
                        f"[ENRICH] Enrichment data keys: {list(alert.enrichment.model_dump().keys()) if alert.enrichment else 'None'}"
                    )
                    # Log actual content presence
                    if alert.enrichment:
                        logging.info(
                            f"[ENRICH] Content check - business_impact: {bool(alert.enrichment.business_impact)}, "
                            f"root_cause: {bool(alert.enrichment.root_cause)}, "
                            f"suggested_action: {bool(alert.enrichment.suggested_action)}"
                        )

                    if self.view:
                        self.view.add_console_line(
                            f"✅ Enrichment complete: {alert_name}"
                        )
                else:
                    # Enrichment failed or returned empty
                    alert.enrichment_status = EnrichmentStatus.FAILED
                    error_msg = enrichment.enrichment_metadata.get(
                        "error", "No content generated"
                    )

                    logging.warning(
                        f"[ENRICH] Enrichment failed for {alert_name}: {error_msg}"
                    )
                    logging.info(
                        f"[ENRICH] Failed enrichment metadata: {enrichment.enrichment_metadata}"
                    )

                    if self.view:
                        self.view.add_console_line(
                            f"⚠️ Enrichment failed for {alert_name}: {error_msg}"
                        )
            else:
                alert.enrichment_status = EnrichmentStatus.FAILED
                logging.warning(f"[ENRICH] No enrichment returned for {alert_name}")
                if self.view:
                    self.view.add_console_line(
                        f"⚠️ No enrichment generated for: {alert_name}"
                    )

        except Exception as e:
            logging.error(f"[ENRICH] Failed to enrich {alert_name}: {e}", exc_info=True)
            alert.enrichment_status = EnrichmentStatus.FAILED
            if self.view:
                self.view.add_console_line(
                    f"❌ Enrichment failed for {alert_name}: {str(e)}"
                )
        finally:
            # Remove from enriching set
            if fingerprint:
                self.enriching_fingerprints.discard(fingerprint)
                logging.info(f"[ENRICH] Removed {fingerprint} from enriching set")

            # Update view
            logging.info(
                f"[ENRICH] Requesting final UI refresh for {alert_name} (status: {alert.enrichment_status})"
            )
            if self.view:
                self.view.request_refresh()

    def enrich_alerts(self, alert_fingerprints: List[str]):
        """Queue alerts for enrichment.

        Args:
            alert_fingerprints: List of alert fingerprints to enrich
        """
        logging.info(
            f"[ENRICH] enrich_alerts called with {len(alert_fingerprints)} fingerprints"
        )
        enriched_count = 0
        if not self.alert_manager:
            logging.error("[ENRICH] Alert manager not initialized")
            return
        for fingerprint in alert_fingerprints:
            alert = self.alert_manager.get_alert(fingerprint)
            if not alert:
                logging.warning(
                    f"[ENRICH] Alert not found for fingerprint: {fingerprint}"
                )
                continue

            # Skip if already enriched or enriching
            if alert.enrichment_status == EnrichmentStatus.COMPLETED:
                logging.info(f"[ENRICH] Skipping already enriched alert: {fingerprint}")
                continue
            if fingerprint in self.enriching_fingerprints:
                logging.info(
                    f"[ENRICH] Skipping alert already being enriched: {fingerprint}"
                )
                continue

            # Mark as QUEUED and add to queue
            alert.enrichment_status = EnrichmentStatus.QUEUED
            self.enriching_fingerprints.add(fingerprint)
            self.enrichment_queue.put(alert)
            enriched_count += 1
            logging.info(
                f"[ENRICH] Queued alert for enrichment: {alert.original.labels.get('alertname', 'Unknown')} ({fingerprint})"
            )

        if self.view:
            if enriched_count > 0:
                self.view.add_console_line(
                    f"📋 Queued {enriched_count} alert(s) for enrichment"
                )
                # Refresh view to show QUEUED status in table
                self.view.request_refresh()
            else:
                self.view.add_console_line(
                    "✨ All selected alerts already enriched - nothing to do"
                )

    def get_alerts_for_display(self) -> List[EnrichedAlert]:
        """Get alerts in order for display."""
        return self.alert_manager.get_all_alerts() if self.alert_manager else []

    def get_alert_at_index(self, index: int) -> Optional[EnrichedAlert]:
        """Get alert at specific index."""
        return (
            self.alert_manager.get_alert_at_position(index)
            if self.alert_manager
            else None
        )

    def run(self):
        """Run the interactive UI with periodic polling."""
        # Create the interactive view
        if not self.enricher:
            # Create enricher if not provided
            self.enricher = AlertEnricher(self.config, self.alert_config.enrichment)
        self.view = AlertUIView(self.alert_config)

        # Set up logging interceptor
        log_interceptor = LogInterceptor(self.view.console)

        # Configure logging for holmes.alert_proxy modules
        alert_proxy_logger = logging.getLogger("holmes.alert_proxy")
        alert_proxy_logger.setLevel(logging.INFO)
        alert_proxy_logger.addHandler(log_interceptor)

        # Also add to root logger for other modules
        original_handlers = logging.root.handlers.copy()
        for handler in original_handlers:
            logging.root.removeHandler(handler)
        logging.root.addHandler(log_interceptor)

        try:
            # Start the view with reference to this model
            logging.info("Starting interactive view application...")
            self.view.set_model(self)  # Connect view to model
            self.view.start()
            logging.info("Interactive view started successfully")

            # Show initial welcome message
            self.view.add_console_line("🚀 HolmesGPT Alert Viewer started")
            self.view.add_console_line("")

            # Show enrichment status
            if self.enricher and self.alert_config.enrichment.enable_enrichment:
                self.view.add_console_line(
                    f"✨ AI enrichment enabled (model: {self.alert_config.enrichment.model})"
                )
                self.view.add_console_line(
                    "  Press 'e' to enrich selected alert, 'E' to enrich all"
                )
                if self.alert_config.enrichment.ai_custom_columns:
                    cols = ", ".join(
                        self.alert_config.enrichment.ai_custom_columns.keys()
                    )
                    self.view.add_console_line(f"  Custom columns: {cols}")
            else:
                self.view.add_console_line("💭 AI enrichment disabled")
            self.view.add_console_line("")

            # Start enrichment worker
            self.start_enrichment_worker()

            # Create AlertManager (it handles its own fetcher and kube_proxy)
            from holmes.alert_proxy.kube_proxy import KubeProxy

            kube_proxy = KubeProxy()
            fetcher = AlertFetcher(
                max_alerts=self.alert_config.max_alerts,
                enrich_only_firing=self.alert_config.enrichment.enrich_only_firing,
                kube_proxy=kube_proxy,
            )
            self.alert_manager = AlertManager(self.alert_config, fetcher)

            # Discover AlertManager instances
            if self.alert_config.auto_discover:
                self.view.add_console_line(
                    "🔍 Auto-discovering AlertManager instances..."
                )
                self.view.add_console_line("  • Searching in Kubernetes cluster...")
            elif self.alert_config.alertmanager_url:
                self.view.add_console_line(
                    f"📡 Using configured AlertManager URL: {self.alert_config.alertmanager_url}"
                )
            else:
                self.view.add_console_line(
                    "⚠️ No AlertManager configured, attempting auto-discovery..."
                )

            self.alert_manager.discover_alertmanagers()

            if self.alert_manager.alertmanager_instances:
                self.view.add_console_line(
                    f"✅ Found {len(self.alert_manager.alertmanager_instances)} AlertManager instance(s)"
                )
                for am in self.alert_manager.alertmanager_instances:
                    location = f"{am.namespace}/{am.name}" if am.namespace else am.name
                    self.view.add_console_line(f"  • {location}")
                self.view.add_console_line("")
                self.view.add_console_line("🔄 Starting initial alert fetch...")
            else:
                self.view.add_console_line("❌ No AlertManager instances found")
                self.view.add_console_line(
                    "  Please check your configuration or cluster setup"
                )

            # Start polling loop in a separate thread
            self.polling_thread = threading.Thread(
                target=self._polling_loop, daemon=True, name="PollingThread"
            )
            self.polling_thread.start()

            # Wait for stop signal
            while not self.view.stop_event.is_set():
                time.sleep(0.1)

        finally:
            # Stop enrichment worker
            self.stop_enrichment_worker()

            # Stop polling
            self.stop_polling.set()
            if self.polling_thread:
                self.polling_thread.join(timeout=2)

            # Stop the view
            if self.view:
                self.view.stop()

            # Restore logging handlers
            logging.root.removeHandler(log_interceptor)
            for handler in original_handlers:
                logging.root.addHandler(handler)

    def _polling_loop(self):
        """Main polling loop for fetching and displaying alerts."""
        first_poll = True
        while not self.stop_polling.is_set() and not self.view.stop_event.is_set():
            try:
                if first_poll:
                    self.view.update_status("Fetching alerts for the first time...")
                else:
                    self.view.update_status("Polling AlertManager...")

                # Poll all AlertManagers (without deduplication for interactive mode)
                fetched_alerts = self.alert_manager.poll_all(deduplicate=False)

                if fetched_alerts:
                    if first_poll:
                        self.view.add_console_line(
                            f"✨ Initial fetch complete: {len(fetched_alerts)} alerts found"
                        )
                    else:
                        self.view.add_console_line(
                            f"🔄 Update: {len(fetched_alerts)} alerts"
                        )

                # Store the fetched alerts
                self._store_fetched_alerts(fetched_alerts)

                # Notify view to refresh (view will pull data from model)
                if self.view:
                    alert_count = self.alert_manager.count()
                    if alert_count > 0:
                        self.view.add_console_line(f"Showing {alert_count} alerts")
                        self.view.update_status(
                            f"Showing {alert_count} alerts • Next poll in {self.alert_config.poll_interval}s"
                        )
                    else:
                        if first_poll:
                            self.view.add_console_line(
                                "✨ Initial fetch complete: No active alerts"
                            )
                            self.view.add_console_line(
                                "  The system is monitoring for new alerts..."
                            )
                        else:
                            self.view.add_console_line("No alerts to display")
                        self.view.mark_initial_load_complete()
                        self.view.update_status(
                            f"No alerts • Next poll in {self.alert_config.poll_interval}s"
                        )
                    self.view.request_refresh()

                first_poll = False

            except Exception as e:
                import traceback

                error_details = traceback.format_exc()
                logging.error(f"Error during polling: {e}\n{error_details}")
                self.view.add_console_line(f"Error during polling: {str(e)[:200]}")
                # Log full error to console for debugging
                for line in error_details.split("\n")[:10]:
                    if line.strip():
                        self.view.add_console_line(f"  {line}")

            # Wait for next poll or exit
            for _ in range(int(self.alert_config.poll_interval * 10)):
                if self.stop_polling.is_set() or self.view.stop_event.is_set():
                    break
                time.sleep(0.1)

    def _store_fetched_alerts(self, fetched_alerts):
        """Store newly fetched alerts in the alert manager.

        This delegates to the centralized state manager.
        """
        # Build source key for the current set of AlertManagers
        # For simplicity, we'll use "interactive-ui" as the source key
        # since this UI aggregates from all AlertManagers
        source_key = "interactive-ui"

        # Update the alert manager with the fetched alerts
        self.alert_manager.update_alerts(fetched_alerts, source_key)
