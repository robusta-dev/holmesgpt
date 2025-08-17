"""HTTP server for receiving and processing AlertManager webhooks."""

import asyncio
import logging

import aiohttp
from aiohttp import web
from holmes.config import Config
from holmes.alert_proxy.enrichment import AlertEnricher
from holmes.alert_proxy.models import (
    AlertmanagerWebhook,
    ProxyConfig,
    ProxyMode,
    EnrichedAlert,
)
from holmes.alert_proxy.destinations import DestinationManager
from holmes.alert_proxy.poller import AlertManagerPoller

logger = logging.getLogger(__name__)


class AlertProxyServer:
    """HTTP server that receives AlertManager webhooks and enriches them."""

    def __init__(self, config: Config, proxy_config: ProxyConfig):
        self.config = config
        self.proxy_config = proxy_config
        # Only create enricher if enrichment is enabled
        self.enricher = (
            AlertEnricher(config, proxy_config)
            if proxy_config.enable_enrichment
            else None
        )
        self.destinations = DestinationManager(config, proxy_config)
        self.poller = None

        # Only setup web app in webhook mode
        if proxy_config.mode in [ProxyMode.WEBHOOK, ProxyMode.AUTO]:
            self.app = web.Application()
            self._setup_routes()
        else:
            self.app = None  # type: ignore

        self._stats = {
            "total_webhooks": 0,
            "total_alerts": 0,
            "enriched_alerts": 0,
            "failed_enrichments": 0,
        }

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_post("/webhook", self.handle_webhook)
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/stats", self.get_stats)
        self.app.router.add_get("/", self.index)

    async def index(self, request: web.Request) -> web.Response:
        """Root endpoint with basic info."""
        info = {
            "service": "HolmesGPT Alert Proxy",
            "version": "0.1.0",
            "status": "running",
            "endpoints": {
                "/webhook": "POST - Receive AlertManager webhooks",
                "/health": "GET - Health check",
                "/stats": "GET - Proxy statistics",
            },
            "configuration": {
                "enrichment_enabled": self.proxy_config.enable_enrichment,
                "model": self.proxy_config.model,
                "destinations": self.destinations.get_configured_destinations(),
            },
        }
        return web.json_response(info)

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "healthy"})

    async def get_stats(self, request: web.Request) -> web.Response:
        """Get proxy statistics."""
        return web.json_response(self._stats)

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming AlertManager webhook."""
        try:
            # Parse webhook payload
            data = await request.json()
            webhook = AlertmanagerWebhook(**data)

            # Apply custom columns to all alerts if specified
            if self.proxy_config.custom_columns:
                for alert in webhook.alerts:
                    for custom_col in self.proxy_config.custom_columns:
                        if "=" in custom_col:
                            key, value = custom_col.split("=", 1)
                            alert.labels[key] = value

            logger.info(f"Received webhook with {len(webhook.alerts)} alerts")
            self._stats["total_webhooks"] += 1
            self._stats["total_alerts"] += len(webhook.alerts)

            # Enrich alerts
            if self.enricher:
                enriched_alerts = await self.enricher.enrich_webhook(webhook)
            else:
                enriched_alerts = [
                    EnrichedAlert(original=alert, enrichment=None)
                    for alert in webhook.alerts
                ]
            self._stats["enriched_alerts"] += sum(
                1
                for a in enriched_alerts
                if a.enrichment
                and a.enrichment.enrichment_metadata.get("enriched") is not False
            )

            # Forward to destinations
            await self.destinations.forward_alerts(enriched_alerts, webhook)

            # Return success
            return web.json_response(
                {
                    "status": "success",
                    "alerts_processed": len(enriched_alerts),
                    "enrichment_enabled": self.proxy_config.enable_enrichment,
                }
            )

        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            self._stats["failed_enrichments"] += 1
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    def run(self):
        """Run the server based on configured mode."""
        logger.info(f"Starting Alert Proxy in {self.proxy_config.mode} mode")
        logger.info(
            f"Enrichment: {'enabled' if self.proxy_config.enable_enrichment else 'disabled'}"
        )
        logger.info(f"Model: {self.proxy_config.model}")
        logger.info(f"Destinations: {self.destinations.get_configured_destinations()}")

        if self.proxy_config.mode == ProxyMode.PULL:
            # Run in pull mode
            self.run_pull_mode()
        elif self.proxy_config.mode == ProxyMode.WEBHOOK:
            # Run in webhook mode
            self.run_webhook_mode()
        else:  # AUTO mode
            # Try pull mode first, fall back to webhook
            self.run_auto_mode()

    def run_webhook_mode(self):
        """Run in traditional webhook receiver mode."""
        logger.info(
            f"Starting webhook server on {self.proxy_config.host}:{self.proxy_config.port}"
        )

        web.run_app(
            self.app,
            host=self.proxy_config.host,
            port=self.proxy_config.port,
            print=lambda _: None,  # Suppress aiohttp startup message
        )

    def run_pull_mode(self):
        """Run in pull mode, polling AlertManager."""
        logger.info("Starting in pull mode - polling AlertManager for alerts")

        # Check if interactive mode is requested
        if hasattr(self.proxy_config, "interactive") and self.proxy_config.interactive:
            self.run_interactive_pull_mode()
            return

        # Create poller, passing the existing enricher and destinations
        self.poller = AlertManagerPoller(
            self.config,
            self.proxy_config,
            enricher=self.enricher,
            destinations=self.destinations,
        )

        # Run async poller
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.poller.start())
        except KeyboardInterrupt:
            logger.info("Shutting down poller...")
            loop.run_until_complete(self.poller.cleanup())
        finally:
            loop.close()

    def run_interactive_pull_mode(self):
        """Run in interactive pull mode with inspector view."""
        logger.info("Starting interactive pull mode with inspector view")

        from holmes.alert_proxy.poller import AlertManagerPoller

        # Create poller, passing the existing enricher and destinations
        self.poller = AlertManagerPoller(
            self.config,
            self.proxy_config,
            enricher=self.enricher,
            destinations=self.destinations,
        )

        # Run interactive view
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Start the interactive view with periodic polling
            loop.run_until_complete(self._run_interactive_loop())
        except KeyboardInterrupt:
            logger.info("Shutting down interactive view...")
            loop.run_until_complete(self.poller.cleanup())
        finally:
            loop.close()

    async def _run_interactive_loop(self):
        """Run the interactive loop with periodic polling."""
        from holmes.alert_proxy.interactive_view import AlertInteractiveView

        # Create the interactive view
        view = AlertInteractiveView(self.proxy_config)

        # Set up logging interceptor
        from holmes.alert_proxy.interactive_view import LogInterceptor

        log_interceptor = LogInterceptor(view)
        original_handlers = logging.root.handlers.copy()

        for handler in original_handlers:
            logging.root.removeHandler(handler)
        logging.root.addHandler(log_interceptor)

        try:
            # Start the view
            logger.info("Starting interactive view application...")
            view.start()
            logger.info("Interactive view started successfully")

            # Initialize poller session and discover AlertManagers
            self.poller.session = aiohttp.ClientSession()

            # Discover AlertManager instances
            if self.proxy_config.auto_discover:
                await self.poller.discover_alertmanagers()
            elif self.proxy_config.alertmanager_url:
                # Use manually configured URL
                self.poller.alertmanager_instances = [
                    {
                        "name": "configured",
                        "namespace": "unknown",
                        "url": self.proxy_config.alertmanager_url,
                        "source": "config",
                        "use_proxy": False,
                    }
                ]

            view.add_console_line(
                f"Found {len(self.poller.alertmanager_instances)} AlertManager instance(s)"
            )

            # Enricher is already initialized in the poller (passed from server __init__)

            # Polling loop
            while not view.stop_event.is_set():
                try:
                    view.update_status("Polling AlertManager...")

                    # Collect all alerts
                    all_alerts = []
                    for am in self.poller.alertmanager_instances:
                        alerts = await self.poller.fetch_alerts(am)
                        if alerts:
                            if self.proxy_config.max_alerts:
                                view.add_console_line(
                                    f"Fetched {len(alerts)} alerts from {am['name']} (limited to {self.proxy_config.max_alerts})"
                                )
                            else:
                                view.add_console_line(
                                    f"Fetched {len(alerts)} alerts from {am['name']}"
                                )

                            # Create webhook for enrichment
                            webhook = self.poller.create_webhook_payload(alerts, am)

                            # First, show alerts immediately with pending status
                            from holmes.alert_proxy.models import EnrichedAlert

                            for alert in webhook.alerts:
                                enriched_alert = EnrichedAlert(
                                    original=alert,
                                    enrichment=None,
                                    enrichment_status="pending"
                                    if self.proxy_config.enable_enrichment
                                    else "skipped",
                                )
                                all_alerts.append(enriched_alert)

                    # Update view immediately with pending alerts
                    if all_alerts:
                        view.add_console_line(f"Showing {len(all_alerts)} alerts")
                        view.update_alerts(all_alerts)
                        view.update_status(f"Showing {len(all_alerts)} alerts")

                        # Now enrich them if enabled
                        if self.proxy_config.enable_enrichment and self.poller.enricher:
                            view.add_console_line("Starting AI enrichment...")

                            # Update status to in_progress
                            for alert in all_alerts:
                                alert.enrichment_status = "in_progress"
                            view.update_alerts(all_alerts)

                            # Enrich each alert individually and update the view
                            for i, alert in enumerate(all_alerts):
                                try:
                                    view.add_console_line(
                                        f"Enriching alert {i+1}/{len(all_alerts)}: {alert.original.labels.get('alertname', 'Unknown')}"
                                    )

                                    # Create single-alert webhook for enrichment
                                    single_webhook = self.poller.create_webhook_payload(
                                        [alert.original],
                                        self.poller.alertmanager_instances[0],
                                    )
                                    enriched_results = (
                                        await self.poller.enricher.enrich_webhook(
                                            single_webhook
                                        )
                                    )

                                    if enriched_results:
                                        # Update the alert with enrichment
                                        alert.enrichment = enriched_results[
                                            0
                                        ].enrichment
                                        alert.enrichment_status = "completed"
                                    else:
                                        alert.enrichment_status = "failed"

                                    # Update view after each alert is enriched
                                    view.update_alerts(all_alerts)

                                except Exception as e:
                                    view.add_console_line(
                                        f"Failed to enrich alert: {str(e)}"
                                    )
                                    alert.enrichment_status = "failed"
                                    view.update_alerts(all_alerts)

                            view.add_console_line("Enrichment complete")

                        view.update_status(
                            f"Showing {len(all_alerts)} alerts • Next poll in {self.proxy_config.poll_interval}s"
                        )
                    else:
                        view.add_console_line("No alerts to display")
                        view.update_status(
                            f"No alerts • Next poll in {self.proxy_config.poll_interval}s"
                        )

                except Exception as e:
                    import traceback

                    error_details = traceback.format_exc()
                    logger.error(f"Error during polling: {e}\n{error_details}")
                    view.add_console_line(f"Error during polling: {str(e)[:200]}")
                    # Log full error to console for debugging
                    for line in error_details.split("\n")[:10]:
                        if line.strip():
                            view.add_console_line(f"  {line}")

                # Wait for next poll or exit
                await asyncio.sleep(self.proxy_config.poll_interval)

        finally:
            # Stop the view
            view.stop()

            # Clean up poller session
            if self.poller.session:
                await self.poller.session.close()

            # Restore logging handlers
            logging.root.removeHandler(log_interceptor)
            for handler in original_handlers:
                logging.root.addHandler(handler)

    def run_auto_mode(self):
        """Run in auto mode - discover and choose best approach."""
        logger.info("Starting in auto mode - discovering AlertManager setup")

        # Try to discover AlertManager
        from holmes.alert_proxy.discovery import AlertManagerDiscovery

        discovery = AlertManagerDiscovery()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            discovered = loop.run_until_complete(discovery.discover_all())

            if discovered:
                logger.info(
                    f"Found {len(discovered)} AlertManager instance(s), using pull mode"
                )
                self.proxy_config.mode = ProxyMode.PULL
                self.run_pull_mode()
            else:
                logger.info("No AlertManager instances found, starting webhook server")
                self.proxy_config.mode = ProxyMode.WEBHOOK
                self.run_webhook_mode()
        finally:
            loop.close()
