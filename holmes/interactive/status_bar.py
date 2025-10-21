"""Status bar management for interactive mode."""

import threading
from enum import Enum
from typing import Optional, Dict, Callable, Union, Tuple, List


class MessageType(Enum):
    """Types of status bar messages."""

    STATUS = "status"  # General status messages (e.g., Ctrl+C message)
    VERSION = "version"  # Version update messages
    TOOLSETS = "toolsets"  # Toolset refresh messages


class StatusBarManager:
    """Manages the bottom toolbar status messages in interactive mode."""

    def __init__(self):
        self.messages: Dict[
            MessageType, Union[str, List[Tuple[str, str]], Tuple[str, str]]
        ] = {
            MessageType.STATUS: "",
            MessageType.VERSION: "",
            MessageType.TOOLSETS: "",
        }
        self.active_timers = []
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_index = 0
        self.spinner_timer = None
        self.spinner_active = False  # Track if spinner is running
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
        self,
        message_type: MessageType,
        content: str,
        duration: Optional[float] = None,
        style: Optional[str] = None,
    ):
        """Set a status message, optionally auto-clearing after duration seconds."""
        # Apply style if provided, otherwise use default for message type
        if style:
            self.messages[message_type] = (style, content)
        else:
            self.messages[message_type] = self._get_default_style(message_type, content)
        self._invalidate()

        if duration:

            def clear_message():
                self.messages[message_type] = ""
                self._invalidate()

            self._create_timer(duration, clear_message)

    def _get_default_style(
        self, message_type: MessageType, content: str
    ) -> Tuple[str, str]:
        """Get default style for a message type."""
        if message_type == MessageType.STATUS:
            return ("bg:#ff0000 fg:#000000", content)
        elif message_type == MessageType.VERSION:
            return ("bg:#ffff00 fg:#000000", content)
        elif message_type == MessageType.TOOLSETS:
            # Simple heuristic for error vs success
            if "✗" in content or "failed" in content.lower():
                return ("bg:#ff0000 fg:#000000", content)
            elif "ready" in content:
                return ("bg:ansigreen ansiblack", content)
            else:
                return ("bg:#0080ff fg:#000000", content)
        else:
            return ("", content)

    def start_spinner(self, get_message: Callable[[], Tuple[str, Optional[str]]]):
        """Start an animated spinner. The callback should return (main_message, right_message)."""
        self.stop_spinner()  # Stop any existing spinner
        self.spinner_active = True  # Track spinner state

        def update_spinner():
            if not self.spinner_active:  # Stop if spinner was stopped
                return

            spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            self.spinner_index += 1

            # Get the formatted messages from the callback
            main_msg, right_msg = get_message()
            msg = f"{spinner} {main_msg}"

            # Build styled message
            styled_parts = [("bg:#0080ff fg:#000000", msg)]
            if right_msg:
                styled_parts.append(("fg:#000000", " "))  # Separator
                styled_parts.append(("bg:#808080 fg:#000000", right_msg))

            self.messages[MessageType.TOOLSETS] = (
                styled_parts if len(styled_parts) > 1 else styled_parts[0]
            )
            self._invalidate()

            # Schedule next update
            self.spinner_timer = self._create_timer(0.1, update_spinner)

        # Start spinner
        update_spinner()

    def stop_spinner(self):
        """Stop the spinner animation."""
        self.spinner_active = False  # Mark spinner as inactive
        if self.spinner_timer:
            self.spinner_timer.cancel()
            self.spinner_timer = None

    def show_toolset_complete(
        self, styled_parts: List[Tuple[str, str]], duration: float = 5
    ):
        """Show toolset refresh completion message with styled parts."""
        self.stop_spinner()
        self.messages[MessageType.TOOLSETS] = styled_parts
        self._invalidate()

        if duration:

            def clear_message():
                self.messages[MessageType.TOOLSETS] = ""
                self._invalidate()

            self._create_timer(duration, clear_message)

    def get_bottom_toolbar(self, terminal_width: Optional[int] = None):
        """Generate the formatted bottom toolbar."""
        left_messages: List[Tuple[str, str]] = []
        right_messages: List[Tuple[str, str]] = []

        # Process each message type
        for msg_type in [MessageType.STATUS, MessageType.VERSION, MessageType.TOOLSETS]:
            msg = self.messages[msg_type]
            if not msg:
                continue

            # Add separator if not first message
            if left_messages:
                left_messages.append(("", " | "))

            # Handle different message formats
            if isinstance(msg, str):
                # Plain string - shouldn't happen with new structure but handle it
                left_messages.append(("", msg))
            elif isinstance(msg, tuple):
                # Single styled message
                left_messages.append(msg)
            elif isinstance(msg, list):
                # Multiple parts - check for right-aligned content
                # Right-aligned content will have separator in middle
                separator_idx = None
                for i, part in enumerate(msg):
                    if part[0] == "fg:#000000" and part[1] == " ":
                        separator_idx = i
                        break

                if separator_idx is not None and separator_idx < len(msg) - 1:
                    # Has right-aligned content
                    left_messages.extend(msg[:separator_idx])
                    right_messages.extend(msg[separator_idx + 1 :])
                else:
                    # All content on left
                    left_messages.extend(msg)

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
