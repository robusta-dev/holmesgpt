"""Utility functions for CLI interactive mode."""

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea
from rich.console import Console
from rich.panel import Panel


def create_vim_navigation_bindings(text_area: TextArea) -> KeyBindings:
    """Create reusable vim/less-like navigation key bindings for scrollable text areas."""
    bindings = KeyBindings()

    # Exit commands
    @bindings.add("q")
    @bindings.add("escape")
    def _(event):
        event.app.exit()

    @bindings.add("c-c")
    def _(event):
        event.app.exit()

    # Vim/less-like navigation
    @bindings.add("j")
    @bindings.add("down")
    def _(event):
        event.app.layout.focus(text_area)
        text_area.buffer.cursor_down()

    @bindings.add("k")
    @bindings.add("up")
    def _(event):
        event.app.layout.focus(text_area)
        text_area.buffer.cursor_up()

    @bindings.add("g")
    @bindings.add("home")
    def _(event):
        event.app.layout.focus(text_area)
        text_area.buffer.cursor_position = 0

    @bindings.add("G")
    @bindings.add("end")
    def _(event):
        event.app.layout.focus(text_area)
        # Go to last line, then to beginning of that line
        text_area.buffer.cursor_position = len(text_area.buffer.text)
        text_area.buffer.cursor_left(
            count=text_area.buffer.document.cursor_position_col
        )

    @bindings.add("d")
    @bindings.add("c-d")
    @bindings.add("pagedown")
    def _(event):
        event.app.layout.focus(text_area)
        # Get current window height and scroll by half
        window_height = event.app.output.get_size().rows - 1  # -1 for header
        scroll_amount = max(1, window_height // 2)
        for _ in range(scroll_amount):
            text_area.buffer.cursor_down()

    @bindings.add("u")
    @bindings.add("c-u")
    @bindings.add("pageup")
    def _(event):
        event.app.layout.focus(text_area)
        # Get current window height and scroll by half
        window_height = event.app.output.get_size().rows - 1  # -1 for header
        scroll_amount = max(1, window_height // 2)
        for _ in range(scroll_amount):
            text_area.buffer.cursor_up()

    @bindings.add("f")
    @bindings.add("c-f")
    @bindings.add("space")
    def _(event):
        event.app.layout.focus(text_area)
        # Get current window height and scroll by full page
        window_height = event.app.output.get_size().rows - 1  # -1 for header
        scroll_amount = max(1, window_height)
        for _ in range(scroll_amount):
            text_area.buffer.cursor_down()

    @bindings.add("b")
    @bindings.add("c-b")
    def _(event):
        event.app.layout.focus(text_area)
        # Get current window height and scroll by full page
        window_height = event.app.output.get_size().rows - 1  # -1 for header
        scroll_amount = max(1, window_height)
        for _ in range(scroll_amount):
            text_area.buffer.cursor_up()

    return bindings


def show_scrollable_modal(
    content: str,
    title: str,
    console: Console,
    enable_word_wrap: bool = True,
    fallback_panel_style: str = "magenta",
) -> None:
    """
    Display content in a scrollable modal window with vim-like navigation.

    Args:
        content: The text content to display
        title: Title for the modal window
        console: Rich console for fallback display
        enable_word_wrap: Whether to enable word wrap toggle (w key)
        fallback_panel_style: Border style for fallback panel display
    """
    try:
        # Create text area with the content
        text_area = TextArea(
            text=content,
            read_only=True,
            scrollbar=True,
            line_numbers=False,
            wrap_lines=False,  # Disable word wrap by default
        )

        wrap_status = "off"
        header_text = f"{title} (exit: q, nav: ↑↓/j/k/g/G/d/u/f/b/space{', wrap: w [' + wrap_status + ']' if enable_word_wrap else ''})"
        header = Window(
            FormattedTextControl(header_text),
            height=1,
            style="reverse",
        )

        # Create layout
        layout = Layout(
            HSplit(
                [
                    header,
                    text_area,
                ]
            )
        )

        # Get navigation bindings
        bindings = create_vim_navigation_bindings(text_area)

        # Add word wrap toggle if enabled
        if enable_word_wrap:

            @bindings.add("w")
            def _(event):
                # Toggle word wrap
                text_area.wrap_lines = not text_area.wrap_lines
                # Update the header to show current wrap state
                nonlocal wrap_status
                wrap_status = "on" if text_area.wrap_lines else "off"
                new_header_text = f"{title} (exit: q, nav: ↑↓/j/k/g/G/d/u/f/b/space, wrap: w [{wrap_status}])"
                header.content = FormattedTextControl(new_header_text)

        # Create and run application
        app: Application = Application(
            layout=layout,
            key_bindings=bindings,
            full_screen=True,
        )

        app.run()

    except Exception as e:
        # Fallback to regular panel display
        console.print(f"[bold red]Error showing modal: {e}[/bold red]")
        console.print(Panel(content, title=title, border_style=fallback_panel_style))
