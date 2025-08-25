"""
Interactive alert view using prompt_toolkit for real-time navigation.
Left pane: Alert list with status and columns
Right pane: Inspector for selected alert details
Bottom: Console output with captured logs
"""

import json
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, VSplit
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.styles import Style
from holmes.alert_proxy.alert_inspector import AlertInspector
from holmes.alert_proxy.alert_list_renderer import AlertListRenderer
from holmes.alert_proxy.console_logger import ConsoleLogger, LogInterceptor
from holmes.alert_proxy.keybindings import KeybindingsManager
from holmes.alert_proxy.search_manager import SearchManager
from holmes.alert_proxy.ui_components import StatusBar, CollapsedPaneIndicators
from holmes.alert_proxy.models import EnrichmentStatus

if TYPE_CHECKING:
    from holmes.alert_proxy.models import InteractiveModeConfig

# UI Constants
CONSOLE_MAX_LINES = 1000
INSPECTOR_WIDTH = 60
CONSOLE_HEIGHT = 12
PAGE_SIZE = 10
BOTTOM_DETECTION_OFFSET = 10
REFRESH_POLL_INTERVAL = 0.1


class AlertUIView:
    """View for alerts with inspector and console output."""

    def __init__(self, alert_config: "InteractiveModeConfig"):
        self.alert_config = alert_config
        self.model = None  # Will be set by the model
        self._selected_index = 0  # View owns the selection state
        self._focused_pane = 0  # 0=list, 1=inspector, 2=console
        self.inspector_collapsed = False
        self.console_collapsed = False
        self.initial_load_complete = False  # Track if we've done first fetch
        self.refresh_requested = threading.Event()  # For model to signal refresh
        self.model_error: Optional[str] = None  # Store model connectivity error

        # Initialize helper modules
        self.search_manager = SearchManager()
        self.list_renderer = AlertListRenderer(alert_config)
        self.inspector = AlertInspector()
        self.console = ConsoleLogger(max_lines=CONSOLE_MAX_LINES)
        self.console.set_update_callback(self._update_console)

        # Initialize status bar
        self.status_bar = StatusBar(
            get_alerts=lambda: self.model.get_alerts_for_display()
            if self.model
            else [],
            get_status=lambda: self.processing_status,
            get_focused_pane=lambda: self.focused_pane,
        )
        self.status_bar.alert_config = alert_config

        # Create text areas for each pane
        self.list_area = TextArea(
            text="\n Loading alerts...",
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
        )
        # Disable cursor in inspector (read-only)

        self.console_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=True,
        )
        # Enable cursor for navigation in console
        # Enable cursor in console for visibility

        # Create the application
        self.app = self._create_application()
        self.app_thread = None
        self.stop_event = threading.Event()
        self.refresh_thread = None

    @property
    def selected_index(self) -> int:
        """Get selected index (view state, not model state)."""
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value: int) -> None:
        """Set selected index with validation."""
        if self.model:
            alerts = self.model.get_alerts_for_display()
            alert_count = len(alerts) if alerts else 0
            if alert_count == 0:
                self._selected_index = 0
            else:
                self._selected_index = max(0, min(value, alert_count - 1))
        else:
            self._selected_index = 0

    @property
    def focused_pane(self) -> int:
        """Get current focused pane."""
        return self._focused_pane

    @focused_pane.setter
    def focused_pane(self, value: int) -> None:
        """Set focused pane with validation."""
        # Prevent setting to collapsed pane, fall back to list
        if value == 1 and self.inspector_collapsed:
            self._focused_pane = 0
        elif value == 2 and self.console_collapsed:
            self._focused_pane = 0
        else:
            self._focused_pane = value

    @property
    def processing_status(self) -> str:
        """Derive processing status from current state."""
        # Check search state first
        search_status = self.search_manager.get_search_status()
        if search_status:
            return search_status

        # Default status based on alerts
        if self.model:
            alerts = self.model.get_alerts_for_display()
            if alerts:
                return f"Showing {len(alerts)} alerts"
            else:
                return "No active alerts"
        return "Loading..."

    def _create_application(self) -> Application:
        """Create the prompt_toolkit application."""
        # Create keybinding manager
        kb_manager = KeybindingsManager()
        kb_manager.view = self  # type: ignore  # Pass reference to view for search state checking

        # Add navigation bindings
        kb_manager.add_navigation_bindings(
            move_up=self._move_up,
            move_down=self._move_down,
            page_up=self._page_up,
            page_down=self._page_down,
            switch_pane=self._switch_pane,
            focus_list=lambda: self._focus_pane(0),  # Focus alert list (pane 0)
        )

        # Add UI toggle bindings
        kb_manager.add_ui_bindings(
            toggle_inspector=self._toggle_inspector,
            toggle_console=self._toggle_console,
        )

        # Add action bindings
        kb_manager.add_action_bindings(
            refresh=self._refresh_alerts,
            enrich_current=lambda: self._enrich_alerts(all_alerts=False),
            enrich_all=lambda: self._enrich_alerts(all_alerts=True),
            copy_current=self._copy_alert,
            export_current=self._export_alert,
        )

        # Add search bindings
        kb_manager.add_search_bindings(
            start_search=self._start_search,
            cancel_search=self._cancel_search,
        )

        # Add help binding
        kb_manager.add_help_binding(self._show_help)

        # Add quit binding
        kb_manager.add_quit_binding(self._quit_app)

        # Get the configured keybindings
        kb = kb_manager.get_bindings()

        # Add context-aware go-to-top and go-to-bottom shortcuts
        @kb.add("g", "g", filter=kb_manager.not_searching_filter)
        def _go_top(event):
            """Go to top - context aware."""
            self._go_to_top()

        @kb.add("G", filter=kb_manager.not_searching_filter)
        def _go_bottom(event):
            """Go to bottom - context aware."""
            self._go_to_bottom()

        # Create a separate KeyBindings instance for search mode that takes priority
        search_kb = KeyBindings()

        # Import Condition for creating filters
        from prompt_toolkit.filters import Condition

        # Create filter conditions
        is_searching = Condition(lambda: self.search_manager.is_active())
        not_searching = Condition(lambda: not self.search_manager.is_active())

        # Handle text input during search - register with higher priority
        @search_kb.add("<any>", filter=is_searching)
        def _(event):
            """Handle character input during search."""
            char = event.data
            if char and char.isprintable():
                self.search_manager.add_character(char)
                self._update_search()

        # Handle backspace during search
        @search_kb.add("backspace", filter=is_searching)
        def _(event):
            """Handle backspace during search."""
            self.search_manager.remove_character()
            self._update_search()

        # Handle Enter during search - apply filter and exit search mode
        @search_kb.add("enter", filter=is_searching)
        def _(event):
            """Apply search filter and exit search mode."""
            self._apply_search_filter()

        # Add Tab key for switching panes (only when not searching)
        @kb.add("tab", filter=not_searching)
        def _(event):
            """Switch to next pane."""
            self._switch_pane()

        # Merge the search keybindings with higher priority
        from prompt_toolkit.key_binding import merge_key_bindings

        kb = merge_key_bindings([search_kb, kb])  # type: ignore

        # Create layout
        layout = self._create_layout()

        # Create style with better colors
        style = Style.from_dict(
            {
                "frame.border": "fg:#808080",
                "frame.title": "bold",
                "status": "reverse",
                "selected": "reverse",
                "firing": "fg:#ff0000 bold",
                "resolved": "fg:#00ff00",
                "critical": "fg:#ff0000",
                "warning": "fg:#ffaa00",
                "info": "fg:#0088ff",
            }
        )

        return Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True,
            mouse_support=False,  # Disabled - interferes with terminal text selection
        )

    def _create_layout(self):
        """Create the application layout."""
        # Alert list (left pane) with title showing shortcut
        list_frame = Frame(
            self.list_area,
            title="Alert List [l to focus]",
            style="bold" if self.focused_pane == 0 else "",
        )

        # Inspector (right pane) with dynamic title
        if not self.inspector_collapsed:
            inspector_frame = Frame(
                self.inspector_area,
                title="Alert Inspector [i to toggle]",
                width=INSPECTOR_WIDTH,  # Fixed width for inspector
                style="bold" if self.focused_pane == 1 else "",
            )
            # Main content with separator
            main_content = VSplit(
                [
                    list_frame,
                    Window(width=1),  # Separator
                    inspector_frame,
                ]
            )
        else:
            # Collapsed inspector indicator
            collapsed_inspector = CollapsedPaneIndicators.get_collapsed_inspector()
            main_content = VSplit(
                [
                    list_frame,
                    Window(width=1),  # Separator
                    collapsed_inspector,
                ]
            )

        # Console (bottom pane) with dynamic title
        if not self.console_collapsed:
            console_frame = Frame(
                self.console_area,
                title="Console Output [o to toggle]",
                height=CONSOLE_HEIGHT,
                style="bold" if self.focused_pane == 2 else "",
            )
            console_component = console_frame
        else:
            # Collapsed console indicator
            console_component = CollapsedPaneIndicators.get_collapsed_console()

        # Build full layout with header and footer
        root_container = HSplit(
            [
                self.status_bar.header,  # Header at top
                main_content,  # Main content
                console_component,  # Console (may be collapsed)
                self.status_bar.footer,  # Footer at bottom
            ]
        )

        return Layout(root_container)

    # Helper methods for safe index handling
    def _get_visible_or_all_indices(self, alerts) -> tuple:
        """Get visible indices from filter, or all indices if no matches."""
        if not alerts:
            return ([], [])

        visible_alerts, visible_indices = self.search_manager.get_filtered_alerts(
            alerts
        )
        if not visible_indices and alerts:
            # No matches but alerts exist - return all
            return (alerts, list(range(len(alerts))))
        return (visible_alerts, visible_indices)

    def _alert_list_navigate(self, direction: str, amount: int = 1):
        """Generic alert list navigation helper.

        Args:
            direction: 'up', 'down', 'page_up', 'page_down', 'top', 'bottom'
            amount: Number of items to move (1 for single, PAGE_SIZE for page)
        """
        if not self.model:
            return False

        alerts = self.model.get_alerts_for_display()
        if not alerts:
            return False

        _, visible_indices = self._get_visible_or_all_indices(alerts)
        if not visible_indices:
            return False

        # Find current position in visible list
        if self.selected_index in visible_indices:
            current_pos = visible_indices.index(self.selected_index)
        else:
            # Not in visible list, jump to first
            self.selected_index = visible_indices[0]
            self._refresh_ui()
            return True

        # Calculate new position based on direction
        if direction == "up":
            new_pos = max(0, current_pos - amount)
        elif direction == "down":
            new_pos = min(len(visible_indices) - 1, current_pos + amount)
        elif direction == "page_up":
            new_pos = max(0, current_pos - PAGE_SIZE)
        elif direction == "page_down":
            new_pos = min(len(visible_indices) - 1, current_pos + PAGE_SIZE)
        elif direction == "top":
            new_pos = 0
        elif direction == "bottom":
            new_pos = len(visible_indices) - 1
        else:
            return False

        # Update selection if position changed
        if new_pos != current_pos:
            self.selected_index = visible_indices[new_pos]
            self._refresh_ui()
            return True

        return False

    def _console_navigate(self, direction: str, amount: int = 1):
        """Generic console navigation helper.

        Args:
            direction: 'up', 'down', 'top', 'bottom', 'page_up', 'page_down'
            amount: Number of lines to move (for line movements) or pages
        """
        buffer = self.console_area.buffer
        text = buffer.text
        pos = buffer.cursor_position

        if direction == "top":
            buffer.cursor_position = 0
        elif direction == "bottom":
            buffer.cursor_position = len(text)
        elif direction == "up":
            # Simple line-by-line up movement
            for _ in range(amount):
                # Find start of current line
                line_start = text.rfind("\n", 0, pos)
                if line_start == -1:
                    # We're on the first line
                    buffer.cursor_position = 0
                    break
                else:
                    # Move to previous line
                    pos = line_start - 1 if line_start > 0 else 0
                    # Find start of that line
                    prev_line_start = text.rfind("\n", 0, pos)
                    pos = prev_line_start + 1 if prev_line_start != -1 else 0
            buffer.cursor_position = pos
        elif direction == "down":
            # Simple line-by-line down movement
            for _ in range(amount):
                # Find next newline
                next_newline = text.find("\n", pos)
                if next_newline != -1 and next_newline < len(text) - 1:
                    # Move to start of next line
                    pos = next_newline + 1
                else:
                    # No more lines
                    break
            buffer.cursor_position = pos
        elif direction == "page_up":
            # Move up by page
            for _ in range(PAGE_SIZE):
                line_start = text.rfind("\n", 0, pos)
                if line_start == -1:
                    buffer.cursor_position = 0
                    break
                else:
                    pos = line_start - 1 if line_start > 0 else 0
                    prev_line_start = text.rfind("\n", 0, pos)
                    pos = prev_line_start + 1 if prev_line_start != -1 else 0
            buffer.cursor_position = pos
        elif direction == "page_down":
            # Move down by page
            for _ in range(PAGE_SIZE):
                next_newline = text.find("\n", pos)
                if next_newline != -1 and next_newline < len(text) - 1:
                    pos = next_newline + 1
                else:
                    break
            buffer.cursor_position = pos

        self.app.invalidate()

    # Navigation methods
    def _move_up(self):
        """Move up - context aware based on focused pane."""
        if self.focused_pane == 0:  # Alert list
            self._alert_list_navigate("up")
        elif self.focused_pane == 1 and not self.inspector_collapsed:  # Inspector
            # Scroll inspector up
            self.inspector_area.buffer.cursor_up()
        elif self.focused_pane == 2:  # Console
            self._console_navigate("up")

    def _move_down(self):
        """Move down - context aware based on focused pane."""
        if self.focused_pane == 0:  # Alert list
            self._alert_list_navigate("down")
        elif self.focused_pane == 1 and not self.inspector_collapsed:  # Inspector
            # Scroll inspector down
            self.inspector_area.buffer.cursor_down()
        elif self.focused_pane == 2:  # Console
            self._console_navigate("down")

    def _page_up(self):
        """Page up - context aware based on focused pane."""
        if self.focused_pane == 0:  # Alert list
            self._alert_list_navigate("page_up")
        elif self.focused_pane == 1 and not self.inspector_collapsed:  # Inspector
            # Scroll inspector up by page
            self.inspector_area.buffer.cursor_up(count=PAGE_SIZE)
        elif self.focused_pane == 2:  # Console
            self._console_navigate("page_up")

    def _page_down(self):
        """Page down - context aware based on focused pane."""
        if self.focused_pane == 0:  # Alert list
            self._alert_list_navigate("page_down")
        elif self.focused_pane == 1 and not self.inspector_collapsed:  # Inspector
            # Scroll inspector down by page
            self.inspector_area.buffer.cursor_down(count=PAGE_SIZE)
        elif self.focused_pane == 2:  # Console
            self._console_navigate("page_down")

    def _go_to_top(self):
        """Go to top - context aware based on focused pane."""
        if self.focused_pane == 0:  # Alert list
            self._alert_list_navigate("top")
        elif self.focused_pane == 1 and not self.inspector_collapsed:  # Inspector
            # Go to top of inspector
            self.inspector_area.buffer.cursor_position = 0
        elif self.focused_pane == 2:  # Console
            self._console_navigate("top")

    def _go_to_bottom(self):
        """Go to bottom - context aware based on focused pane."""
        if self.focused_pane == 0:  # Alert list
            self._alert_list_navigate("bottom")
        elif self.focused_pane == 1 and not self.inspector_collapsed:  # Inspector
            # Go to bottom of inspector
            self.inspector_area.buffer.cursor_position = len(self.inspector_area.text)
        elif self.focused_pane == 2:  # Console
            self._console_navigate("bottom")

    # Pane management
    def _focus_pane(self, pane: int):
        """Focus a specific pane."""
        self.focused_pane = pane
        self._update_focus()

    def _switch_pane(self):
        """Switch to next pane in cycle, skipping collapsed panes."""
        available_panes = [0]  # Alert list is always available
        if not self.inspector_collapsed:
            available_panes.append(1)
        if not self.console_collapsed:
            available_panes.append(2)

        current_idx = available_panes.index(self.focused_pane)
        next_idx = (current_idx + 1) % len(available_panes)
        self.focused_pane = available_panes[next_idx]
        self._update_focus()

    def _sync_cursor_to_selection(self):
        """Sync TextArea cursor position to match the selected alert index."""
        if not self.list_area.text:
            return

        # Get the filtered view to find position in displayed list
        if self.model:
            alerts = self.model.get_alerts_for_display()
            if alerts:
                _, visible_indices = self.search_manager.get_filtered_alerts(alerts)
                # Find position of selected_index in the visible list
                try:
                    display_position = visible_indices.index(self.selected_index)
                except ValueError:
                    display_position = 0
            else:
                display_position = 0
        else:
            display_position = 0

        position = self.list_renderer.calculate_cursor_position(
            display_position, self.list_area.text
        )
        self.list_area.buffer.cursor_position = position

    def _update_focus(self):
        """Update focus to match focused_pane and refresh display."""
        if self.focused_pane == 0:
            self.app.layout.focus(self.list_area)
            # Sync cursor position with selected index
            self._sync_cursor_to_selection()
        elif self.focused_pane == 1:
            self.app.layout.focus(self.inspector_area)
        elif self.focused_pane == 2:
            self.app.layout.focus(self.console_area)

        # Always invalidate after focus change
        self.app.invalidate()

    def _toggle_inspector(self):
        """Toggle inspector pane."""
        self.inspector_collapsed = not self.inspector_collapsed
        # If collapsing and inspector was focused, move focus to list
        if self.inspector_collapsed and self.focused_pane == 1:
            self.focused_pane = 0
        self.app.layout = self._create_layout()
        self._update_focus()

    def _toggle_console(self):
        """Toggle console pane."""
        self.console_collapsed = not self.console_collapsed
        # If collapsing and console was focused, move focus to list
        if self.console_collapsed and self.focused_pane == 2:
            self.focused_pane = 0
        self.app.layout = self._create_layout()
        self._update_focus()

    # Single UI update path
    def _refresh_ui(self, update_inspector=True, sync_cursor=True):
        """Single method for all UI updates to ensure consistency."""

        # logger = logging.getLogger(__name__)
        # logging.info(
        #     f"[UI] _refresh_ui called (update_inspector={update_inspector}, sync_cursor={sync_cursor})"
        # )

        # Update components
        self._update_list()
        if update_inspector:
            self._update_inspector()

        # Sync cursor position if needed (but not during enrichment)
        if sync_cursor and self.focused_pane == 0:
            self._sync_cursor_to_selection()

        # Single invalidate at the end
        self.app.invalidate()

    # Search functionality
    def _start_search(self):
        """Start search mode."""
        if not self.model:
            return
        alerts = self.model.get_alerts_for_display()
        if not alerts:
            return

        self.search_manager.start_search()
        self._update_search()  # Update matches immediately
        self.app.invalidate()

    def _cancel_search(self):
        """Cancel search and clear all filters."""
        self.search_manager.cancel_search()

        # Single UI refresh handles everything
        self._refresh_ui(update_inspector=True)

        # Ensure layout is reset for immediate visual update
        if self.app.layout:
            self.app.layout.reset()

    def _apply_search_filter(self):
        """Apply search as a persistent filter and exit search mode."""
        status, has_filter = self.search_manager.apply_filter()
        self._refresh_ui()

    def _update_search(self):
        """Update search results based on current query."""
        if not self.model:
            return

        alerts = self.model.get_alerts_for_display()
        if not alerts:
            return

        query = self.search_manager.search_query
        matches, first_match = self.search_manager.update_search(query, alerts)

        # Jump to first match
        if first_match is not None:
            self.selected_index = first_match

        self._refresh_ui()

    # Actions
    def _refresh_alerts(self):
        """Refresh alert list."""
        self.console.add_line("🔄 Refreshing alerts...")
        # Just trigger refresh - status is derived
        self._refresh_ui()

    def _enrich_alerts(self, all_alerts=False):
        """Request enrichment of alerts via the model."""
        if not self.model:
            self.console.add_line("⚠️ Model not connected")
            return

        alerts = self.model.get_alerts_for_display()
        if not alerts:
            self.console.add_line("⚠️ No alerts available")
            return

        # Determine which alerts to enrich
        if all_alerts:
            from holmes.alert_proxy.models import EnrichmentStatus

            fingerprints_to_enrich = [
                a.original.fingerprint
                for a in alerts
                if a.enrichment_status != EnrichmentStatus.COMPLETED
                and a.original.fingerprint
            ]
            if not fingerprints_to_enrich:
                return
        else:
            # Use selected_index to find the alert (it's an index into the full list)
            try:
                # The selected_index should be valid in the full alert list
                if 0 <= self.selected_index < len(alerts):
                    alert = alerts[self.selected_index]
                else:
                    self.console.add_line("⚠️ Invalid selection")
                    return

                if not alert.original.fingerprint:
                    self.console.add_line("⚠️ Alert has no fingerprint")
                    return

                fingerprints_to_enrich = [alert.original.fingerprint]
            except (IndexError, ValueError) as e:
                self.console.add_line(f"⚠️ Error selecting alert: {e}")
                return

        # Request enrichment from model (the model will log the actual enrichment start)
        self.model.enrich_alerts(fingerprints_to_enrich)

        # Don't sync cursor here - the model will trigger a refresh which will handle it
        # The immediate sync was causing the jump because it happened before the UI text was updated

    def _copy_alert(self):
        """Copy current alert details to clipboard."""
        import pyperclip

        if not self.model:
            return

        alerts = self.model.get_alerts_for_display()
        if not alerts:
            return

        # Get visible alerts
        visible_alerts, visible_indices = self.search_manager.get_filtered_alerts(
            alerts
        )
        if not visible_alerts or self.selected_index >= len(visible_indices):
            return

        # Get the actual alert
        original_index = visible_indices[self.selected_index]
        alert = alerts[original_index]

        # Format alert details
        alert_text = f"""Alert: {alert.original.labels.get('alertname', 'Unknown')}
Status: {alert.original.status}
Severity: {alert.original.labels.get('severity', 'unknown')}
Namespace: {alert.original.labels.get('namespace', 'default')}

Labels:
{json.dumps(alert.original.labels, indent=2)}

Annotations:
{json.dumps(alert.original.annotations, indent=2)}

Started: {alert.original.startsAt}"""

        if alert.enrichment and alert.enrichment_status == EnrichmentStatus.COMPLETED:
            alert_text += f"""

AI Enrichment:
Business Impact: {alert.enrichment.business_impact or 'N/A'}
Root Cause: {alert.enrichment.root_cause or 'N/A'}
Suggested Action: {alert.enrichment.suggested_action or 'N/A'}"""

        try:
            pyperclip.copy(alert_text)
            self.console.add_line("✅ Alert details copied to clipboard")
        except Exception as e:
            self.console.add_line(f"❌ Failed to copy: {e}")

    def _export_alert(self):
        """Export current alert to JSON file."""
        if not self.model:
            return

        alerts = self.model.get_alerts_for_display()
        if not alerts:
            return

        # Get visible alerts
        visible_alerts, visible_indices = self.search_manager.get_filtered_alerts(
            alerts
        )
        if not visible_alerts or self.selected_index >= len(visible_indices):
            return

        # Get the actual alert
        original_index = visible_indices[self.selected_index]
        alert = alerts[original_index]

        # Create filename
        alert_name = alert.original.labels.get("alertname", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alert_{alert_name}_{timestamp}.json"

        # Export data
        export_data = {
            "alert": alert.original.model_dump(mode="json"),
            "enrichment": alert.enrichment.model_dump(mode="json")
            if alert.enrichment
            else None,
            "enrichment_status": alert.enrichment_status.value,
            "enriched_at": alert.enriched_at.isoformat() if alert.enriched_at else None,
        }

        try:
            with open(filename, "w") as f:
                json.dump(export_data, f, indent=2, default=str)
            self.console.add_line(f"✅ Alert exported to {filename}")
        except Exception as e:
            self.console.add_line(f"❌ Failed to export: {e}")

    def _get_help_text(self) -> str:
        """Get help text for keybindings."""
        return """
Navigation:
  ↑/k         Move up
  ↓/j         Move down
  PgUp/Ctrl-B Page up
  PgDn/Ctrl-F Page down
  gg          Go to top
  G           Go to bottom
  Tab         Switch pane

Actions:
  r           Refresh alerts
  e           Enrich current alert
  E           Enrich all alerts
  y           Copy alert details
  x           Export current alert

UI:
  i           Toggle inspector
  o           Toggle console
  /           Search
  Esc         Clear search
  ?/h         Show this help
  q/Ctrl-C    Quit
"""

    def _show_help(self):
        """Show help text."""
        help_text = self._get_help_text()
        self.console.add_header("Help")
        for line in help_text.split("\n"):
            self.console.add_line(line, timestamp=False)
        self._update_console()

    def _quit_app(self, event):
        """Quit the application."""
        # Signal all threads to stop
        self.stop_event.set()
        self.refresh_requested.set()  # Wake up the refresh thread

        # Exit the app
        try:
            event.app.exit()
        except Exception:
            # App might already be exiting, that's fine
            pass

    # Update methods
    def _update_list(self):
        """Update the alert list display."""
        if not self.model:
            self.list_area.text = "\n Model not connected..."
            return

        alerts = self.model.get_alerts_for_display()
        if not alerts:
            self.list_area.text = self.list_renderer.render_empty_state()
            return

        # Get filtered alerts from search manager
        visible_alerts, visible_indices = self.search_manager.get_filtered_alerts(
            alerts
        )

        if not visible_alerts:
            active_filter = self.search_manager.get_current_filter()
            self.list_area.text = self.list_renderer.render_no_matches(active_filter)
            return

        # Ensure selected_index is valid within visible alerts
        if visible_indices and self.selected_index not in visible_indices:
            self.selected_index = visible_indices[0]
        elif not visible_indices:
            self.selected_index = 0

        # Render the alert list
        self.list_area.text = self.list_renderer.render_with_filter(
            alerts,
            visible_alerts,
            visible_indices,
            self.selected_index,
            self.search_manager.get_current_filter(),
        )

    def _update_inspector(self):
        """Update the inspector pane."""

        # logger = logging.getLogger(__name__)

        if not self.model:
            self.inspector_area.text = self.inspector.format_alert_details(None)
            return
        alerts = self.model.get_alerts_for_display()
        if not alerts or self.selected_index >= len(alerts):
            # logging.info(
            #     f"[UI] No alerts to show in inspector (alerts={len(alerts) if alerts else 0}, selected={self.selected_index})"
            # )
            self.inspector_area.text = self.inspector.format_alert_details(None)
        else:
            alert = alerts[self.selected_index]
            # alert_name = alert.original.labels.get("alertname", "Unknown")
            # logging.info(
            #     f"[UI] Updating inspector for alert: {alert_name}, enrichment_status={alert.enrichment_status}, has_enrichment={bool(alert.enrichment)}"
            # )
            # if alert.enrichment:
            #     logging.info(
            #         f"[UI] Enrichment content: business_impact={bool(alert.enrichment.business_impact)}, root_cause={bool(alert.enrichment.root_cause)}, suggested_action={bool(alert.enrichment.suggested_action)}"
            #     )
            self.inspector_area.text = self.inspector.format_alert_details(alert)

    def _update_console(self):
        """Update the console pane."""
        # Remember if we were at the bottom
        was_at_bottom = False
        if (
            self.console_area.buffer.cursor_position
            >= len(self.console_area.text) - BOTTOM_DETECTION_OFFSET
        ):
            was_at_bottom = True

        # Update text
        self.console_area.text = self.console.get_text()

        # Auto-scroll if we were at bottom
        if self.console.get_lines() and was_at_bottom:
            self.console_area.buffer.cursor_position = len(self.console_area.text)

    # Public methods
    def start(self):
        """Start the interactive view in a separate thread."""
        self.app_thread = threading.Thread(target=self.app.run, daemon=True)
        self.app_thread.start()

        # Start refresh monitoring thread
        def monitor_refresh():
            """Monitor for refresh requests from model."""

            # logger = logging.getLogger(__name__)

            while not self.stop_event.is_set():
                if self.refresh_requested.wait(timeout=REFRESH_POLL_INTERVAL):
                    self.refresh_requested.clear()
                    # logging.info("[UI] Processing refresh request from monitor thread")
                    # Refresh UI from polling thread
                    self._refresh_ui()

        self.refresh_thread = threading.Thread(target=monitor_refresh, daemon=True)
        self.refresh_thread.start()

    def stop(self):
        """Stop the interactive view."""
        # Signal all threads to stop
        self.stop_event.set()
        self.refresh_requested.set()  # Wake up the refresh thread

        # Wait for threads to finish
        if self.refresh_thread and self.refresh_thread.is_alive():
            self.refresh_thread.join(timeout=0.5)

        # Exit the app
        try:
            if self.app:
                self.app.exit()
        except Exception:
            # App might already be stopped, that's fine
            pass

        # Wait for app thread
        if self.app_thread and self.app_thread.is_alive():
            self.app_thread.join(timeout=0.5)

    def set_model(self, model):
        """Set the model reference."""
        self.model = model

    def request_refresh(self):
        """Request a UI refresh (called by model when data changes)."""

        # logger = logging.getLogger(__name__)
        # logging.info("[UI] UI refresh requested")
        # Simply set the flag for the monitor thread to handle
        self.refresh_requested.set()

    def update_status(self, status: str):
        """Update status - kept for compatibility but status is now derived."""
        # Status is now derived from state, just trigger UI update
        self.app.invalidate()

    def mark_initial_load_complete(self):
        """Mark that the initial load is complete."""
        self.initial_load_complete = True
        self.list_renderer.mark_initial_load_complete()
        self.app.invalidate()

    def add_console_line(self, message: str):
        """Add a line to the console output."""
        self.console.add_line(message)

    def set_model_error(self, error: str):
        """Set model connectivity error to display in header."""
        self.model_error = error
        self.status_bar.model_error = error
        self.app.invalidate()


# LogInterceptor is re-exported from console_logger
__all__ = ["AlertUIView", "LogInterceptor"]
