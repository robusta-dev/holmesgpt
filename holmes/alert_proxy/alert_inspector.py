"""Alert inspector for detailed view of individual alerts."""

import json
from typing import Optional
from datetime import datetime
from holmes.alert_proxy.models import EnrichedAlert, AlertStatus


class AlertInspector:
    """Provides detailed inspection of individual alerts."""

    @staticmethod
    def format_alert_details(alert: Optional[EnrichedAlert]) -> str:
        """Format alert details for the inspector pane."""
        if not alert:
            return AlertInspector._empty_inspector()

        lines = []

        # Header
        alert_name = alert.original.labels.get("alertname", "Unknown")
        lines.append(f" {alert_name}")
        lines.append("─" * 56)

        # Status and timing
        status = (
            "FIRING 🔥"
            if alert.original.status == AlertStatus.FIRING
            else "RESOLVED ✅"
        )
        lines.append(f" Status: {status}")

        # Duration
        if alert.original.startsAt:
            from datetime import timezone

            duration = datetime.now(timezone.utc) - alert.original.startsAt
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            lines.append(f" Duration: {duration_str}")

        # Started at
        if alert.original.startsAt:
            started = alert.original.startsAt.strftime("%Y-%m-%d %H:%M:%S UTC")
            lines.append(f" Started: {started}")

        lines.append("")

        # AI Enrichment - Show this BEFORE labels
        if alert.enrichment:
            # AI Analysis header with emoji
            lines.append(" 🤖 AI Analysis")
            lines.append("─" * 56)

            # Root cause analysis
            if alert.enrichment.root_cause_analysis:
                lines.append(" 🔍 Root Cause Analysis:")
                wrapped = AlertInspector._wrap_text(
                    alert.enrichment.root_cause_analysis, 54
                )
                for line in wrapped:
                    lines.append(f"  {line}")
                lines.append("")
            elif alert.enrichment.root_cause:
                lines.append(" 🔍 Root Cause:")
                wrapped = AlertInspector._wrap_text(alert.enrichment.root_cause, 54)
                for line in wrapped:
                    lines.append(f"  {line}")
                lines.append("")

            # Business impact
            if alert.enrichment.business_impact:
                lines.append(" 💼 Business Impact:")
                wrapped = AlertInspector._wrap_text(
                    alert.enrichment.business_impact, 54
                )
                for line in wrapped:
                    lines.append(f"  {line}")
                lines.append("")

            # Suggested action
            if alert.enrichment.suggested_action:
                lines.append(" 💡 Suggested Action:")
                wrapped = AlertInspector._wrap_text(
                    alert.enrichment.suggested_action, 54
                )
                for line in wrapped:
                    lines.append(f"  {line}")
                lines.append("")

            # Custom columns
            custom_cols = getattr(alert.enrichment, "custom_columns", None)
            if custom_cols:
                lines.append(" ⚙️ Custom Fields:")
                for key, value in custom_cols.items():
                    # Format key nicely
                    display_key = " ".join(w.capitalize() for w in key.split("_"))
                    wrapped = AlertInspector._wrap_text(f"{display_key}: {value}", 54)
                    for line in wrapped:
                        lines.append(f"  {line}")
                lines.append("")

        # Labels
        lines.append(" Labels")
        lines.append("─" * 56)

        for key, value in sorted(alert.original.labels.items()):
            if len(key) + len(value) > 50:
                # Truncate long values
                max_val_len = 50 - len(key) - 2
                value = value[:max_val_len] + "..."
            lines.append(f"  {key}: {value}")

        # Annotations
        if alert.original.annotations:
            lines.append("")
            lines.append(" Annotations")
            lines.append("─" * 56)

            for key, value in sorted(alert.original.annotations.items()):
                # Wrap long annotation values
                wrapped = AlertInspector._wrap_text(f"{key}: {value}", 54)
                for line in wrapped:
                    lines.append(f"  {line}")

        # Investigation results (if any)
        investigation_result = getattr(alert, "investigation_result", None)
        if investigation_result:
            lines.append("")
            lines.append(" Investigation Results")
            lines.append("─" * 56)

            wrapped = AlertInspector._wrap_text(investigation_result, 54)
            for line in wrapped:
                lines.append(f"  {line}")

        return "\n".join(lines)

    @staticmethod
    def _empty_inspector() -> str:
        """Return empty inspector view."""
        return """
 Alert Inspector
 ────────────────────────────────────────────────────────

 No alert selected

 Use j/k or arrow keys to navigate alerts
 Press 'e' to enrich the selected alert
 Press '?' for help
"""

    @staticmethod
    def _wrap_text(text: str, width: int) -> list:
        """Wrap text to fit within specified width."""
        import textwrap

        # Use textwrap with proper settings
        wrapper = textwrap.TextWrapper(
            width=width,
            break_long_words=True,
            break_on_hyphens=True,
            expand_tabs=False,
            replace_whitespace=True,
            initial_indent="",
            subsequent_indent="  ",  # Indent wrapped lines
        )

        return wrapper.wrap(text)

    @staticmethod
    def export_alert_json(alert: EnrichedAlert) -> str:
        """Export alert as JSON string."""
        data = {
            "alert": alert.original.model_dump(),
            "enrichment": alert.enrichment.model_dump() if alert.enrichment else None,
            "enrichment_status": getattr(alert, "enrichment_status", "unknown"),
        }

        # Add investigation results if present
        if hasattr(alert, "investigation_result"):
            data["investigation_result"] = getattr(alert, "investigation_result")

        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def export_alert_yaml(alert: EnrichedAlert) -> str:
        """Export alert as YAML string."""
        import yaml

        data = {
            "alert": alert.original.model_dump(),
            "enrichment": alert.enrichment.model_dump() if alert.enrichment else None,
            "enrichment_status": getattr(alert, "enrichment_status", "unknown"),
        }

        # Add investigation results if present
        if hasattr(alert, "investigation_result"):
            data["investigation_result"] = getattr(alert, "investigation_result")

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @staticmethod
    def get_alert_summary(alert: EnrichedAlert) -> str:
        """Get a brief summary of the alert."""
        alert_name = alert.original.labels.get("alertname", "Unknown")
        severity = alert.original.labels.get("severity", "unknown")
        namespace = alert.original.labels.get("namespace", "default")

        summary = f"Alert: {alert_name}\n"
        summary += f"Severity: {severity}\n"
        summary += f"Namespace: {namespace}\n"

        if alert.original.annotations.get("description"):
            summary += f"Description: {alert.original.annotations['description']}\n"

        if alert.enrichment and alert.enrichment.root_cause_analysis:
            summary += f"\nRoot Cause: {alert.enrichment.root_cause_analysis}\n"

        return summary
