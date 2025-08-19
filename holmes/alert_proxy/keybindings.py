"""Keybindings for the interactive alert view."""

from typing import Callable, Optional
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition


class KeybindingsManager:
    """Manages all keybindings for the alert view."""

    def __init__(self):
        self.kb = KeyBindings()
        self.not_searching_filter = Condition(lambda: not self._is_searching())
        self.view = None  # Will be set when view is created

    def _is_searching(self) -> bool:
        """Check if search is active."""
        return self.view and self.view.search_manager.is_active()

    def add_navigation_bindings(
        self,
        move_up: Callable,
        move_down: Callable,
        page_up: Callable,
        page_down: Callable,
        switch_pane: Callable,
    ):
        """Add navigation keybindings."""

        @self.kb.add("up", filter=self.not_searching_filter)
        @self.kb.add("k", filter=self.not_searching_filter)
        def _move_up(event):
            """Move up in list."""
            move_up()

        @self.kb.add("down", filter=self.not_searching_filter)
        @self.kb.add("j", filter=self.not_searching_filter)
        def _move_down(event):
            """Move down in list."""
            move_down()

        @self.kb.add("pageup", filter=self.not_searching_filter)
        @self.kb.add("c-b", filter=self.not_searching_filter)
        def _page_up(event):
            """Page up."""
            page_up()

        @self.kb.add("pagedown", filter=self.not_searching_filter)
        @self.kb.add("c-f", filter=self.not_searching_filter)
        def _page_down(event):
            """Page down."""
            page_down()

        @self.kb.add("tab")
        def _switch_pane(event):
            """Switch focus between panes."""
            switch_pane()

        @self.kb.add("g", "g", filter=self.not_searching_filter)
        def _go_to_top(event):
            """Go to top of list."""
            # Move to first item
            while move_up():
                pass

        @self.kb.add("G", filter=self.not_searching_filter)
        def _go_to_bottom(event):
            """Go to bottom of list."""
            # Move to last item
            while move_down():
                pass

    def add_ui_bindings(
        self,
        toggle_inspector: Optional[Callable] = None,
        toggle_console: Optional[Callable] = None,
    ):
        """Add UI toggle keybindings."""

        def _toggle_inspector(event):
            """Toggle inspector pane."""
            if toggle_inspector:
                toggle_inspector()

        def _toggle_console(event):
            """Toggle console output pane."""
            if toggle_console:
                toggle_console()

        if toggle_inspector:
            self.kb.add("i", filter=self.not_searching_filter)(_toggle_inspector)

        if toggle_console:
            self.kb.add("o", filter=self.not_searching_filter)(_toggle_console)

    def add_action_bindings(
        self,
        refresh: Callable,
        enrich_current: Optional[Callable] = None,
        enrich_all: Optional[Callable] = None,
        copy_current: Optional[Callable] = None,
        export_current: Optional[Callable] = None,
    ):
        """Add action keybindings."""

        @self.kb.add("r", filter=self.not_searching_filter)
        def _refresh(event):
            """Refresh alerts."""
            refresh()

        def _enrich_current(event):
            """Enrich current alert."""
            if enrich_current:
                enrich_current()

        def _enrich_all(event):
            """Enrich all alerts."""
            if enrich_all:
                enrich_all()

        def _copy_current(event):
            """Copy current alert details."""
            if copy_current:
                copy_current()

        def _export_current(event):
            """Export current alert."""
            if export_current:
                export_current()

        if enrich_current:
            self.kb.add("e", filter=self.not_searching_filter)(_enrich_current)

        if enrich_all:
            self.kb.add("E", filter=self.not_searching_filter)(_enrich_all)

        if copy_current:
            self.kb.add("y", filter=self.not_searching_filter)(_copy_current)

        if export_current:
            self.kb.add("s", filter=self.not_searching_filter)(_export_current)

    def add_search_bindings(
        self,
        start_search: Optional[Callable] = None,
        cancel_search: Optional[Callable] = None,
    ):
        """Add search keybindings."""

        def _start_search(event):
            """Start search."""
            # Check if not already in search mode
            if (
                start_search
                and hasattr(self, "view")
                and not self.view.search_manager.is_active()
            ):
                start_search()

        def _cancel_search(event):
            """Cancel search or clear filter - always clears all search state."""
            # Always call cancel_search - it handles all cases
            if cancel_search:
                cancel_search()

        if start_search:
            self.kb.add("/")(_start_search)

        if cancel_search:
            self.kb.add("escape")(_cancel_search)

    def add_help_binding(self, show_help: Callable):
        """Add help keybinding."""

        @self.kb.add("?", filter=self.not_searching_filter)
        @self.kb.add("h", filter=self.not_searching_filter)
        def _show_help(event):
            """Show help."""
            show_help()

    def add_quit_binding(self, quit_app: Callable):
        """Add quit keybinding."""

        @self.kb.add("q", filter=self.not_searching_filter)
        @self.kb.add("c-c")
        def _quit(event):
            """Quit application."""
            quit_app()

    def get_bindings(self) -> KeyBindings:
        """Get the configured keybindings."""
        return self.kb
