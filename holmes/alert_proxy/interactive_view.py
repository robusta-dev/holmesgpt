"""
Interactive alert view using prompt_toolkit for real-time navigation.
Left pane: Alert list with status and columns
Right pane: Inspector for selected alert details
Bottom: Console output with captured logs
"""

import asyncio
import logging
import re
import threading
import time
from datetime import datetime
from typing import List

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, VSplit
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.styles import Style

from holmes.alert_proxy.models import EnrichedAlert, AlertStatus


class AlertInteractiveView:
    """Interactive view for alerts with inspector and console output."""

    def __init__(self, proxy_config):
        self.proxy_config = proxy_config
        self.alerts: List[EnrichedAlert] = []
        self.selected_index = 0
        self.console_lines: List[str] = []
        self.focused_pane = 0  # 0=list, 1=inspector, 2=console
        self.processing_status = "Starting..."
        self.last_update = datetime.utcnow()
        self.inspector_collapsed = False
        self.console_collapsed = False

        # Create text areas for each pane
        # Use regular TextArea for simplicity
        self.list_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=False,
        )

        self.inspector_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=True,
            lexer=None,  # Will use rich for formatting
        )
        # Hide cursor in inspector too
        self.inspector_area.control.show_cursor = False

        self.console_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=True,
        )
        # Hide cursor in console too
        self.console_area.control.show_cursor = False

        # Create the application
        self.app = self._create_application()
        self.app_thread = None
        self.stop_event = threading.Event()

    def _create_application(self) -> Application:
        """Create the prompt_toolkit application."""

        # Create key bindings
        kb = KeyBindings()

        @kb.add("c-l")
        def _(event):
            """Focus alert list pane."""
            if self.focused_pane == 0:
                # Already on list, can't collapse it (main pane)
                pass
            else:
                self.focused_pane = 0
                event.app.layout.focus(self.list_area)
                self._update_headers()
                self._rebuild_layout()

        @kb.add("c-e")
        def _(event):
            """Toggle inspector pane visibility."""
            # Always toggle the collapse state
            self.inspector_collapsed = not self.inspector_collapsed
            self._rebuild_layout()

            # If we're expanding, focus the inspector
            if not self.inspector_collapsed:
                self.focused_pane = 1
                # Focus will be set in _rebuild_layout
            # If collapsing and we were on inspector, focus goes to list (handled in _rebuild_layout)

        @kb.add("c-o")
        def _(event):
            """Toggle console pane visibility."""
            # Always toggle the collapse state
            self.console_collapsed = not self.console_collapsed
            self._rebuild_layout()

            # If we're expanding, focus the console
            if not self.console_collapsed:
                self.focused_pane = 2
                # Focus will be set in _rebuild_layout
            # If collapsing and we were on console, focus goes to list (handled in _rebuild_layout)

        @kb.add("tab")
        def _(event):
            """Cycle through panes."""
            # Find next available pane
            for _ in range(3):  # Max 3 attempts
                self.focused_pane = (self.focused_pane + 1) % 3

                # Skip collapsed panes
                if self.focused_pane == 1 and self.inspector_collapsed:
                    continue
                if self.focused_pane == 2 and self.console_collapsed:
                    continue

                # Focus the pane
                if self.focused_pane == 0:
                    event.app.layout.focus(self.list_area)
                elif self.focused_pane == 1:
                    event.app.layout.focus(self.inspector_area)
                elif self.focused_pane == 2:
                    event.app.layout.focus(self.console_area)
                self._update_headers()
                break
            else:
                # All panes collapsed except list, stay on list
                self.focused_pane = 0
                event.app.layout.focus(self.list_area)
                self._update_headers()

        @kb.add("c-c")
        @kb.add("c-q")
        def _(event):
            """Exit application."""
            self.stop_event.set()
            event.app.exit()

        # Vim-style navigation
        @kb.add("j")
        def _(event):
            """Move down in current pane or select next alert."""
            if self.focused_pane == 0:
                # In list pane, select next alert
                if self.selected_index < len(self.alerts) - 1:
                    self.selected_index += 1
                    self._update_list()
                    self._update_inspector()
            elif self.focused_pane == 1:
                self.inspector_area.buffer.cursor_down()
            elif self.focused_pane == 2:
                self.console_area.buffer.cursor_down()

        @kb.add("down")
        def _(event):
            """Move down in current pane or select next alert."""
            if self.focused_pane == 0:
                # In list pane, select next alert
                if self.selected_index < len(self.alerts) - 1:
                    self.selected_index += 1
                    self._update_list()
                    self._update_inspector()
            elif self.focused_pane == 1:
                self.inspector_area.buffer.cursor_down()
            elif self.focused_pane == 2:
                self.console_area.buffer.cursor_down()

        @kb.add("k")
        def _(event):
            """Move up in current pane or select previous alert."""
            if self.focused_pane == 0:
                # In list pane, select previous alert
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self._update_list()
                    self._update_inspector()
            elif self.focused_pane == 1:
                self.inspector_area.buffer.cursor_up()
            elif self.focused_pane == 2:
                self.console_area.buffer.cursor_up()

        @kb.add("up")
        def _(event):
            """Move up in current pane or select previous alert."""
            if self.focused_pane == 0:
                # In list pane, select previous alert
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self._update_list()
                    self._update_inspector()
            elif self.focused_pane == 1:
                self.inspector_area.buffer.cursor_up()
            elif self.focused_pane == 2:
                self.console_area.buffer.cursor_up()

        @kb.add("h")
        def _(event):
            """Move left in current pane."""
            current_area = [self.list_area, self.inspector_area, self.console_area][
                self.focused_pane
            ]
            current_area.buffer.cursor_left()

        @kb.add("l")
        def _(event):
            """Move right in current pane."""
            current_area = [self.list_area, self.inspector_area, self.console_area][
                self.focused_pane
            ]
            current_area.buffer.cursor_right()

        @kb.add("0")
        def _(event):
            """Move to beginning of line."""
            current_area = [self.list_area, self.inspector_area, self.console_area][
                self.focused_pane
            ]
            # Move to start of current line
            text = current_area.buffer.text
            cursor_pos = current_area.buffer.cursor_position
            line_start = text.rfind("\n", 0, cursor_pos)
            if line_start == -1:
                current_area.buffer.cursor_position = 0
            else:
                current_area.buffer.cursor_position = line_start + 1

        @kb.add("$")
        def _(event):
            """Move to end of line."""
            current_area = [self.list_area, self.inspector_area, self.console_area][
                self.focused_pane
            ]
            # Move to end of current line
            text = current_area.buffer.text
            cursor_pos = current_area.buffer.cursor_position
            line_end = text.find("\n", cursor_pos)
            if line_end == -1:
                current_area.buffer.cursor_position = len(text)
            else:
                current_area.buffer.cursor_position = line_end

        @kb.add("^")
        def _(event):
            """Move to first non-whitespace character of line."""
            current_area = [self.list_area, self.inspector_area, self.console_area][
                self.focused_pane
            ]
            text = current_area.buffer.text
            cursor_pos = current_area.buffer.cursor_position
            # Find start of line
            line_start = text.rfind("\n", 0, cursor_pos)
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            # Find first non-whitespace
            line_end = text.find("\n", line_start)
            if line_end == -1:
                line_end = len(text)
            line_text = text[line_start:line_end]
            stripped = line_text.lstrip()
            if stripped:
                offset = len(line_text) - len(stripped)
                current_area.buffer.cursor_position = line_start + offset

        @kb.add("w")
        def _(event):
            """Move to next word."""
            current_area = [self.list_area, self.inspector_area, self.console_area][
                self.focused_pane
            ]
            text = current_area.buffer.text
            pos = current_area.buffer.cursor_position
            # Skip current word
            while pos < len(text) and text[pos].isalnum():
                pos += 1
            # Skip whitespace
            while pos < len(text) and not text[pos].isalnum():
                pos += 1
            current_area.buffer.cursor_position = pos

        @kb.add("b")
        def _(event):
            """Move to previous word."""
            current_area = [self.list_area, self.inspector_area, self.console_area][
                self.focused_pane
            ]
            text = current_area.buffer.text
            pos = current_area.buffer.cursor_position
            if pos > 0:
                pos -= 1
                # Skip whitespace backward
                while pos > 0 and not text[pos].isalnum():
                    pos -= 1
                # Move to beginning of word
                while pos > 0 and text[pos - 1].isalnum():
                    pos -= 1
            current_area.buffer.cursor_position = pos

        @kb.add("enter")
        def _(event):
            """Open selected alert in inspector."""
            if self.focused_pane == 0 and self.alerts:
                self.focused_pane = 1
                event.app.layout.focus(self.inspector_area)
                self._update_headers()

        @kb.add("g")
        def _(event):
            """Go to beginning of current pane."""
            if self.focused_pane == 0:
                self.selected_index = 0
                self._update_list()
                self._update_inspector()
            else:
                current_area = [self.list_area, self.inspector_area, self.console_area][
                    self.focused_pane
                ]
                current_area.buffer.cursor_position = 0

        @kb.add("G")
        def _(event):
            """Go to end of current pane."""
            if self.focused_pane == 0:
                if self.alerts:
                    self.selected_index = len(self.alerts) - 1
                    self._update_list()
                    self._update_inspector()
            else:
                current_area = [self.list_area, self.inspector_area, self.console_area][
                    self.focused_pane
                ]
                current_area.buffer.cursor_position = len(current_area.buffer.text)

        @kb.add("c-d")
        def _(event):
            """Page down."""
            if self.focused_pane == 0:
                # Jump 5 alerts down
                new_index = min(self.selected_index + 5, len(self.alerts) - 1)
                if new_index != self.selected_index:
                    self.selected_index = new_index
                    self._update_list()
                    self._update_inspector()
            else:
                current_area = [self.list_area, self.inspector_area, self.console_area][
                    self.focused_pane
                ]
                for _ in range(10):
                    current_area.buffer.cursor_down()

        @kb.add("c-u")
        def _(event):
            """Page up."""
            if self.focused_pane == 0:
                # Jump 5 alerts up
                new_index = max(self.selected_index - 5, 0)
                if new_index != self.selected_index:
                    self.selected_index = new_index
                    self._update_list()
                    self._update_inspector()
            else:
                current_area = [self.list_area, self.inspector_area, self.console_area][
                    self.focused_pane
                ]
                for _ in range(10):
                    current_area.buffer.cursor_up()

        @kb.add("r")
        def _(event):
            """Refresh view."""
            self._update_list()
            self._update_inspector()
            self._update_console()

        # Create frames (these will be recreated in _build_layout)
        self.list_frame = None
        self.inspector_frame = None
        self.console_frame = None

        # Create header
        self.header = Window(
            FormattedTextControl(self._get_header_text),
            height=1,
            style="bold fg:#00aa00",
        )

        # Create footer
        self.footer = Window(
            FormattedTextControl(self._get_footer_text),
            height=1,
            style="fg:#888888",
        )

        # Build initial layout
        self._build_layout()
        layout = self._get_layout()

        # Create style
        style = Style.from_dict(
            {
                "frame.border": "fg:#808080",
                "frame.title": "bold",
                "firing": "fg:#ff0000 bold",
                "resolved": "fg:#00ff00",
                "critical": "fg:#ff0000",
                "warning": "fg:#ffaa00",
                "info": "fg:#0088ff",
            }
        )

        # Create application
        app: Application = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True,
            mouse_support=False,  # Disabled - interferes with terminal text selection
        )

        return app

    def _get_header_text(self):
        """Get header text."""
        firing_count = sum(
            1 for a in self.alerts if a.original.status == AlertStatus.FIRING
        )
        resolved_count = len(self.alerts) - firing_count

        status_parts = []
        if firing_count > 0:
            status_parts.append(f"🔥 {firing_count} firing")
        if resolved_count > 0:
            status_parts.append(f"✅ {resolved_count} resolved")

        if status_parts:
            status_str = " • ".join(status_parts)
            return f"🚨 HolmesGPT Alert Proxy  •  {status_str}  •  {self.processing_status}"
        else:
            return f"🚨 HolmesGPT Alert Proxy  •  {self.processing_status}"

    def _build_layout(self):
        """Build the frames based on current collapse state."""
        # Alert list frame (always visible)
        self.list_frame = Frame(self.list_area, title=self._get_list_title())

        # Inspector frame
        if self.inspector_collapsed:
            # Collapsed inspector - create a narrow indicator bar with vertical text
            def get_collapsed_text():
                lines = []
                # Create a visual sidebar indicator
                lines.extend(
                    [
                        "◀",  # Arrow pointing left
                        "━",  # Heavy horizontal line
                        " ",
                        "C",
                        "t",
                        "r",
                        "l",
                        " ",
                        "+",
                        " ",
                        "E",
                        " ",
                        "━",
                        " ",
                        "E",
                        "x",
                        "p",
                        "a",
                        "n",
                        "d",
                        " ",
                        "━",
                    ]
                )
                # Fill remaining with subtle line
                for _ in range(10):
                    lines.append("┊")  # Dotted vertical line
                lines.append("◀")
                return "\n".join(lines)

            self.inspector_frame = Window(
                FormattedTextControl(get_collapsed_text),
                width=1,
                style="fg:#505050",  # Subtle gray, no bold for cleaner look
            )
        else:
            # Expanded case - frame will be created in _get_layout
            self.inspector_frame = None

        # Console frame
        if not self.console_collapsed:
            self.console_frame = Frame(
                self.console_area,
                title=self._get_console_title(),
                height=12,
            )
        else:
            # Collapsed console - create a narrow horizontal indicator bar
            def get_collapsed_console_text():
                return " Console (Ctrl+O to expand) "

            self.console_frame = Window(
                FormattedTextControl(get_collapsed_console_text),
                height=1,
                style="fg:#606060 bold",
            )

    def _get_layout(self):
        """Get the current layout."""
        # Always show both panes, but inspector might be collapsed to a narrow bar
        # Adjust the split ratio - list gets more space
        if not self.inspector_collapsed:
            # When inspector is expanded, give list 65% and inspector 35%
            top_panes = VSplit(
                [
                    self.list_frame,  # Takes available space
                    Window(width=1),  # Separator
                    Frame(
                        self.inspector_area, title=self._get_inspector_title(), width=50
                    ),  # Fixed width inspector
                ],
                padding=0,
            )
        else:
            # When collapsed, use the narrow indicator
            top_panes = VSplit(
                [
                    self.list_frame,
                    Window(width=1),  # Separator
                    self.inspector_frame,  # This is the narrow indicator
                ],
                padding=0,
            )

        # Build the full layout
        components = [self.header]

        # Add spacing
        components.append(Window(height=1, char=" "))

        # Add main content
        components.append(top_panes)

        # Always add console (might be collapsed to single line)
        components.append(Window(height=1, char=" "))
        components.append(self.console_frame)

        # Add footer
        components.append(self.footer)

        return Layout(HSplit(components))

    def _rebuild_layout(self):
        """Rebuild the layout when panes are collapsed/expanded."""
        self._build_layout()
        new_layout = self._get_layout()

        if self.app:
            self.app.layout = new_layout

            # Restore focus to the appropriate area
            # If a pane is collapsed and was focused, move focus to list
            if self.focused_pane == 0:
                self.app.layout.focus(self.list_area)
            elif self.focused_pane == 1:
                if not self.inspector_collapsed:
                    self.app.layout.focus(self.inspector_area)
                else:
                    # Inspector collapsed, move focus to list
                    self.focused_pane = 0
                    self.app.layout.focus(self.list_area)
            elif self.focused_pane == 2:
                if not self.console_collapsed:
                    self.app.layout.focus(self.console_area)
                else:
                    # Console collapsed, move focus to list
                    self.focused_pane = 0
                    self.app.layout.focus(self.list_area)

            self._update_headers()
            self.app.invalidate()

    def _get_list_title(self):
        """Get title for list frame."""
        return "Alert List [Ctrl+L]"

    def _get_inspector_title(self):
        """Get title for inspector frame."""
        if self.inspector_collapsed:
            return "[Collapsed - Ctrl+E to expand]"
        return "Alert Inspector [Ctrl+E to hide]"

    def _get_console_title(self):
        """Get title for console frame."""
        if self.console_collapsed:
            return "Console [Collapsed - Ctrl+O to expand]"
        return "Console Output [Ctrl+O to hide]"

    def _get_footer_text(self):
        """Get footer text."""
        shortcuts = []

        # Show collapse state indicators (only for inspector, console has its own bar)
        if self.inspector_collapsed:
            shortcuts.append("Inspector (Ctrl+E)")

        # Context-specific shortcuts
        if self.focused_pane == 0:
            shortcuts.extend(["j/k: select", "0/$: line start/end", "Enter: inspect"])
        elif self.focused_pane == 1 and not self.inspector_collapsed:
            shortcuts.extend(["j/k: scroll", "0/$: line", "w/b: word", "Ctrl+E: hide"])
        elif self.focused_pane == 2 and not self.console_collapsed:
            shortcuts.extend(["j/k: scroll", "0/$: line", "w/b: word", "Ctrl+O: hide"])

        # Add enrichment status
        if self.proxy_config.enable_enrichment and self.alerts:
            enriched_count = sum(1 for a in self.alerts if a.enrichment)
            if enriched_count > 0:
                shortcuts.append(f"AI: {enriched_count}/{len(self.alerts)}")

        shortcuts.append("Tab: cycle")
        shortcuts.append("Ctrl+Q: quit")

        return " • ".join(shortcuts)

    def _update_headers(self):
        """Update frame titles to show focus."""
        # Update titles
        if self.list_frame and hasattr(self.list_frame, "title"):
            self.list_frame.title = self._get_list_title()
            self.list_frame.style = "bold" if self.focused_pane == 0 else ""

        if self.inspector_frame and hasattr(self.inspector_frame, "title"):
            self.inspector_frame.title = self._get_inspector_title()
            self.inspector_frame.style = "bold" if self.focused_pane == 1 else ""

        if self.console_frame and hasattr(self.console_frame, "title"):
            self.console_frame.title = self._get_console_title()
            self.console_frame.style = "bold" if self.focused_pane == 2 else ""

        if self.app:
            self.app.invalidate()

    def _update_list(self):
        """Update alert list pane."""
        # Save current scroll position (not used currently, but kept for future)
        # try:
        #     saved_position = self.list_area.buffer.cursor_position
        # except Exception:
        #     saved_position = 0

        if not self.alerts:
            self.list_area.text = "\n  No alerts yet...\n\n  Alerts will appear here as they are received."
            return

        # Debug: ensure selected_index is valid
        if self.selected_index >= len(self.alerts):
            self.selected_index = 0

        lines = []

        # Build header row
        header_parts = [
            "",
            "Alert",
            "Status",
            "Severity",
            "AI",
        ]  # First column is for selector

        # No common label columns - keep it simple

        # Add custom AI columns if configured
        custom_columns = []
        if self.proxy_config.ai_custom_columns:
            for col in self.proxy_config.ai_custom_columns[:2]:  # Show max 2 in list
                col_display = " ".join(word.capitalize() for word in col.split("_"))
                header_parts.append(col_display)
                custom_columns.append(col)

        # Format header with fixed widths
        header = self._format_row(header_parts, is_header=True)
        lines.append(header)
        lines.append("─" * len(header))  # Match header length

        # Add alerts
        for i, alert in enumerate(self.alerts):
            # Determine if this row is selected
            is_selected = i == self.selected_index

            # Build row data
            row_parts = []

            # Selection indicator - ALWAYS add it
            selector = "▶" if is_selected else " "
            row_parts.append(selector)

            # Alert name (truncated if needed)
            alert_name = alert.original.labels.get("alertname", "Unknown")
            if len(alert_name) > 25:
                alert_name = alert_name[:22] + "..."
            row_parts.append(alert_name)

            # Status
            if alert.original.status == AlertStatus.FIRING:
                row_parts.append("🔥 FIRING")
            else:
                row_parts.append("✅ RESOLVED")

            # Severity
            severity = alert.original.labels.get("severity", "unknown").lower()
            severity_icons = {
                "critical": "🔴",
                "warning": "🟡",
                "info": "🔵",
            }
            row_parts.append(f"{severity_icons.get(severity, '⚪')} {severity}")

            # AI Enrichment status
            enrichment_status = getattr(alert, "enrichment_status", "unknown")
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "skipped": "⊘",
            }.get(enrichment_status, "❓")
            row_parts.append(f"{status_icon} {enrichment_status}")

            # Add custom column values
            for col in custom_columns:
                if alert.enrichment and alert.enrichment.enrichment_metadata:
                    value = alert.enrichment.enrichment_metadata.get(col, "-")
                    if value and len(str(value)) > 15:
                        value = str(value)[:12] + "..."
                    row_parts.append(str(value) if value else "-")
                else:
                    row_parts.append("-")

            # Format row
            row = self._format_row(row_parts, is_selected=is_selected)
            lines.append(row)

        # Join lines and set text
        full_text = "\n".join(lines)
        self.list_area.text = full_text

        # Debug: Log first line to see if selector is there
        if lines and len(lines) > 2:
            first_data_line = lines[2] if len(lines) > 2 else ""
            if first_data_line and first_data_line[0] == "▶":
                pass  # Selector is present in the text

        # Move cursor to the selected line
        try:
            if self.selected_index < len(self.alerts):
                # Calculate line position (header + separator + selected index)
                line_num = 2 + self.selected_index
                # Find the position in text for this line
                lines_before = lines[:line_num] if line_num < len(lines) else lines
                cursor_pos = sum(
                    len(line) + 1 for line in lines_before
                )  # +1 for newline
                self.list_area.buffer.cursor_position = min(cursor_pos, len(full_text))
        except Exception:
            # If there's an issue, just ignore
            pass

    def _format_row(
        self, parts: List[str], is_header: bool = False, is_selected: bool = False
    ) -> str:
        """Format a row with fixed column widths."""
        widths = [2, 25, 10, 12, 15, 30, 30]  # Shorter alert name, tighter columns

        formatted_parts = []
        for i, part in enumerate(parts):
            if i < len(widths):
                # Truncate or pad to fit width
                width = widths[i]
                if len(part) > width:
                    part = part[: width - 1] + "…"
                formatted_parts.append(part.ljust(width))
            else:
                formatted_parts.append(part)

        row = "|".join(formatted_parts)  # Use | separator for tighter spacing

        # Don't use [selected] tags - just return the row
        # Selection is shown with the ▶ indicator
        return row

    def _update_inspector(self):
        """Update inspector pane with selected alert details."""
        if not self.alerts or self.selected_index >= len(self.alerts):
            self.inspector_area.text = "\n  Select an alert to inspect its details..."
            return

        alert = self.alerts[self.selected_index]
        lines = []

        # Alert name and status
        # Inspector width is 50, so headers should be 48 chars (50 - 2 for borders)
        lines.append("╔══ Alert Details ═════════════════════════╗")
        lines.append("")
        lines.append(f"  Alert: {alert.original.labels.get('alertname', 'Unknown')}")

        status_text = (
            "FIRING" if alert.original.status == AlertStatus.FIRING else "RESOLVED"
        )
        lines.append(f"  Status: {status_text}")

        # Timing
        lines.append(
            f"  Started: {alert.original.startsAt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        if alert.original.endsAt:
            lines.append(
                f"  Ended: {alert.original.endsAt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

        # AI Enrichment section - MOVED BEFORE LABELS
        enrichment_status = getattr(alert, "enrichment_status", "unknown")
        if enrichment_status != "pending" and enrichment_status != "unknown":
            # Truncate status if needed to fit in 48 chars
            status_display = (
                enrichment_status[:10]
                if len(enrichment_status) > 10
                else enrichment_status
            )
            header = f"╔══ AI Analysis ({status_display}) "
            padding = "═" * (48 - len(header) - 1)
            lines.append(f"\n{header}{padding}╗")

        if alert.enrichment:
            if not (enrichment_status != "pending" and enrichment_status != "unknown"):
                lines.append("\n╔══ AI ANALYSIS ═══════════════════════════╗")

            # Skip summary - removed

            if alert.enrichment.root_cause:
                lines.append("\n  Root Cause:")
                for line in alert.enrichment.root_cause.split("\n"):
                    lines.append(f"     {line}")

            if alert.enrichment.business_impact:
                lines.append("\n  Business Impact:")
                for line in alert.enrichment.business_impact.split("\n"):
                    lines.append(f"     {line}")

            if alert.enrichment.suggested_action:
                lines.append("\n  Suggested Action:")
                for line in alert.enrichment.suggested_action.split("\n"):
                    lines.append(f"     {line}")

            # Skip priority score - removed

            if alert.enrichment.affected_services:
                lines.append("\n  Affected Services:")
                for service in alert.enrichment.affected_services:
                    lines.append(f"     • {service}")

            # Custom AI columns - HIGHLIGHT THESE
            if alert.enrichment.enrichment_metadata:
                custom_fields = {
                    k: v
                    for k, v in alert.enrichment.enrichment_metadata.items()
                    if k not in ["model", "parse_error", "raw_response", "enriched"]
                }
                if custom_fields:
                    lines.append("\n  ⭐ AI-GENERATED FIELDS ⭐")
                    for key, value in custom_fields.items():
                        display_key = " ".join(
                            word.capitalize() for word in key.split("_")
                        )
                        lines.append(f"     • {display_key}: {value}")

        # Labels section (MOVED AFTER AI ANALYSIS)
        lines.append("\n╔══ Labels ═══════════════════════════════╗")
        for key, value in sorted(alert.original.labels.items()):
            if key not in ["__name__"]:
                # Format label nicely
                lines.append(f"  {key:20s} : {value}")

        # Annotations section
        if alert.original.annotations:
            lines.append("\n╔══ Annotations ═══════════════════════════╗")
            for key, value in sorted(alert.original.annotations.items()):
                # Handle multi-line annotations
                if "\n" in value:
                    lines.append(f"  {key}:")
                    for line in value.split("\n"):
                        lines.append(f"    {line}")
                else:
                    lines.append(f"  {key:20s} : {value}")

        # Metadata section
        if alert.original.fingerprint or alert.original.generatorURL:
            lines.append("\n╔══ Metadata ══════════════════════════════╗")
            if alert.original.fingerprint:
                lines.append(f"  Fingerprint: {alert.original.fingerprint}")
            if alert.original.generatorURL:
                lines.append(f"  Generator URL: {alert.original.generatorURL}")

        self.inspector_area.text = "\n".join(lines)

    def _update_console(self):
        """Update console output pane."""
        # Remember if we were at the bottom before update
        was_at_bottom = False
        if self.console_area.buffer.cursor_position >= len(self.console_area.text) - 10:
            # Consider "at bottom" if within 10 chars of the end
            was_at_bottom = True

        # Show ALL console lines - the TextArea is scrollable
        self.console_area.text = "\n".join(self.console_lines)

        # Only auto-scroll to bottom if we were already at the bottom
        if self.console_lines and was_at_bottom:
            self.console_area.buffer.cursor_position = len(self.console_area.text)

    def update_alerts(self, alerts: List[EnrichedAlert]):
        """Update the alerts list."""
        self.alerts = alerts
        self.last_update = datetime.utcnow()

        # Debug: log the update
        self.add_console_line(f"View received {len(alerts)} alerts for display")

        # Update selected index if needed
        if self.selected_index >= len(self.alerts):
            self.selected_index = max(0, len(self.alerts) - 1)

        self._update_list()
        self._update_inspector()

        if self.app:
            self.app.invalidate()

    def add_console_line(self, line: str):
        """Add a line to console output."""
        # Strip ANSI escape codes
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_line = ansi_escape.sub("", line).strip()

        if clean_line:
            # Add timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.console_lines.append(f"[{timestamp}] {clean_line}")

            # No limit - keep all console lines forever
            # User can scroll through entire history

            self._update_console()

        if self.app:
            self.app.invalidate()

    def update_status(self, status: str):
        """Update processing status."""
        self.processing_status = status
        if self.app:
            self.app.invalidate()

    def start(self):
        """Start the application in a background thread."""

        def run_app():
            try:
                self.app.run()
            except Exception as e:
                import traceback
                import sys

                print(f"Error in interactive view: {e}", file=sys.stderr)
                traceback.print_exc()

        self.app_thread = threading.Thread(target=run_app)
        self.app_thread.daemon = True
        self.app_thread.start()

        # Give the app time to start
        time.sleep(0.5)

    def stop(self):
        """Stop the application."""
        self.stop_event.set()
        if self.app:
            self.app.exit()
        if self.app_thread:
            self.app_thread.join(timeout=2)

    def wait_for_exit(self):
        """Wait for user to exit the application."""
        while not self.stop_event.is_set():
            time.sleep(0.5)


class LogInterceptor(logging.Handler):
    """Intercepts logging output for the interactive view."""

    def __init__(self, view: AlertInteractiveView):
        super().__init__()
        self.view = view

    def emit(self, record):
        try:
            msg = self.format(record)
            if msg and msg.strip():
                self.view.add_console_line(msg)
        except Exception:
            pass


async def run_interactive_view(enriched_alerts: List[EnrichedAlert], proxy_config):
    """Run the interactive alert view."""
    view = AlertInteractiveView(proxy_config)

    # Set up logging interceptor
    log_interceptor = LogInterceptor(view)
    original_handlers = logging.root.handlers.copy()

    for handler in original_handlers:
        logging.root.removeHandler(handler)
    logging.root.addHandler(log_interceptor)

    try:
        # Start the view
        view.start()

        # Update with initial alerts
        view.update_alerts(enriched_alerts)
        view.update_status(f"Showing {len(enriched_alerts)} alerts")

        # Add initial console message
        view.add_console_line(
            "Interactive view started. Use j/k to navigate, Enter to inspect, Tab to switch panes, Ctrl+E to toggle inspector."
        )
        view.add_console_line(f"Loaded {len(enriched_alerts)} alerts from AlertManager")

        # Simulate periodic updates (in real usage, this would be from alert polling)
        update_count = 0
        while not view.stop_event.is_set():
            await asyncio.sleep(5)

            # Update status to show it's live
            update_count += 1
            view.update_status(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

            # Could add new alerts here if polling

    finally:
        # Stop the view
        view.stop()

        # Restore logging handlers
        logging.root.removeHandler(log_interceptor)
        for handler in original_handlers:
            logging.root.addHandler(handler)
