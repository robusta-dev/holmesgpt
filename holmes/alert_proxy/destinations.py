"""Destination handlers for forwarding enriched alerts."""

import logging
from typing import List, Optional
import json

import requests
from rich.console import Console
from rich.table import Table
from holmes.config import Config
from holmes.alert_proxy.models import (
    AlertmanagerWebhook,
    AlertStatus,
    EnrichedAlert,
    WebhookModeConfig,
)

logger = logging.getLogger(__name__)


class DestinationManager:
    """Manages forwarding enriched alerts to various destinations."""

    def __init__(self, config: Config, webhook_config: WebhookModeConfig):
        self.config = config
        self.webhook_config = webhook_config
        self.session: Optional[requests.Session] = None
        self.console = Console()

    def _ensure_session(self):
        """Ensure we have a requests session."""
        if not self.session:
            self.session = requests.Session()

    def get_configured_destinations(self) -> List[str]:
        """Get list of configured destinations."""
        destinations = []
        if self.webhook_config.slack_webhook_url:
            destinations.append("slack")
        if self.webhook_config.alertmanager_url:
            destinations.append("alertmanager")
        for url in self.webhook_config.webhook_urls:
            destinations.append(f"webhook:{url}")
        return destinations

    def forward_alerts(
        self,
        enriched_alerts: List[EnrichedAlert],
        original_webhook: AlertmanagerWebhook,
    ):
        """Forward enriched alerts to all configured destinations."""
        self._ensure_session()

        # Always show in console if no other destinations configured
        has_destinations = any(
            [
                self.webhook_config.slack_webhook_url,
                self.webhook_config.alertmanager_url,
                self.webhook_config.webhook_urls,
            ]
        )

        if not has_destinations:
            # Console-only mode
            self._print_to_console(enriched_alerts)

        # Process destinations sequentially
        errors = []

        # Slack
        if self.webhook_config.slack_webhook_url:
            try:
                self._send_to_slack(enriched_alerts)
            except Exception as e:
                errors.append(f"Slack: {e}")
                logger.error(f"Failed to send to Slack: {e}")

        # AlertManager (forward original with enriched annotations)
        if self.webhook_config.alertmanager_url:
            try:
                self._forward_to_alertmanager(enriched_alerts, original_webhook)
            except Exception as e:
                errors.append(f"AlertManager: {e}")
                logger.error(f"Failed to forward to AlertManager: {e}")

        # Additional webhooks
        for url in self.webhook_config.webhook_urls:
            try:
                self._send_to_webhook(url, enriched_alerts)
            except Exception as e:
                errors.append(f"Webhook {url}: {e}")
                logger.error(f"Failed to send to webhook {url}: {e}")

        if errors:
            logger.error(f"Some destinations failed: {errors}")

    def _send_to_slack(self, alerts: List[EnrichedAlert]):
        """Send enriched alerts to Slack in default AlertManager format."""
        if not alerts:
            return

        # Group alerts by status
        firing_alerts = [a for a in alerts if a.original.status == "firing"]
        resolved_alerts = [a for a in alerts if a.original.status == "resolved"]

        # Build status header like default AlertManager
        status_parts = []
        if firing_alerts:
            status_parts.append(f"FIRING:{len(firing_alerts)}")
        if resolved_alerts:
            status_parts.append(f"RESOLVED:{len(resolved_alerts)}")

        # Group by alertname and severity for the title
        alert_groups: dict[tuple[str, str], list] = {}
        for alert in alerts:
            alert_name = alert.original.labels.get("alertname", "Unknown")
            severity = alert.original.labels.get("severity", "")
            key = (alert_name, severity)
            if key not in alert_groups:
                alert_groups[key] = []
            alert_groups[key].append(alert)

        # Build title - show first alertname (bold)
        first_alert = alerts[0]
        title_alert_name = first_alert.original.labels.get("alertname", "Alert")

        # Simple bold title like AlertManager default
        title = f"*[{', '.join(status_parts)}] {title_alert_name}*"

        # Build message sections for each alert
        sections = []

        for alert in alerts:
            alert_name = alert.original.labels.get("alertname", "Unknown")
            severity = alert.original.labels.get("severity", "")

            # Build alert header
            alert_header = f"*Alert:* {alert.original.labels.get('alertname', 'Alert')}"
            if alert.original.labels.get("instance"):
                alert_header += f" {alert.original.labels.get('instance')}"
            if alert.original.status == "resolved":
                alert_header += " - ✅ resolved"
            else:
                alert_header += f" - {severity}" if severity else ""

            # Build description
            description = alert.original.annotations.get(
                "description"
            ) or alert.original.annotations.get("summary", "")

            # Build details section with key labels
            details_lines = []
            if description:
                details_lines.append(f"*Description:* {description}")

            details_lines.append("*Details:*")

            # Add important labels as bullet points
            for label_key in [
                "alertname",
                "instance",
                "job",
                "severity",
                "namespace",
                "pod",
                "service",
            ]:
                if value := alert.original.labels.get(label_key):
                    details_lines.append(f"  • *{label_key}:* `{value}`")

            # Add AI enrichment as additional detail items
            if alert.enrichment:
                # Check if using custom columns only or default enrichment
                if alert.enrichment.enrichment_metadata:
                    # Custom columns mode - show all custom fields
                    for meta_key, value in alert.enrichment.enrichment_metadata.items():
                        if (
                            meta_key not in ["model", "parse_error", "raw_response"]
                            and value
                        ):
                            # Use the original key with ai_ prefix for consistency
                            details_lines.append(f"  • *ai_{meta_key}⚡:* {str(value)}")

                # Also show default fields if they exist (when not skipping default)
                if alert.enrichment.root_cause:
                    details_lines.append(
                        f"  • *ai_analysis⚡:* {alert.enrichment.root_cause}"
                    )

                if alert.enrichment.suggested_action:
                    details_lines.append(
                        f"  • *ai_suggested_action⚡:* {alert.enrichment.suggested_action}"
                    )

                # Show business impact if available
                if alert.enrichment.business_impact:
                    details_lines.append(
                        f"  • *ai_business_impact⚡:* {alert.enrichment.business_impact}"
                    )

            # Combine into section text
            section_text = alert_header + "\n" + "\n".join(details_lines)
            sections.append(section_text)

        # Build footer with model info if available
        footer = None
        if any(a.enrichment for a in alerts):
            # Try to get model from enrichment metadata
            model = None
            for alert in alerts:
                if alert.enrichment and alert.enrichment.enrichment_metadata:
                    model = alert.enrichment.enrichment_metadata.get("model")
                    if model:
                        break

            if model:
                footer = f"⚡ AI-enriched by Holmes ({model})"
            else:
                footer = "⚡ AI-enriched by Holmes"

        # Build Slack message using attachments (like default AlertManager)
        payload = {
            "username": "AlertManager",
            "text": title,
            "attachments": [
                {
                    "color": "danger" if firing_alerts else "good",
                    "text": "\n\n".join(sections),
                    "mrkdwn_in": ["text"],
                    "footer": footer,
                }
            ],
        }

        try:
            if not self.session:
                logger.error("No session available for Slack webhook")
                return
            if not self.webhook_config.slack_webhook_url:
                logger.error("No Slack webhook URL configured")
                return
            response = self.session.post(
                self.webhook_config.slack_webhook_url,
                json=payload,
                timeout=10,
            )
            if response.status_code != 200:
                logger.error(
                    f"Slack webhook failed: {response.status_code} - {response.text}"
                )
            else:
                logger.info(f"Sent {len(alerts)} alerts to Slack")
        except Exception as e:
            logger.error(f"Failed to send to Slack: {e}")

    def _forward_to_alertmanager(
        self,
        enriched_alerts: List[EnrichedAlert],
        original_webhook: AlertmanagerWebhook,
    ):
        """Forward to AlertManager with enriched annotations."""
        # Create modified webhook with enriched annotations
        modified_webhook = original_webhook.model_copy()

        for i, alert in enumerate(modified_webhook.alerts):
            if i < len(enriched_alerts):
                enriched = enriched_alerts[i]

                # Add ALL enrichment fields as annotations generically
                if enriched.enrichment:
                    enrichment_dict = enriched.enrichment.model_dump(exclude_none=True)

                    # Add each non-empty field as an annotation
                    for field_name, field_value in enrichment_dict.items():
                        # Convert lists to comma-separated strings
                        if isinstance(field_value, list):
                            if field_value:  # Only add if list is not empty
                                alert.annotations[f"ai_{field_name}"] = ",".join(
                                    str(v) for v in field_value
                                )
                        # Add dictionaries as JSON strings
                        elif isinstance(field_value, dict):
                            if field_value:  # Only add if dict is not empty
                                alert.annotations[f"ai_{field_name}"] = json.dumps(
                                    field_value
                                )
                        # Add other types directly
                        elif field_value:
                            alert.annotations[f"ai_{field_name}"] = str(field_value)

        # Forward to AlertManager
        try:
            if not self.session:
                logger.error("No session available for AlertManager forward")
                return
            response = self.session.post(
                f"{self.webhook_config.alertmanager_url}/api/v1/alerts",
                json=[alert.model_dump() for alert in modified_webhook.alerts],
                timeout=10,
            )
            if response.status_code not in (200, 202):
                logger.error(
                    f"AlertManager forward failed: {response.status_code} - {response.text}"
                )
            else:
                logger.info(
                    f"Forwarded {len(modified_webhook.alerts)} alerts to AlertManager"
                )
        except Exception as e:
            logger.error(f"Failed to forward to AlertManager: {e}")

    def _send_to_webhook(self, url: str, alerts: List[EnrichedAlert]):
        """Send enriched alerts to a generic webhook."""
        payload = {
            "alerts": [
                {
                    "original": alert.original.model_dump(),
                    "enrichment": alert.enrichment.model_dump()
                    if alert.enrichment
                    else None,
                    "enriched_at": alert.enriched_at.isoformat(),
                }
                for alert in alerts
            ]
        }

        try:
            if not self.session:
                logger.error("No session available for webhook forward")
                return
            response = self.session.post(url, json=payload, timeout=10)
            if response.status_code not in (200, 201, 202):
                logger.error(
                    f"Webhook {url} failed: {response.status_code} - {response.text}"
                )
            else:
                logger.info(f"Sent {len(alerts)} alerts to {url}")
        except Exception as e:
            logger.error(f"Failed to send to webhook {url}: {e}")

    def _print_to_console(self, alerts: List[EnrichedAlert]):
        """Print enriched alerts to console in a table format."""
        from rich.text import Text
        from rich import box

        if not alerts:
            return

        # Create table
        table = Table(
            title=f"\n📢 {len(alerts)} Alert(s) at {alerts[0].enriched_at.strftime('%H:%M:%S')}",
            box=box.ROUNDED,
            show_lines=True,
            title_style="bold cyan",
            header_style="bold",
            width=None,
        )

        # Add columns
        table.add_column("Alert", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Severity", justify="center")
        table.add_column("Labels", overflow="fold", max_width=35)

        # Check if we have custom columns to display
        custom_columns = []
        if alerts and alerts[0].enrichment and alerts[0].enrichment.enrichment_metadata:
            # Get all custom columns from the first alert (should be same for all)
            for key in alerts[0].enrichment.enrichment_metadata.keys():
                if key != "model" and key not in ["parse_error", "raw_response"]:
                    custom_columns.append(key)

        # Add custom columns to table
        for col in custom_columns:
            # Make column name readable (e.g., related_kubernetes_resource -> Related Kubernetes Resource)
            col_display = " ".join(word.capitalize() for word in col.split("_"))
            table.add_column(col_display, overflow="fold", max_width=30)

        # Only add default columns if not skipping default enrichment
        if not (
            custom_columns and self.webhook_config.enrichment.skip_default_enrichment
        ):
            table.add_column("AI Summary", overflow="fold", max_width=45)
            table.add_column("Suggested Action", overflow="fold", max_width=35)

        for alert in alerts:
            # Alert name
            alert_name = alert.original.labels.get("alertname", "Unknown")

            # Status with color
            if alert.original.status == AlertStatus.FIRING:
                status = Text("🔥 FIRING", style="bold red")
            else:
                status = Text("✅ RESOLVED", style="bold green")

            # Severity with icon
            severity = alert.original.labels.get("severity", "unknown").lower()
            if severity == "critical":
                severity_text = Text("🔴 Critical", style="red")
            elif severity == "warning":
                severity_text = Text("🟡 Warning", style="yellow")
            elif severity == "info":
                severity_text = Text("🔵 Info", style="blue")
            else:
                severity_text = Text("⚪ " + severity.title(), style="dim")

            # Format labels (exclude alertname and severity)
            labels_list = []
            for k, v in alert.original.labels.items():
                if k not in ["alertname", "severity", "__name__"]:
                    # Truncate long values
                    if len(v) > 25:
                        v = v[:22] + "..."
                    labels_list.append(f"{k}={v}")

            # Join labels with newlines for better readability
            if labels_list:
                labels_text = Text("\n".join(labels_list[:4]))  # Show first 4 labels
                if len(labels_list) > 4:
                    labels_text.append(f"\n+{len(labels_list)-4} more", style="dim")
            else:
                labels_text = Text("-", style="dim")

            # Build row data
            row_data = [alert_name, status, severity_text, labels_text]

            # Add custom column values
            for col in custom_columns:
                value = (
                    alert.enrichment.enrichment_metadata.get(col, "-")
                    if alert.enrichment
                    else "-"
                )
                if value and value != "-":
                    row_data.append(Text(str(value), style="magenta"))
                else:
                    row_data.append(Text("-", style="dim"))

            # Add default columns if not skipping
            if not (
                custom_columns
                and self.webhook_config.enrichment.skip_default_enrichment
            ):
                # AI analysis
                if alert.enrichment and alert.enrichment.root_cause:
                    summary = Text(alert.enrichment.root_cause[:100], style="cyan")
                else:
                    summary = Text("[Awaiting enrichment]", style="dim italic")

                # Suggested action
                if alert.enrichment and alert.enrichment.suggested_action:
                    action = Text(alert.enrichment.suggested_action, style="green")
                else:
                    action = Text("-", style="dim")

                row_data.extend([summary, action])

            # Add row (convert all to strings for type safety)
            table.add_row(*[str(item) for item in row_data])

        # Print the table
        self.console.print(table)
        self.console.print()  # Empty line after table

    def close(self):
        """Close the requests session."""
        if self.session:
            self.session.close()
