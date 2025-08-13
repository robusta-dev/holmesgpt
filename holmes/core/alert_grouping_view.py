"""
Two-pane view for alert grouping visualization using Rich.
"""

import uuid
import logging
from io import StringIO
from typing import List, Optional, Union
from datetime import datetime
from rich.console import Console, Group as RichGroup
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich.align import Align
from rich import box

from holmes.core.alert_grouping import AlertGroup, SmartAlertGrouper


class LogCapture:
    """Captures console and logging output."""

    def __init__(self):
        self.lines = []
        self.max_lines = 10
        self.pending_lines = []  # Buffer for batching

    def write(self, text):
        if text and text.strip():
            # Split by newlines and add to pending
            for line in text.split("\n"):
                if line.strip():
                    self.pending_lines.append(line)

    def flush_pending(self):
        """Flush pending lines to main buffer in batch."""
        if self.pending_lines:
            self.lines.extend(self.pending_lines)
            # Trim to max_lines
            if len(self.lines) > self.max_lines:
                self.lines = self.lines[-self.max_lines :]
            self.pending_lines = []

    def flush(self):
        pass

    def get_lines(self):
        # Include pending lines in output
        all_lines = self.lines + self.pending_lines
        return all_lines[-self.max_lines :]


class AlertGroupingView:
    """Manages a two-pane view for alert grouping visualization."""

    def __init__(self, console: Console):
        self.console = console
        self.layout = self._create_layout()
        self.groups: List[AlertGroup] = []
        self.current_alert: Optional[str] = None
        self.total_alerts = 0
        self.processed_alerts = 0
        self.log_lines: List[str] = []
        self.max_log_lines = 20
        self.console_output = LogCapture()

    def _create_layout(self) -> Layout:
        """Create the layout with three sections."""
        layout = Layout()

        # Create main structure
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="logs", size=8),  # Console output pane
            Layout(name="footer", size=1),
        )

        # Split body into two panes (make groups pane wider)
        layout["body"].split_row(
            Layout(name="progress", ratio=2),
            Layout(name="groups", ratio=3),  # 3:2 ratio = groups pane is 1.5x wider
        )

        return layout

    def _create_header(self) -> Panel:
        """Create the header panel."""
        header_text = Text("🔍 Alert Grouping Analysis", style="bold magenta")
        subtitle = Text(
            f"Processing {self.processed_alerts}/{self.total_alerts} alerts",
            style="dim",
        )
        content = RichGroup(Align.center(header_text), Align.center(subtitle))
        return Panel(content, box=box.DOUBLE, style="bright_blue")

    def _create_progress_panel(self) -> Panel:
        """Create the left panel showing investigation progress."""
        # Create a text buffer with recent log lines
        log_content = Text()

        for line in self.log_lines[-self.max_log_lines :]:
            if "Processing" in line:
                log_content.append(line + "\n", style="bold yellow")
            elif "Running root cause analysis" in line:
                log_content.append(line + "\n", style="cyan")
            elif "→ Grouped into:" in line:
                log_content.append(line + "\n", style="green")
            elif "📁 Created new group:" in line:
                log_content.append(line + "\n", style="bold green")
            elif "Tool" in line or "Running tool" in line:
                log_content.append(line + "\n", style="dim")
            elif "Error" in line:
                log_content.append(line + "\n", style="red")
            else:
                log_content.append(line + "\n")

        # Add current processing status
        if self.current_alert:
            status = Text(
                f"\n⚡ Currently analyzing: {self.current_alert}", style="bold cyan"
            )
            log_content.append(status)

        return Panel(
            log_content,
            title="[bold]Investigation Progress[/bold]",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2),
        )

    def _create_groups_panel(self) -> Panel:
        """Create the right panel showing grouped alerts."""
        content: Union[Align, Tree]
        if not self.groups:
            content = Align.center(
                Text("No groups formed yet...", style="dim"), vertical="middle"
            )
        else:
            # Create a tree view of groups
            tree = Tree("📊 Alert Groups", style="bold")

            for i, group in enumerate(self.groups, 1):
                # Group node with colored severity indicator
                severity_color = self._get_severity_color(group)
                group_label = Text(f"Group {i}: ", style="bold")
                group_label.append(f"{group.issue_title}", style=severity_color)

                group_node = tree.add(group_label)

                # Add metadata
                meta_node = group_node.add("[dim]Metadata[/dim]")
                meta_node.add(f"📝 Category: {group.category}")
                meta_node.add(f"📊 Alerts: {len(group.alerts)}")
                # Add root cause as a detail (truncate if too long)
                root_cause_text = (
                    group.root_cause[:100] + "..."
                    if len(group.root_cause) > 100
                    else group.root_cause
                )
                meta_node.add(f"🔍 Root Cause: {root_cause_text}", style="dim")
                if group.has_rule:
                    meta_node.add("✅ Rule: Generated", style="green")
                else:
                    meta_node.add("⏳ Rule: Pending", style="yellow")

                # Add alerts
                alerts_node = group_node.add(f"[dim]Alerts ({len(group.alerts)})[/dim]")
                for alert in group.alerts[:5]:  # Show first 5
                    alert_text = f"• {alert.name}"
                    alerts_node.add(alert_text, style="cyan")
                if len(group.alerts) > 5:
                    alerts_node.add(
                        f"... and {len(group.alerts) - 5} more", style="dim"
                    )

            content = tree

        return Panel(
            content,
            title="[bold]Alert Groups[/bold]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )

    def _create_logs_panel(self) -> Panel:
        """Create the console output panel."""
        log_content = Text()

        # Get captured console output
        console_lines = self.console_output.get_lines()

        if console_lines:
            for line in console_lines:
                # Color code based on content
                if "error" in line.lower():
                    log_content.append(line + "\n", style="red dim")
                elif "warning" in line.lower():
                    log_content.append(line + "\n", style="yellow dim")
                elif "info" in line.lower():
                    log_content.append(line + "\n", style="blue dim")
                elif "Running tool" in line or "Finished" in line:
                    log_content.append(line + "\n", style="cyan dim")
                else:
                    log_content.append(line + "\n", style="dim")
        else:
            log_content.append("No console output yet...", style="dim italic")

        return Panel(
            log_content,
            title="[bold]Console Output[/bold]",
            border_style="dim",
            box=box.SIMPLE,
            padding=(0, 1),
        )

    def _create_footer(self) -> Panel:
        """Create the footer with statistics."""
        stats = []

        if self.groups:
            total_in_groups = sum(len(g.alerts) for g in self.groups)
            rules_generated = sum(1 for g in self.groups if g.has_rule)

            stats = [
                f"Groups: {len(self.groups)}",
                f"Grouped Alerts: {total_in_groups}",
                f"Rules: {rules_generated}",
                f"Time: {datetime.now().strftime('%H:%M:%S')}",
            ]

        footer_text = " | ".join(stats) if stats else "Initializing..."
        return Panel(
            Align.center(Text(footer_text, style="dim")), box=box.SIMPLE, style="dim"
        )

    def _get_severity_color(self, group: AlertGroup) -> str:
        """Get color based on group severity."""
        # Check if any alerts in the group have critical severity
        for alert in group.alerts:
            if alert.raw and alert.raw.get("labels", {}).get("severity") == "critical":
                return "red"
            elif alert.raw and alert.raw.get("labels", {}).get("severity") == "warning":
                return "yellow"
        return "green"

    def update(
        self,
        groups: Optional[List[AlertGroup]] = None,
        current_alert: Optional[str] = None,
        log_line: Optional[str] = None,
        total_alerts: Optional[int] = None,
        processed_alerts: Optional[int] = None,
        console_line: Optional[str] = None,
    ):
        """Update the view with new data."""
        if groups is not None:
            self.groups = groups
        if current_alert is not None:
            self.current_alert = current_alert
        if log_line:
            self.log_lines.append(log_line)
        if total_alerts is not None:
            self.total_alerts = total_alerts
        if processed_alerts is not None:
            self.processed_alerts = processed_alerts
        if console_line:
            self.console_output.write(console_line)

        # Update layout panels
        self.layout["header"].update(self._create_header())
        self.layout["progress"].update(self._create_progress_panel())
        self.layout["groups"].update(self._create_groups_panel())
        self.layout["logs"].update(self._create_logs_panel())
        self.layout["footer"].update(self._create_footer())

    def get_layout(self) -> Layout:
        """Get the current layout."""
        return self.layout


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


class LiveAlertGrouper(SmartAlertGrouper):
    """Extended SmartAlertGrouper with live view support."""

    def __init__(self, ai, console, verify_first_n: int = 5):
        # Initialize parent but we'll override console usage
        super().__init__(ai, console, verify_first_n)
        self.view: Optional[AlertGroupingView] = None
        self.live: Optional[Live] = None
        # Create a separate console for investigations to capture output
        from rich.console import Console

        self.investigation_buffer = StringIO()
        self.investigation_console = Console(
            file=self.investigation_buffer, force_terminal=True, width=120
        )

    def process_alerts_with_view(self, alerts) -> List[AlertGroup]:
        """Process alerts with live two-pane view."""
        self.view = AlertGroupingView(self.console)

        # Initialize view
        self.view.total_alerts = len(alerts)
        self.view.update()

        # Replace all logging handlers with our interceptor to prevent console output
        log_interceptor = LogInterceptor(self.view)
        original_handlers = logging.root.handlers.copy()

        # Remove all existing handlers and add only our interceptor
        for handler in original_handlers:
            logging.root.removeHandler(handler)
        logging.root.addHandler(log_interceptor)

        try:
            # Use Live display with the main console
            with Live(
                self.view.get_layout(),
                console=self.console,
                refresh_per_second=2,
                screen=False,
            ) as live:
                self.live = live

                # Process each alert
                for i, alert in enumerate(alerts):
                    self.view.update(
                        current_alert=alert.name,
                        processed_alerts=i,
                        log_line=f"[{i+1}/{len(alerts)}] Processing {alert.name}...",
                    )

                    # Clear the investigation buffer before processing
                    self.investigation_buffer.truncate(0)
                    self.investigation_buffer.seek(0)

                    # Process the alert (using investigation_console internally)
                    group = self._process_single_alert_with_logging(alert)

                    # Get output from investigation console and batch update
                    investigation_output = self.investigation_buffer.getvalue()
                    if investigation_output:
                        # Collect all lines first
                        lines_to_add = [
                            line.strip()
                            for line in investigation_output.split("\n")
                            if line.strip()
                        ]
                        # Update console output in one batch
                        if lines_to_add:
                            for line in lines_to_add:
                                self.view.console_output.write(line)
                            # Force a single refresh after batch update
                            self.view.console_output.flush_pending()
                            live.refresh()

                    if group:
                        self.view.update(
                            groups=self.groups,
                            log_line=f"  → Grouped into: {group.issue_title}",
                        )

                    self.view.update(processed_alerts=i + 1)

                    # Force refresh the display
                    live.refresh()

                # Final update
                self.view.update(
                    current_alert=None, log_line="\n✅ Alert grouping complete!"
                )

                # Keep the display for a moment
                import time

                time.sleep(2)
        finally:
            # Restore original logging handlers
            logging.root.removeHandler(log_interceptor)
            for handler in original_handlers:
                logging.root.addHandler(handler)

        return self.groups

    def _process_single_alert_with_logging(self, alert):
        """Process alert with logging to view."""
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
                            return group
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
                        return group

        # No rule matched - run RCA
        self.view.update(log_line="  Running root cause analysis...")

        # Use the investigation console instead of main console
        investigation = self.ai.investigate(
            issue=alert,
            prompt="builtin://generic_investigation.jinja2",
            console=self.investigation_console,  # Use separate console
            instructions=None,
            post_processing_prompt=None,
        )

        rca = self._extract_rca_from_investigation(investigation, alert)

        # Check existing groups
        for group in self.groups:
            if self._check_root_cause_match(rca, group):
                group.alerts.append(alert)
                self.view.update(log_line="  ✓ Matched existing group")

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
                        # Log rule details to console output
                        rule_details = (
                            f"Rule: {len(generated_rule.conditions)} conditions"
                        )
                        self.view.update(console_line=rule_details)
                    else:
                        self.view.update(log_line="  ℹ️ No clear pattern for rule")

                return group

        # Create new group
        group = AlertGroup(
            id=f"group-{uuid.uuid4().hex[:8]}",
            issue_title=rca.get("issue_title", "Unknown Issue"),
            root_cause=rca["root_cause"],
            alerts=[alert],
            evidence=rca.get("evidence", []),
            affected_components=rca.get("affected_components", []),
            category=rca.get("category", "unknown"),
        )
        self.groups.append(group)
        self.view.update(log_line=f"  📁 Created new group: {group.issue_title}")
        return group
