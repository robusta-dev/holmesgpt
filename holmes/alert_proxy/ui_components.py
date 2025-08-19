"""UI components for the interactive alert view."""

from typing import Callable, Optional, TYPE_CHECKING
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

if TYPE_CHECKING:
    from holmes.alert_proxy.models import InteractiveModeConfig


class StatusBar:
    """Status bar component showing header and footer."""

    def __init__(
        self, get_alerts: Callable, get_status: Callable, get_focused_pane: Callable
    ):
        """Initialize status bar.

        Args:
            get_alerts: Function to get current alerts list
            get_status: Function to get current processing status
            get_focused_pane: Function to get currently focused pane index
        """
        self.get_alerts = get_alerts
        self.get_status = get_status
        self.get_focused_pane = get_focused_pane
        self.alert_config: Optional["InteractiveModeConfig"] = None  # Set by view

        # Create header window
        self.header = Window(
            FormattedTextControl(self._get_header_text),
            height=1,
            style="bold fg:#00aa00",
        )

        # Create footer window
        self.footer = Window(
            FormattedTextControl(self._get_footer_text),
            height=1,
            style="fg:#888888",
        )

    def _get_header_text(self):
        """Get header text with branding and model info."""
        model_info = ""
        if self.alert_config and hasattr(self.alert_config, "model"):
            model_info = f"  •  Model: {self.alert_config.model}"
        return f"🚨 HolmesGPT Alert Viewer{model_info}  •  {self.get_status()}"

    def _get_footer_text(self):
        """Get footer text with context-sensitive shortcuts."""
        shortcuts = []
        focused_pane = self.get_focused_pane()

        # Context-specific shortcuts based on focused pane
        if focused_pane == 0:  # Alert list
            shortcuts = [
                "Move=j/k",
                "Enrich=e",
                "Enrich all=E",
                "Copy=y",
                "Export=x",
                "Tab=Switch",
                "Help=?",
                "Quit=q",
            ]
        elif focused_pane == 1:  # Inspector
            shortcuts = [
                "Scroll=j/k",
                "Tab=Switch",
                "Help=?",
                "Quit=q",
            ]
        elif focused_pane == 2:  # Console
            shortcuts = [
                "Scroll=j/k",
                "Tab=Switch",
                "Help=?",
                "Quit=q",
            ]
        else:
            shortcuts = ["Switch=Tab", "Help=?", "Quit=q"]

        return " | ".join(shortcuts)


class CollapsedPaneIndicators:
    """Visual indicators for collapsed panes."""

    @staticmethod
    def get_collapsed_inspector():
        """Get collapsed inspector indicator (vertical text)."""

        def get_text():
            lines = [
                "◀",  # Arrow pointing left
                "━",  # Heavy horizontal line
                " ",
                "P",
                "r",
                "e",
                "s",
                "s",
                " ",
                "i",
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
            # Fill remaining with subtle line
            for _ in range(10):
                lines.append("┊")  # Dotted vertical line
            lines.append("◀")
            return "\n".join(lines)

        return Window(
            FormattedTextControl(get_text),
            width=1,
            style="fg:#505050",  # Subtle gray
        )

    @staticmethod
    def get_collapsed_console():
        """Get collapsed console indicator (horizontal bar)."""

        def get_text():
            return " Console (o to expand) "

        return Window(
            FormattedTextControl(get_text),
            height=1,
            style="fg:#606060 bold",
        )
