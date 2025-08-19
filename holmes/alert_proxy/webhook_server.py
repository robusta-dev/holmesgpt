"""HTTP webhook server for receiving AlertManager alerts."""

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from holmes.alert_proxy.models import (
    AlertmanagerWebhook,
)
from holmes.alert_proxy.alert_enrichment import AlertEnricher
from holmes.alert_proxy.destinations import DestinationManager

logger = logging.getLogger(__name__)


class AlertWebhookServer:
    """HTTP server that ONLY handles webhook receiving and processing."""

    def __init__(
        self,
        enricher: AlertEnricher,
        destinations: DestinationManager,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        """Initialize webhook server with required components.

        Args:
            enricher: Enricher for AI analysis
            destinations: Manager for forwarding alerts
            host: Host to bind to
            port: Port to listen on
        """
        self.enricher = enricher
        self.destinations = destinations
        self.host = host
        self.port = port

        # Statistics
        self._stats = {
            "total_webhooks": 0,
            "total_alerts": 0,
            "enriched_alerts": 0,
            "failed_enrichments": 0,
            "total_enrichment_time": 0.0,
            "avg_enrichment_time": 0.0,
        }

        # Server will be created in run()
        self.server = None
        self.server_thread = None

    def _create_request_handler(self):
        """Create a request handler class with access to the server instance."""
        server_instance = self

        class WebhookRequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                """Handle GET requests."""
                if self.path == "/":
                    info = {
                        "service": "HolmesGPT Alert Webhook Server",
                        "version": "0.1.0",
                        "status": "running",
                        "endpoints": {
                            "/webhook": "POST - Receive AlertManager webhooks",
                            "/health": "GET - Health check",
                            "/stats": "GET - Server statistics",
                        },
                        "configuration": {
                            "enrichment_enabled": True,
                            "destinations": server_instance.destinations.get_configured_destinations(),
                        },
                        "stats": server_instance._stats,
                    }
                    self._send_json_response(200, info)
                elif self.path == "/health":
                    self._send_json_response(
                        200, {"status": "healthy", "service": "alert-webhook-server"}
                    )
                elif self.path == "/stats":
                    self._send_json_response(200, server_instance._stats)
                else:
                    self.send_error(404)

            def do_POST(self):
                """Handle POST requests."""
                if self.path == "/webhook":
                    try:
                        # Parse webhook payload
                        content_length = int(self.headers["Content-Length"])
                        post_data = self.rfile.read(content_length)
                        data = json.loads(post_data)
                        webhook = AlertmanagerWebhook(**data)

                        # Update stats
                        server_instance._stats["total_webhooks"] += 1
                        server_instance._stats["total_alerts"] += len(webhook.alerts)

                        logger.info(
                            f"Received webhook with {len(webhook.alerts)} alerts "
                            f"(status: {webhook.status}, version: {webhook.version})"
                        )

                        # Process alerts with AI enrichment (now synchronous)
                        import time

                        start_time = time.time()
                        enriched_alerts = server_instance.enricher.enrich_webhook(
                            webhook
                        )
                        enrichment_time = time.time() - start_time

                        # Update statistics
                        enriched_count = len(
                            [a for a in enriched_alerts if a.enrichment]
                        )
                        server_instance._stats["enriched_alerts"] += enriched_count
                        server_instance._stats["total_enrichment_time"] += (
                            enrichment_time
                        )

                        # Calculate average enrichment time
                        if server_instance._stats["enriched_alerts"] > 0:
                            server_instance._stats["avg_enrichment_time"] = (
                                server_instance._stats["total_enrichment_time"]
                                / server_instance._stats["enriched_alerts"]
                            )

                        # Forward to destinations (now synchronous)
                        server_instance.destinations.forward_alerts(
                            enriched_alerts, webhook
                        )

                        # Return success response
                        response = {
                            "status": "success",
                            "alerts_received": len(webhook.alerts),
                            "alerts_enriched": len(
                                [a for a in enriched_alerts if a.enrichment]
                            ),
                        }
                        self._send_json_response(200, response)

                    except Exception as e:
                        logger.error(f"Error processing webhook: {e}", exc_info=True)
                        server_instance._stats["failed_enrichments"] += 1
                        self._send_json_response(
                            500, {"status": "error", "message": str(e)}
                        )
                else:
                    self.send_error(404)

            def _send_json_response(self, code, data):
                """Send a JSON response."""
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))

            def log_message(self, format, *args):
                """Override to use our logger."""
                logger.debug(f"{self.client_address[0]} - {format % args}")

        return WebhookRequestHandler

    def run(self):
        """Run the webhook server."""
        logger.info(f"Starting webhook server on {self.host}:{self.port}")

        # Create HTTP server with our custom handler
        handler_class = self._create_request_handler()
        self.server = HTTPServer((self.host, self.port), handler_class)

        logger.info(f"Webhook server listening on http://{self.host}:{self.port}")
        logger.info("POST webhooks to /webhook")

        # Run server in a separate thread
        def serve():
            try:
                self.server.serve_forever()
            except Exception as e:
                logger.error(f"Server error: {e}")

        self.server_thread = threading.Thread(target=serve, daemon=True)
        self.server_thread.start()

        # Wait for shutdown
        try:
            self.server_thread.join()
        except KeyboardInterrupt:
            logger.info("Shutting down webhook server...")
            self.shutdown()

    def shutdown(self):
        """Shutdown the server."""
        if self.server:
            self.server.shutdown()
        if hasattr(self.destinations, "close"):
            self.destinations.close()
        logger.info("Webhook server stopped")
