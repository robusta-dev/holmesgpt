"""
Alert list rendering functionality for the interactive view.
Handles formatting and display of the alert list.
"""

from typing import List, Optional, TYPE_CHECKING

from holmes.alert_proxy.alert_formatter import AlertFormatter

if TYPE_CHECKING:
    from holmes.alert_proxy.models import EnrichedAlert
    from holmes.alert_proxy.models import InteractiveModeConfig


class AlertListRenderer:
    """Renders the alert list for display in the UI."""

    def __init__(self, alert_config: "InteractiveModeConfig"):
        """
        Initialize the alert list renderer.

        Args:
            alert_config: Alert configuration containing display settings
        """
        self.alert_config = alert_config
        self.formatter = AlertFormatter()
        self.initial_load_complete = False

    def render_empty_state(self) -> str:
        """
        Render the empty state when no alerts are present.

        Returns:
            Formatted text for empty alert list
        """
        if self.initial_load_complete:
            # No alerts found after loading - simple clean message
            return f"""
  ✓ AlertManager connected

  No active alerts found.

  The system is currently healthy.
  Next check in: {self.alert_config.poll_interval}s
"""
        else:
            return "\n Loading alerts..."

    def render_no_matches(self, filter_text: str) -> str:
        """
        Render message when no alerts match the current filter.

        Args:
            filter_text: The filter that produced no matches

        Returns:
            Formatted text for no matches state
        """
        return f"\n  No alerts match: '{filter_text}'\n  Press ESC to clear filter or / to search again"

    def render_alert_list(
        self,
        alerts: List["EnrichedAlert"],
        visible_indices: List[int],
        selected_index: int,
        custom_columns: Optional[List[str]] = None,
    ) -> str:
        """
        Render the full alert list with headers and rows.

        Args:
            alerts: List of all alerts
            visible_indices: Indices of alerts that should be shown
            selected_index: Currently selected alert index
            custom_columns: Optional list of custom column names to display

        Returns:
            Formatted text for the alert list
        """
        if not visible_indices:
            return "\n  No alerts to display"

        lines = []

        # Build header
        header_parts = ["", "Alert Name", "Status", "Severity", "🤖 AI Status"]

        # Add custom AI columns if configured - with AI emoji
        columns_to_show = []
        if custom_columns is None and self.alert_config.enrichment.ai_custom_columns:
            columns_to_show = list(
                self.alert_config.enrichment.ai_custom_columns.keys()
            )[:2]
            for col in columns_to_show:
                col_display = " ".join(word.capitalize() for word in col.split("_"))
                header_parts.append(f"🤖 {col_display}")
        elif custom_columns:
            columns_to_show = custom_columns
            for col in columns_to_show:
                col_display = " ".join(word.capitalize() for word in col.split("_"))
                header_parts.append(f"🤖 {col_display}")

        # Format header
        header = self._format_row(header_parts, is_header=True)
        lines.append(header)
        lines.append("─" * min(len(header), 200))  # Use lighter line

        # Add visible alerts only
        visible_alerts = [alerts[i] for i in visible_indices]
        for alert, original_index in zip(visible_alerts, visible_indices):
            is_selected = original_index == selected_index

            # Build row
            row_parts = self.formatter.build_alert_row(
                alert, is_selected, columns_to_show
            )
            row = self._format_row(row_parts, is_header=False)
            lines.append(row)

        return "\n".join(lines)

    def render_with_filter(
        self,
        all_alerts: List["EnrichedAlert"],
        visible_alerts: List["EnrichedAlert"],
        visible_indices: List[int],
        selected_index: int,
        filter_text: str,
    ) -> str:
        """
        Render alert list with filtering applied.

        Args:
            all_alerts: Complete list of all alerts
            visible_alerts: Filtered list of visible alerts
            visible_indices: Original indices of visible alerts
            selected_index: Currently selected alert index
            filter_text: Active filter text

        Returns:
            Formatted text for the filtered alert list
        """
        if not visible_alerts and filter_text:
            return self.render_no_matches(filter_text)

        # Get custom columns if configured
        custom_columns = None
        if self.alert_config.enrichment.ai_custom_columns:
            custom_columns = list(
                self.alert_config.enrichment.ai_custom_columns.keys()
            )[:2]

        return self.render_alert_list(
            all_alerts, visible_indices, selected_index, custom_columns
        )

    def _format_row(self, parts: List[str], is_header: bool = False) -> str:
        """
        Format a row with proper column widths.

        Args:
            parts: List of column values
            is_header: Whether this is a header row

        Returns:
            Formatted row string
        """
        if is_header:
            widths = [1, 28, 11, 12, 15]  # Column widths
        else:
            widths = [1, 28, 11, 12, 15]  # Column widths

        # Add widths for custom columns
        while len(widths) < len(parts):
            widths.append(25)  # More space for custom columns

        # Format each part with its width
        formatted_parts = []
        for part, width in zip(parts, widths):
            if len(part) > width:
                part = part[: width - 3] + "..."
            formatted_parts.append(part.ljust(width))

        return " ".join(formatted_parts)

    def mark_initial_load_complete(self):
        """Mark that the initial load is complete."""
        self.initial_load_complete = True

    def calculate_cursor_position(self, selected_index: int, text: str) -> int:
        """
        Calculate the cursor position for a given selected index.

        Args:
            selected_index: The selected alert index (in visible list)
            text: The full rendered text

        Returns:
            Cursor position in the text (character position)
        """
        if not text:
            return 0

        # Find the line number for the selected index
        # Account for header lines (2 lines for header + separator)
        header_lines = 2
        target_line = header_lines + selected_index

        # Normalize newlines for consistent handling
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized_text.split("\n")

        if target_line >= len(lines):
            return 0

        # Calculate character position (prompt_toolkit uses character positions)
        position = 0
        for i in range(min(target_line, len(lines))):
            position += len(lines[i]) + 1  # +1 for newline character

        # Ensure we don't go past the end of text
        return min(position, len(normalized_text))
