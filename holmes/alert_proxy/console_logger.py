"""Console logging functionality for the interactive view."""

import logging
from datetime import datetime
from typing import List, Optional, Callable
from collections import deque


class ConsoleLogger:
    """Manages console output for the interactive view."""

    def __init__(self, max_lines: int = 1000):
        """Initialize console logger with a maximum number of lines to keep."""
        self.lines: deque = deque(maxlen=max_lines)
        self.update_callback: Optional[Callable] = None

    def set_update_callback(self, callback: Callable):
        """Set a callback to be called when lines are added."""
        self.update_callback = callback

    def add_line(self, message: str, timestamp: bool = True):
        """Add a line to the console output."""
        if timestamp:
            ts = datetime.now().strftime("%H:%M:%S")
            message = f"[{ts}] {message}"

        self.lines.append(message)

        # Trigger update callback if set
        if self.update_callback:
            self.update_callback()

    def add_lines(self, messages: List[str], timestamp: bool = True):
        """Add multiple lines to the console output."""
        for message in messages:
            self.add_line(message, timestamp)

    def clear(self):
        """Clear all console output."""
        self.lines.clear()
        if self.update_callback:
            self.update_callback()

    def get_text(self, last_n: Optional[int] = None) -> str:
        """Get console text as a single string."""
        if last_n:
            lines_to_show = list(self.lines)[-last_n:]
        else:
            lines_to_show = list(self.lines)

        return "\n".join(lines_to_show)

    def get_lines(self) -> List[str]:
        """Get all console lines as a list."""
        return list(self.lines)

    def add_separator(self):
        """Add a separator line."""
        self.add_line("─" * 60, timestamp=False)

    def add_header(self, title: str):
        """Add a header with title."""
        self.add_separator()
        self.add_line(f"  {title}", timestamp=False)
        self.add_separator()

    def add_error(self, message: str, exception: Optional[Exception] = None):
        """Add an error message to the console."""
        self.add_line(f"❌ ERROR: {message}")
        if exception:
            self.add_line(f"   {str(exception)}", timestamp=False)

    def add_warning(self, message: str):
        """Add a warning message to the console."""
        self.add_line(f"⚠️  WARNING: {message}")

    def add_info(self, message: str):
        """Add an info message to the console."""
        self.add_line(f"ℹ️  {message}")

    def add_success(self, message: str):
        """Add a success message to the console."""
        self.add_line(f"✅ {message}")


class LogInterceptor(logging.Handler):
    """Logging handler that intercepts logs and sends them to ConsoleLogger."""

    def __init__(self, console_logger: ConsoleLogger):
        """Initialize the log interceptor."""
        super().__init__()
        self.console_logger = console_logger
        self.setLevel(logging.INFO)

    def emit(self, record):
        """Emit a log record to the console logger."""
        try:
            msg = self.format(record)

            # Add appropriate icon based on log level
            if record.levelno >= logging.ERROR:
                self.console_logger.add_error(msg)
            elif record.levelno >= logging.WARNING:
                self.console_logger.add_warning(msg)
            elif record.levelno >= logging.INFO:
                self.console_logger.add_info(msg)
            else:
                self.console_logger.add_line(msg)

        except Exception:
            # Ignore errors in logging
            pass
