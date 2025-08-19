"""Alert formatting utilities for the interactive view."""

from typing import List, Optional
from holmes.alert_proxy.models import EnrichedAlert, AlertStatus


class AlertFormatter:
    """Formats alerts for display in the interactive UI."""

    @staticmethod
    def format_severity(severity: str) -> str:
        """Format severity with appropriate icon."""
        severity = severity.lower()
        severity_icons = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵",
        }
        icon = severity_icons.get(severity, "⚪")
        return f"{icon} {severity}"

    @staticmethod
    def format_status(status: AlertStatus) -> str:
        """Format alert status with icon."""
        if status == AlertStatus.FIRING:
            return "● FIRING"  # Simple bullet instead of fire emoji
        return "○ RESOLVED"  # Hollow bullet for resolved

    @staticmethod
    def format_enrichment_status(alert: EnrichedAlert) -> str:
        """Format the enrichment status of an alert."""
        from holmes.alert_proxy.models import EnrichmentStatus

        # Simple text, no symbols
        status_text = {
            EnrichmentStatus.READY: "-",
            EnrichmentStatus.QUEUED: "queued",
            EnrichmentStatus.IN_PROGRESS: "in progress",
            EnrichmentStatus.COMPLETED: "✨ enriched",  # Add sparkle emoji for AI-enriched
            EnrichmentStatus.FAILED: "failed",
        }
        return status_text.get(alert.enrichment_status, "-")

    @staticmethod
    def truncate_text(text: str, max_length: int = 25) -> str:
        """Truncate text to fit in a column."""
        if len(text) > max_length:
            return text[: max_length - 3] + "..."
        return text

    @staticmethod
    def format_custom_column_value(
        alert: EnrichedAlert, column_name: str, max_length: int = 20
    ) -> str:
        """Extract and format a custom AI column value."""
        if not alert.enrichment:
            return "-"

        # Check if value exists in custom columns
        custom_cols = getattr(alert.enrichment, "custom_columns", None)
        if custom_cols and column_name in custom_cols:
            value = str(custom_cols[column_name])
            return AlertFormatter.truncate_text(value, max_length)

        return "-"

    @staticmethod
    def format_alert_name(alert: EnrichedAlert, max_length: int = 25) -> str:
        """Format alert name for display."""
        alert_name = alert.original.labels.get("alertname", "Unknown")
        return AlertFormatter.truncate_text(alert_name, max_length)

    @staticmethod
    def format_namespace(alert: EnrichedAlert) -> str:
        """Format namespace for display."""
        namespace = alert.original.labels.get("namespace", "-")
        return AlertFormatter.truncate_text(namespace, 15)

    @staticmethod
    def format_duration(alert: EnrichedAlert) -> str:
        """Format alert duration."""
        from datetime import datetime, timezone

        if not alert.original.startsAt:
            return "-"

        duration = datetime.now(timezone.utc) - alert.original.startsAt
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @staticmethod
    def build_alert_row(
        alert: EnrichedAlert,
        is_selected: bool,
        custom_columns: Optional[List[str]] = None,
    ) -> List[str]:
        """Build a row of data for an alert."""
        row_parts = []

        # Selection indicator
        selector = "▶" if is_selected else " "
        row_parts.append(selector)

        # Alert name
        row_parts.append(AlertFormatter.format_alert_name(alert))

        # Status
        row_parts.append(AlertFormatter.format_status(alert.original.status))

        # Severity
        severity = alert.original.labels.get("severity", "unknown")
        row_parts.append(AlertFormatter.format_severity(severity))

        # AI Status
        row_parts.append(AlertFormatter.format_enrichment_status(alert))

        # Custom columns if provided
        if custom_columns:
            for col in custom_columns:
                row_parts.append(AlertFormatter.format_custom_column_value(alert, col))

        return row_parts
