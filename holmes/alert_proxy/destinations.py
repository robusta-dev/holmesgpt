"""Destination handlers for forwarding enriched alerts."""

import asyncio
import logging
from typing import List, Optional

import aiohttp
from rich.console import Console
from rich.table import Table
from holmes.config import Config
from holmes.alert_proxy.models import (
    AlertmanagerWebhook,
    AlertStatus,
    EnrichedAlert,
    ProxyConfig,
)

logger = logging.getLogger(__name__)


class DestinationManager:
    """Manages forwarding enriched alerts to various destinations."""

    def __init__(self, config: Config, proxy_config: ProxyConfig):
        self.config = config
        self.proxy_config = proxy_config
        self.session: Optional[aiohttp.ClientSession] = None
        self.console = Console()

    async def _ensure_session(self):
        """Ensure we have an aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def forward_alerts(
        self,
        enriched_alerts: List[EnrichedAlert],
        original_webhook: AlertmanagerWebhook,
    ):
        """Forward enriched alerts to all configured destinations."""
        await self._ensure_session()

        # Always show in console if no other destinations configured
        has_destinations = any(
            [
                self.proxy_config.slack_webhook_url,
                self.proxy_config.alertmanager_url,
                self.proxy_config.webhook_urls,
            ]
        )

        if not has_destinations:
            # Console-only mode
            await self._print_to_console(enriched_alerts)

        tasks = []

        # Slack
        if self.proxy_config.slack_webhook_url:
            tasks.append(self._send_to_slack(enriched_alerts))

        # AlertManager (forward original with enriched annotations)
        if self.proxy_config.alertmanager_url:
            tasks.append(
                self._forward_to_alertmanager(enriched_alerts, original_webhook)
            )

        # Additional webhooks
        for url in self.proxy_config.webhook_urls:
            tasks.append(self._send_to_webhook(url, enriched_alerts))

        # HolmesGPT investigation
        if self.proxy_config.enable_investigation:
            tasks.append(self._trigger_investigation(enriched_alerts))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Destination {i} failed: {result}")

    async def _send_to_slack(self, alerts: List[EnrichedAlert]):
        """Send enriched alerts to Slack."""
        if not alerts:
            return

        # Group alerts by priority
        critical_alerts = [
            a for a in alerts if a.original.labels.get("severity") == "critical"
        ]
        warning_alerts = [
            a for a in alerts if a.original.labels.get("severity") == "warning"
        ]
        other_alerts = [
            a for a in alerts if a not in critical_alerts and a not in warning_alerts
        ]

        # Build Slack message
        blocks = []

        # Add header
        alert_count = len(alerts)
        firing_count = sum(1 for a in alerts if a.original.status == "firing")

        if firing_count > 0:
            header_text = (
                f"🚨 {firing_count} Alert{'s' if firing_count != 1 else ''} Firing"
            )
        else:
            header_text = (
                f"✅ {alert_count} Alert{'s' if alert_count != 1 else ''} Resolved"
            )

        blocks.append(
            {"type": "header", "text": {"type": "plain_text", "text": header_text}}
        )

        # Add summary if multiple alerts
        if alert_count > 1:
            summary_parts = []
            if critical_alerts:
                summary_parts.append(f"🔴 {len(critical_alerts)} critical")
            if warning_alerts:
                summary_parts.append(f"🟡 {len(warning_alerts)} warning")
            if other_alerts:
                summary_parts.append(f"🔵 {len(other_alerts)} other")

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": " • ".join(summary_parts)},
                }
            )
            blocks.append({"type": "divider"})

        # Add top 3 most important alerts (skip sorting by deprecated priority_score)
        # Just use the first 3 alerts in order
        sorted_alerts = alerts
        for alert in sorted_alerts[:3]:
            blocks.extend(alert.to_slack_blocks())
            if alert != sorted_alerts[min(2, len(sorted_alerts) - 1)]:
                blocks.append({"type": "divider"})

        # Send to Slack
        payload = {"blocks": blocks}

        try:
            if not self.session:
                logger.error("No session available for Slack webhook")
                return
            if not self.proxy_config.slack_webhook_url:
                logger.error("No Slack webhook URL configured")
                return
            async with self.session.post(
                self.proxy_config.slack_webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Slack webhook failed: {response.status} - {text}")
                else:
                    logger.info(f"Sent {alert_count} alerts to Slack")
        except Exception as e:
            logger.error(f"Failed to send to Slack: {e}")

    async def _forward_to_alertmanager(
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
                # Add AI-generated annotations (check enrichment exists first)
                if enriched.enrichment:
                    # Skip deprecated summary field
                    if enriched.enrichment.business_impact:
                        alert.annotations["ai_business_impact"] = (
                            enriched.enrichment.business_impact
                        )
                    if enriched.enrichment.root_cause:
                        alert.annotations["ai_root_cause"] = (
                            enriched.enrichment.root_cause
                        )
                    if enriched.enrichment.suggested_action:
                        alert.annotations["ai_suggested_action"] = (
                            enriched.enrichment.suggested_action
                        )
                    # Skip deprecated priority_score field - no routing by priority

                if enriched.enrichment and enriched.enrichment.affected_services:
                    alert.labels["ai_affected_services"] = ",".join(
                        enriched.enrichment.affected_services
                    )

        # Forward to AlertManager
        try:
            if not self.session:
                logger.error("No session available for AlertManager forward")
                return
            async with self.session.post(
                f"{self.proxy_config.alertmanager_url}/api/v1/alerts",
                json=[alert.model_dump() for alert in modified_webhook.alerts],
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status not in (200, 202):
                    text = await response.text()
                    logger.error(
                        f"AlertManager forward failed: {response.status} - {text}"
                    )
                else:
                    logger.info(
                        f"Forwarded {len(modified_webhook.alerts)} alerts to AlertManager"
                    )
        except Exception as e:
            logger.error(f"Failed to forward to AlertManager: {e}")

    async def _send_to_webhook(self, url: str, alerts: List[EnrichedAlert]):
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
            async with self.session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status not in (200, 201, 202):
                    text = await response.text()
                    logger.error(f"Webhook {url} failed: {response.status} - {text}")
                else:
                    logger.info(f"Sent {len(alerts)} alerts to {url}")
        except Exception as e:
            logger.error(f"Failed to send to webhook {url}: {e}")

    async def _trigger_investigation(self, alerts: List[EnrichedAlert]):
        """Trigger HolmesGPT investigation for critical alerts."""
        # Only investigate critical firing alerts
        critical_alerts = [
            a
            for a in alerts
            if a.original.status == "firing"
            and a.original.labels.get("severity") == "critical"
        ]

        if not critical_alerts:
            return

        for alert in critical_alerts[:1]:  # Investigate top priority alert
            try:
                # Build investigation command
                namespace = alert.original.labels.get("namespace", "default")
                alert_name = alert.original.labels.get("alertname", "Unknown")

                # This would integrate with HolmesGPT's investigation API
                # For now, we just log it
                investigation_query = (
                    f"Investigate {alert_name} in namespace {namespace}"
                )

                logger.info(f"Would trigger investigation: {investigation_query}")

                # In real implementation:
                # from holmes.core.investigation import investigate_issue
                # await investigate_issue(investigation_query, namespace=namespace)

                # Update the enrichment with investigation URL if enrichment exists
                if alert.enrichment:
                    alert.enrichment.investigation_url = f"http://holmes.local/investigations/{alert.original.fingerprint}"

            except Exception as e:
                logger.error(f"Failed to trigger investigation: {e}")

    async def _print_to_console(self, alerts: List[EnrichedAlert]):
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
        if not (custom_columns and self.proxy_config.skip_default_enrichment):
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
            if not (custom_columns and self.proxy_config.skip_default_enrichment):
                # AI analysis (skip deprecated summary/priority fields)
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

    def get_configured_destinations(self) -> List[str]:
        """Get list of configured destinations."""
        destinations = []
        if self.proxy_config.slack_webhook_url:
            destinations.append("slack")
        if self.proxy_config.alertmanager_url:
            destinations.append("alertmanager")
        if self.proxy_config.webhook_urls:
            destinations.append(f"{len(self.proxy_config.webhook_urls)} webhooks")
        if self.proxy_config.enable_investigation:
            destinations.append("holmes-investigation")

        # If no destinations, we're in console mode
        if not destinations:
            destinations.append("console")

        return destinations

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
