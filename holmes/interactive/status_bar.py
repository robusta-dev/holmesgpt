"""Status bar management for interactive mode."""

import threading
from typing import Optional, Dict, Any, Callable


class StatusBarManager:
    """Manages the bottom toolbar status messages in interactive mode."""

    def __init__(self):
        self.messages = {
            "status": "",  # General status messages (e.g., Ctrl+C message)
            "version": "",  # Version update messages
            "toolsets": "",  # Toolset refresh messages
        }
        self.active_timers = []
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_index = 0
        self.spinner_timer = None
        self.session_app = None  # Will be set when session is available

    def set_session_app(self, app):
        """Set the prompt session app for invalidation."""
        self.session_app = app

    def _create_timer(self, delay: float, func: Callable) -> threading.Timer:
        """Create a daemon timer and track it for cleanup."""
        timer = threading.Timer(delay, func)
        timer.daemon = True
        self.active_timers.append(timer)
        timer.start()
        return timer

    def cleanup(self):
        """Cancel all active timers for clean shutdown."""
        if self.spinner_timer:
            self.spinner_timer.cancel()
        for timer in self.active_timers:
            timer.cancel()
        self.active_timers.clear()

    def set_message(
        self, message_type: str, content: str, duration: Optional[float] = None
    ):
        """Set a status message, optionally auto-clearing after duration seconds."""
        self.messages[message_type] = content
        self._invalidate()

        if duration:

            def clear_message():
                self.messages[message_type] = ""
                self._invalidate()

            self._create_timer(duration, clear_message)

    def start_spinner(
        self, base_message: str, get_progress_info: Optional[Callable] = None
    ):
        """Start an animated spinner with optional progress info."""
        self.stop_spinner()  # Stop any existing spinner

        def update_spinner():
            if not self.messages.get("toolsets"):  # Stop if message was cleared
                return

            spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            self.spinner_index += 1

            msg = f"{spinner} {base_message}"

            # Add progress info if available
            if get_progress_info:
                progress = get_progress_info()
                if progress and progress.get("total", 0) > 0:
                    msg = f"{spinner} {base_message} {progress['current']}/{progress['total']}"

                    # Format with active checks info for right-alignment
                    if progress.get("active"):
                        first_active = progress["active"][0]
                        extra = (
                            f" +{len(progress['active']) - 1}"
                            if len(progress["active"]) > 1
                            else ""
                        )
                        # Return formatted list for proper splitting
                        self.messages["toolsets"] = [
                            ("bg:#0080ff fg:#000000", msg),
                            ("fg:#000000", " "),  # Separator
                            (
                                "bg:#808080 fg:#000000",
                                f"checking {first_active}{extra}",
                            ),
                        ]
                        self._invalidate()
                        self.spinner_timer = self._create_timer(0.1, update_spinner)
                        return

            # Simple message without progress
            self.messages["toolsets"] = [("bg:#0080ff fg:#000000", msg)]
            self._invalidate()

            # Schedule next update
            self.spinner_timer = self._create_timer(0.1, update_spinner)

        # Start spinner
        update_spinner()

    def stop_spinner(self):
        """Stop the spinner animation."""
        if self.spinner_timer:
            self.spinner_timer.cancel()
            self.spinner_timer = None

    def set_toolset_status(self, status_data: Dict[str, Any]):
        """Set toolset refresh completion status."""
        self.stop_spinner()

        if not status_data.get("success"):
            self.set_message("toolsets", "✗ Toolset refresh failed", duration=5)
            return

        # Build formatted status message
        total_enabled = status_data["total_enabled"]
        newly_enabled = status_data.get("newly_enabled", set())
        newly_disabled = status_data.get("newly_disabled", set())

        if newly_enabled or newly_disabled:
            status_parts = []

            # First section with green background
            status_parts.append(("bg:ansigreen ansiblack", f" {total_enabled} ready "))

            if newly_enabled:
                # Show first 3 toolsets by name, then count if more
                names_to_show = sorted(newly_enabled)[:3]
                if len(newly_enabled) > 3:
                    extra_count = len(newly_enabled) - 3
                    names_display = " ".join(names_to_show) + f" +{extra_count}"
                else:
                    names_display = " ".join(names_to_show)
                status_parts.append(
                    ("bg:ansiblue ansiwhite", f" new: {names_display} ")
                )

            if newly_disabled:
                # Show first 3 toolsets by name, then count if more
                names_to_show = sorted(newly_disabled)[:3]
                if len(newly_disabled) > 3:
                    extra_count = len(newly_disabled) - 3
                    names_display = " ".join(names_to_show) + f" +{extra_count}"
                else:
                    names_display = " ".join(names_to_show)
                status_parts.append(
                    ("bg:ansired ansiwhite", f" disabled: {names_display} ")
                )

            self.messages["toolsets"] = status_parts
        else:
            # No changes - show simple status
            self.messages["toolsets"] = [
                ("bg:ansigreen ansiblack", f" {total_enabled} datasources ready "),
                ("bg:ansibrightblack ansiwhite", " no changes "),
            ]

        self._invalidate()

        # Clear after 5 seconds
        def clear_status():
            self.messages["toolsets"] = ""
            self._invalidate()

        self._create_timer(5, clear_status)

    def get_bottom_toolbar(self, terminal_width: Optional[int] = None):
        """Generate the formatted bottom toolbar."""
        left_messages = []
        right_messages = []

        # Status message (red background) - goes on left
        if self.messages["status"]:
            left_messages.append(("bg:#ff0000 fg:#000000", self.messages["status"]))

        # Version message (yellow background) - goes on left
        if self.messages["version"]:
            if left_messages:
                left_messages.append(("", " | "))
            left_messages.append(("bg:#ffff00 fg:#000000", self.messages["version"]))

        # Toolsets message
        toolsets_msg = self.messages["toolsets"]
        if toolsets_msg:
            if isinstance(toolsets_msg, list) and len(toolsets_msg) > 2:
                # Split message - main part on left, active toolset on right
                if left_messages:
                    left_messages.append(("", " | "))
                left_messages.append(toolsets_msg[0])
                right_messages.append(toolsets_msg[2])
            else:
                # Regular message handling
                if left_messages:
                    left_messages.append(("", " | "))

                if isinstance(toolsets_msg, list):
                    left_messages.extend(toolsets_msg)
                elif isinstance(toolsets_msg, str):
                    # Handle string messages (errors)
                    if "✗" in toolsets_msg:
                        left_messages.append(("bg:#ff0000 fg:#000000", toolsets_msg))
                    else:
                        left_messages.append(("bg:#00ff00 fg:#000000", toolsets_msg))

        if not left_messages and not right_messages:
            return None

        # If we have right messages, we need to create formatted text with alignment
        if right_messages:
            width = terminal_width or 80

            # Calculate left side width
            left_text = "".join(text for _, text in left_messages)
            left_width = len(left_text)

            # Calculate padding
            right_text = "".join(text for _, text in right_messages)
            right_width = len(right_text)
            padding_width = max(1, width - left_width - right_width - 2)

            # Combine with padding
            return (
                left_messages + [("fg:#000000", " " * padding_width)] + right_messages
            )
        else:
            return left_messages

    def _invalidate(self):
        """Invalidate the prompt session to refresh display."""
        if self.session_app:
            self.session_app.invalidate()
