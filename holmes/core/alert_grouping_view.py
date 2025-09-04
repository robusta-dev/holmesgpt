"""
Alert grouping view using prompt_toolkit for real-time keyboard navigation.
"""

import uuid
import logging
import re
import threading
import time
from io import StringIO
from typing import List, Optional, Any

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, VSplit
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.styles import Style

from holmes.core.alert_grouping import AlertGroup, SmartAlertGrouper


class AlertGroupingLiveView:
    """Live view for alert grouping with keyboard navigation using prompt_toolkit."""

    def __init__(self):
        self.groups: List[AlertGroup] = []
        self.current_alert: Optional[str] = None
        self.total_alerts = 0
        self.processed_alerts = 0
        self.log_lines: List[str] = []
        self.console_lines: List[str] = []
        self.focused_pane = 0  # 0=progress, 1=groups, 2=console

        # Create text areas for each pane
        self.progress_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=True,
        )

        self.groups_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=True,
        )

        self.console_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=True,
        )

        # Create the application
        self.app = self._create_application()
        self.app_thread = None
        self.stop_event = threading.Event()

    def _create_application(self) -> Application:
        """Create the prompt_toolkit application."""

        # Create key bindings
        kb = KeyBindings()

        @kb.add("c-p")
        def _(event):
            """Focus progress pane."""
            self.focused_pane = 0
            event.app.layout.focus(self.progress_area)
            self._update_headers()

        @kb.add("c-g")
        def _(event):
            """Focus groups pane."""
            self.focused_pane = 1
            event.app.layout.focus(self.groups_area)
            self._update_headers()

        @kb.add("c-o")
        def _(event):
            """Focus console pane."""
            self.focused_pane = 2
            event.app.layout.focus(self.console_area)
            self._update_headers()

        @kb.add("tab")
        def _(event):
            """Cycle through panes."""
            self.focused_pane = (self.focused_pane + 1) % 3
            if self.focused_pane == 0:
                event.app.layout.focus(self.progress_area)
            elif self.focused_pane == 1:
                event.app.layout.focus(self.groups_area)
            else:
                event.app.layout.focus(self.console_area)
            self._update_headers()

        @kb.add("c-c")
        @kb.add("c-q")
        def _(event):
            """Stop processing."""
            self.stop_event.set()
            event.app.exit()

        # Vim navigation keys
        @kb.add("j")
        def _(event):
            """Move down in current pane."""
            if self.focused_pane == 0:
                self.progress_area.buffer.cursor_down()
            elif self.focused_pane == 1:
                self.groups_area.buffer.cursor_down()
            elif self.focused_pane == 2:
                self.console_area.buffer.cursor_down()

        @kb.add("k")
        def _(event):
            """Move up in current pane."""
            if self.focused_pane == 0:
                self.progress_area.buffer.cursor_up()
            elif self.focused_pane == 1:
                self.groups_area.buffer.cursor_up()
            elif self.focused_pane == 2:
                self.console_area.buffer.cursor_up()

        @kb.add("g")
        def _(event):
            """Go to beginning of current pane."""
            current_area = [self.progress_area, self.groups_area, self.console_area][
                self.focused_pane
            ]
            current_area.buffer.cursor_position = 0

        @kb.add("G")
        def _(event):
            """Go to end of current pane."""
            current_area = [self.progress_area, self.groups_area, self.console_area][
                self.focused_pane
            ]
            current_area.buffer.cursor_position = len(current_area.buffer.text)

        # Page navigation
        @kb.add("c-d")
        def _(event):
            """Half page down."""
            current_area = [self.progress_area, self.groups_area, self.console_area][
                self.focused_pane
            ]
            for _ in range(10):  # About half page
                current_area.buffer.cursor_down()

        @kb.add("c-u")
        def _(event):
            """Half page up."""
            current_area = [self.progress_area, self.groups_area, self.console_area][
                self.focused_pane
            ]
            for _ in range(10):  # About half page
                current_area.buffer.cursor_up()

        # Create frames for each pane with nice borders and shortcuts
        self.progress_frame = Frame(
            self.progress_area, title="📊 Investigation Progress [Ctrl+P]"
        )

        self.groups_frame = Frame(self.groups_area, title="📁 Alert Groups [Ctrl+G]")

        self.console_frame = Frame(
            self.console_area,
            title="🖥️  Console Output [Ctrl+O]",
            height=10,  # Taller console output
        )

        # Create thin header with title
        self.header = Window(
            FormattedTextControl(self._get_header_text),
            height=1,
            style="bold fg:#00aa00",
        )

        # Create footer with instructions
        self.footer = Window(
            FormattedTextControl(self._get_footer_text),
            height=1,
            style="fg:#888888",
        )

        # Create layout with 2 panes on top, console at bottom
        # Use HSplit to stack vertically, VSplit to arrange horizontally
        top_panes = VSplit(
            [
                self.progress_frame,  # Left pane - progress
                Window(width=1),  # Small separator
                self.groups_frame,  # Right pane - groups (wider)
            ],
            padding=0,
        )

        layout = Layout(
            HSplit(
                [
                    self.header,  # Thin header at top
                    Window(height=1),  # Small gap
                    top_panes,  # Two panes side-by-side
                    Window(height=1),  # Small gap
                    self.console_frame,  # Console at bottom (smaller)
                    self.footer,  # Footer with instructions
                ]
            )
        )

        # Create style
        style = Style.from_dict(
            {
                "frame.border": "fg:#808080",
                "frame.title": "bold",
            }
        )

        # Create application
        app: Application = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True,
            mouse_support=True,
        )

        return app

    def _get_header_text(self):
        """Get header text."""
        if self.processed_alerts == 0:
            return (
                f"🔍 Alert Grouping Analysis  •  {self.total_alerts} alerts to process"
            )
        elif self.processed_alerts == self.total_alerts:
            return f"🔍 Alert Grouping Analysis  •  Completed {self.processed_alerts}/{self.total_alerts} alerts"
        else:
            return f"🔍 Alert Grouping Analysis  •  Processing alert {self.processed_alerts} of {self.total_alerts}"

    def _get_footer_text(self):
        """Get footer text."""
        stats = []
        if self.groups:
            total_in_groups = sum(len(g.alerts) for g in self.groups)
            rules_generated = sum(1 for g in self.groups if g.has_rule)
            stats.append(f"Groups: {len(self.groups)}")
            stats.append(f"Alerts grouped: {total_in_groups}")
            if rules_generated > 0:
                stats.append(f"Rules: {rules_generated}")

        # Just show stats and basic navigation hint
        if stats:
            stats_str = " • ".join(stats)
            return f"{stats_str}  |  Tab: cycle panes • j/k: scroll"
        else:
            # No stats yet, just show navigation
            return "Tab: cycle panes • j/k: scroll"

    def _update_headers(self):
        """Update frame titles to show focus."""
        # Update frame titles with keyboard shortcuts, bold the focused one
        if self.focused_pane == 0:
            self.progress_frame.title = "📊 Investigation Progress [Ctrl+P]"
            self.progress_frame.style = "bold"
        else:
            self.progress_frame.title = "📊 Investigation Progress [Ctrl+P]"
            self.progress_frame.style = ""

        if self.focused_pane == 1:
            self.groups_frame.title = "📁 Alert Groups [Ctrl+G]"
            self.groups_frame.style = "bold"
        else:
            self.groups_frame.title = "📁 Alert Groups [Ctrl+G]"
            self.groups_frame.style = ""

        if self.focused_pane == 2:
            self.console_frame.title = "🖥️  Console Output [Ctrl+O]"
            self.console_frame.style = "bold"
        else:
            self.console_frame.title = "🖥️  Console Output [Ctrl+O]"
            self.console_frame.style = ""

        if self.app:
            self.app.invalidate()

    def update_progress(self, log_line: Optional[str] = None):
        """Update progress pane."""
        if log_line:
            self.log_lines.append(log_line)

        # Format progress content without emojis - clean and simple
        content_lines = []
        for line in self.log_lines[-30:]:  # Show last 30 lines
            content_lines.append(line)

        if self.current_alert:
            content_lines.append(f"\nCurrently analyzing: {self.current_alert}")

        self.progress_area.text = "\n".join(content_lines)
        if self.app:
            self.app.invalidate()

    def update_groups(self, groups: Optional[List[AlertGroup]] = None):
        """Update groups pane."""
        if groups is not None:
            self.groups = groups

        if not self.groups:
            self.groups_area.text = "\n  No groups formed yet...\n\n  Groups will appear here as alerts are processed."
        else:
            lines = []
            for i, group in enumerate(self.groups, 1):
                # Severity indicator based on category
                severity_emoji = {
                    "critical": "🔴",
                    "infrastructure": "🟠",
                    "application": "🟡",
                    "database": "🟣",
                    "network": "🔵",
                }.get(group.category, "⚪")

                lines.append(f"\n{severity_emoji} Group {i}: {group.issue_title}")
                lines.append("─" * 50)

                # Show category with color
                lines.append(f"  📂 Category: {group.category}")

                # Show full root cause - no truncation
                lines.append(f"  🔍 Root Cause: {group.root_cause}")

                # Only show rule status if generated
                if group.has_rule:
                    lines.append("  ✅ Rule Generated")

                # Show alerts more compactly
                alert_count = len(group.alerts)
                if alert_count == 1:
                    # For single alert, show it inline without numbering
                    lines.append(f"  🚨 Alert: {group.alerts[0].name}")
                else:
                    # For multiple alerts, show with numbering
                    lines.append(f"  🚨 {alert_count} Alerts:")
                    for j, alert in enumerate(group.alerts[:3], 1):
                        lines.append(f"     {j}. {alert.name}")
                    if alert_count > 3:
                        lines.append(f"     ... +{alert_count - 3} more")

            self.groups_area.text = "\n".join(lines)

        if self.app:
            self.app.invalidate()

    def update_console(self, console_line: Optional[str] = None):
        """Update console output pane."""
        if console_line:
            # Strip ANSI escape codes and clean up the line
            # Remove ANSI escape sequences
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            clean_line = ansi_escape.sub("", console_line).strip()

            if clean_line:
                self.console_lines.append(clean_line)

        # Show last 15 console lines (more lines for taller console)
        self.console_area.text = "\n".join(self.console_lines[-15:])

        if self.app:
            self.app.invalidate()

    def update(
        self,
        groups: Optional[List[AlertGroup]] = None,
        current_alert: Optional[str] = None,
        log_line: Optional[str] = None,
        total_alerts: Optional[int] = None,
        processed_alerts: Optional[int] = None,
        console_line: Optional[str] = None,
    ):
        """Update all view components."""

        if groups is not None:
            self.update_groups(groups)
        if current_alert is not None:
            self.current_alert = current_alert
        if log_line:
            self.update_progress(log_line)
        if total_alerts is not None:
            self.total_alerts = total_alerts
        if processed_alerts is not None:
            self.processed_alerts = processed_alerts
        if console_line:
            self.update_console(console_line)

        # Refresh the app
        if self.app:
            self.app.invalidate()

    def start(self):
        """Start the application in a background thread."""

        def run_app():
            try:
                self.app.run()
            except Exception:
                pass  # App was stopped

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


class LogInterceptor(logging.Handler):
    """Intercepts logging output during live view."""

    def __init__(self, view):
        super().__init__()
        self.view = view

    def emit(self, record):
        try:
            msg = self.format(record)
            if msg and msg.strip():
                self.view.update(console_line=msg)
        except Exception:
            pass


class PromptToolkitAlertGrouper(SmartAlertGrouper):
    """Alert grouper with prompt_toolkit live view."""

    def __init__(self, ai, console, verify_first_n: int = 5):
        super().__init__(ai, console, verify_first_n)
        self.view: Optional[AlertGroupingLiveView] = None
        self.investigation_buffer = StringIO()
        self.investigation_console: Optional[Any] = None

    def process_alerts_with_view(self, alerts) -> List[AlertGroup]:
        """Process alerts with live prompt_toolkit view."""
        return self.process_alerts_with_live_view(alerts)

    def process_alerts_with_live_view(self, alerts) -> List[AlertGroup]:
        """Process alerts with live prompt_toolkit view."""
        from rich.console import Console

        # Create investigation console
        self.investigation_console = Console(
            file=self.investigation_buffer, force_terminal=True, width=120
        )

        # Create and start the view
        self.view = AlertGroupingLiveView()
        self.view.total_alerts = len(alerts)
        self.view.update()

        # Add concise initial message
        self.view.update(log_line="Starting alert grouping analysis...")
        self.view.update(log_line="-" * 40)

        # Set up logging interceptor
        log_interceptor = LogInterceptor(self.view)
        original_handlers = logging.root.handlers.copy()

        for handler in original_handlers:
            logging.root.removeHandler(handler)
        logging.root.addHandler(log_interceptor)

        try:
            # Start the view
            self.view.start()

            # Process each alert
            for i, alert in enumerate(alerts):
                # Check if user requested stop
                if self.view.stop_event.is_set():
                    self.view.update(log_line="Processing stopped by user")
                    break

                self.view.update(
                    current_alert=alert.name,
                    processed_alerts=i + 1,  # Show 1-based counter
                    log_line=f"[{i+1}/{len(alerts)}] Processing {alert.name}...",
                )

                # DON'T clear investigation buffer - keep console output continuous
                # Just mark position for new output
                buffer_start = self.investigation_buffer.tell()

                # Process the alert
                group, is_new = self._process_single_alert_with_view(alert)

                # Get only the new investigation output since buffer_start
                self.investigation_buffer.seek(buffer_start)
                new_output = self.investigation_buffer.read()
                self.investigation_buffer.seek(0, 2)  # Go back to end for next write

                if new_output:
                    for line in new_output.split("\n"):
                        if line.strip():
                            self.view.update(console_line=line.strip())

                if group and not is_new:
                    # Only show "Grouped into" for existing groups
                    self.view.update(
                        groups=self.groups,
                        log_line=f"  → Added to existing group: {group.issue_title}",
                    )
                elif group and is_new:
                    # New group creation already logged, just update groups display
                    self.view.update(groups=self.groups)

                # Small delay to make updates visible
                time.sleep(0.1)

            # Final update
            self.view.update(
                current_alert=None,
                log_line="\n✅ Alert grouping complete!",
            )

            # Keep the display running until user exits
            self.view.update(log_line="")
            self.view.update(log_line="Press Ctrl+C to exit and see summary...")

            # Wait for user to exit
            while not self.view.stop_event.is_set():
                time.sleep(0.5)

        finally:
            # Stop the view
            self.view.stop()

            # Restore logging handlers
            logging.root.removeHandler(log_interceptor)
            for handler in original_handlers:
                logging.root.addHandler(handler)

        return self.groups

    def _process_single_alert_with_view(self, alert):
        """Process alert with logging to view. Returns (group, is_new) tuple."""
        # Check rules first
        for rule in self.rules:
            if self._matches_rule(alert, rule):
                if rule.times_used < self.verify_first_n:
                    self.view.update(log_line="  Verifying rule match...")
                    verification = self._verify_rule_match(alert, rule)

                    if verification.get("match_confirmed", False):
                        rule.times_used += 1
                        group = self._get_group(rule.group_id)
                        if group:
                            group.alerts.append(alert)
                            self.view.update(log_line="  ✓ Rule match verified")
                            return group, False  # Not a new group
                    else:
                        self.view.update(log_line="  ✗ Rule match failed verification")
                        if verification.get("suggested_adjustment"):
                            self._adjust_rule(
                                rule, verification["suggested_adjustment"]
                            )
                else:
                    # Trusted rule
                    rule.times_used += 1
                    group = self._get_group(rule.group_id)
                    if group:
                        group.alerts.append(alert)
                        self.view.update(log_line="  ✓ Matched by trusted rule")
                        return group, False  # Not a new group

        # No rule matched - run RCA
        self.view.update(log_line="  Running root cause analysis...")

        # Use the investigation console
        investigation = self.ai.investigate(
            issue=alert,
            prompt="builtin://generic_investigation.jinja2",
            console=self.investigation_console,
            instructions=None,
            post_processing_prompt=None,
        )

        rca = self._extract_rca_from_investigation(investigation, alert)

        # Check existing groups
        for group in self.groups:
            if self._check_root_cause_match(rca, group):
                group.alerts.append(alert)
                self.view.update(log_line="  ✓ Matched existing group")

                # Update the group's analysis to reflect the new alert
                old_title = group.issue_title
                self._update_group_analysis(group, alert)
                if group.issue_title != old_title:
                    self.view.update(
                        log_line=f"  📝 Updated group analysis: {group.issue_title}"
                    )

                # Maybe generate rule
                if len(group.alerts) >= 3 and not group.has_rule:
                    self.view.update(
                        log_line="  🔍 Analyzing pattern for rule generation..."
                    )
                    generated_rule = self._generate_rule(group)
                    if generated_rule is not None:
                        self.rules.append(generated_rule)
                        group.has_rule = True
                        self.view.update(
                            log_line=f"  ✅ Rule generated: {generated_rule.explanation[:50]}..."
                        )
                    else:
                        self.view.update(log_line="  ℹ️ No clear pattern for rule")

                return group, False  # Not a new group

        # Create new group
        group = AlertGroup(
            id=f"group-{uuid.uuid4().hex[:8]}",
            issue_title=rca.get("issue_title", "Unknown Issue"),
            description=rca.get("issue_title", ""),  # Start with title as description
            root_cause=rca["root_cause"],
            alerts=[alert],
            evidence=rca.get("evidence", []),
            affected_components=rca.get("affected_components", []),
            category=rca.get("category", "unknown"),
        )
        self.groups.append(group)
        self.view.update(log_line=f"  Created new group: {group.issue_title}")
        return group, True  # This is a new group
