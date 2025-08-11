"""Toolset refresh management for interactive mode."""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Set, List, Tuple

from holmes.core.tools import ToolsetStatusEnum
from holmes.core.tools_utils.tool_executor import ToolExecutor


@dataclass
class RefreshProgress:
    """Progress information for toolset refresh."""

    current: int = 0
    total: int = 0
    active: List[str] = field(default_factory=list)


@dataclass
class RefreshResult:
    """Result of a toolset refresh operation."""

    success: bool
    total_enabled: int = 0
    newly_enabled: Set[str] = field(default_factory=set)
    newly_disabled: Set[str] = field(default_factory=set)
    error: Optional[str] = None


class ToolsetRefreshManager:
    """Manages background toolset refresh operations."""

    def __init__(self, config, ai, status_bar=None):
        self.config = config
        self.ai = ai
        self.status_bar = status_bar
        self.refreshing = False
        self.refresh_thread = None
        self.progress = RefreshProgress()

    def should_refresh(self) -> bool:
        """Check if background refresh should be started."""
        if not self.config:
            return False

        # Check if cache file exists
        cache_location = self.config.toolset_manager.toolset_status_location
        if not os.path.exists(cache_location):
            return False

        # Check if we loaded from cache
        loaded_from_cache = getattr(
            self.config.toolset_manager, "_loaded_from_cache", True
        )
        return loaded_from_cache

    def format_progress_message(self) -> Tuple[str, Optional[str]]:
        """Format the current progress for spinner display."""
        base = "Refreshing toolsets..."
        if self.progress.total > 0:
            base = (
                f"Refreshing toolsets... {self.progress.current}/{self.progress.total}"
            )

        right = None
        if self.progress.active:
            first_active = self.progress.active[0]
            if len(self.progress.active) > 1:
                right = f"checking {first_active} +{len(self.progress.active) - 1}"
            else:
                right = f"checking {first_active}"

        return base, right

    def build_completion_message(self, result: RefreshResult) -> List[Tuple[str, str]]:
        """Build styled message parts for completion display."""
        if not result.success:
            # Error message - single red part
            return [
                (
                    "bg:#ff0000 fg:#000000",
                    f"✗ Toolset refresh failed: {result.error or 'Unknown error'}",
                )
            ]

        # Build the success message with styled parts
        styled_parts = [("bg:ansigreen ansiblack", f" {result.total_enabled} ready ")]

        if result.newly_enabled:
            # Show first 3 toolsets by name, then count if more
            names_to_show = sorted(result.newly_enabled)[:3]
            if len(result.newly_enabled) > 3:
                extra_count = len(result.newly_enabled) - 3
                names_display = " ".join(names_to_show) + f" +{extra_count}"
            else:
                names_display = " ".join(names_to_show)
            styled_parts.append(("bg:ansiblue ansiwhite", f" new: {names_display} "))

        if result.newly_disabled:
            # Show first 3 toolsets by name, then count if more
            names_to_show = sorted(result.newly_disabled)[:3]
            if len(result.newly_disabled) > 3:
                extra_count = len(result.newly_disabled) - 3
                names_display = " ".join(names_to_show) + f" +{extra_count}"
            else:
                names_display = " ".join(names_to_show)
            styled_parts.append(
                ("bg:ansired ansiwhite", f" disabled: {names_display} ")
            )

        if not result.newly_enabled and not result.newly_disabled:
            styled_parts.append(("bg:ansibrightblack ansiwhite", " no changes "))

        return styled_parts

    def start_background_refresh(self, status_bar=None):
        """Start background toolset refresh with integrated status bar updates."""
        if not self.should_refresh():
            return

        if self.refreshing:
            return

        self.refreshing = True
        self.progress = RefreshProgress()  # Reset progress

        # Use provided status bar or instance one
        status_bar = status_bar or self.status_bar

        if status_bar:
            # Start spinner with our formatter
            status_bar.start_spinner(self.format_progress_message)

        def progress_callback(current, total, active_checks):
            """Internal callback to update progress."""
            self.progress.current = current
            self.progress.total = total
            self.progress.active = active_checks[:]

        def refresh_worker():
            try:
                # Track what was enabled before refresh
                enabled_before = set()
                if hasattr(self.ai, "tool_executor") and hasattr(
                    self.ai.tool_executor, "toolsets"
                ):
                    enabled_before = set(
                        ts.name
                        for ts in self.ai.tool_executor.toolsets
                        if ts.enabled and ts.status == ToolsetStatusEnum.ENABLED
                    )

                # Suppress logging during background refresh
                self.config.toolset_manager.set_suppress_logging(True)

                # Perform the refresh
                self.config.toolset_manager.refresh_toolset_status(
                    dal=None,
                    enable_all_toolsets=True,
                    toolset_tags=self.config.toolset_manager.cli_tool_tags,
                    progress_callback=progress_callback,
                )

                # Reload toolsets after refresh
                refreshed_toolsets = self.config.toolset_manager.list_console_toolsets(
                    refresh_status=False,  # We just refreshed
                    skip_prerequisite_check=True,  # Already checked during refresh
                )

                # Update the tool executor with refreshed toolsets
                self.ai.tool_executor = ToolExecutor(refreshed_toolsets)

                # Track what's enabled after refresh
                enabled_after = set(
                    ts.name
                    for ts in refreshed_toolsets
                    if ts.enabled and ts.status == ToolsetStatusEnum.ENABLED
                )

                # Build result
                result = RefreshResult(
                    success=True,
                    total_enabled=len(enabled_after),
                    newly_enabled=enabled_after - enabled_before,
                    newly_disabled=enabled_before - enabled_after,
                )

                # Update status bar with completion message
                if status_bar:
                    styled_parts = self.build_completion_message(result)
                    status_bar.show_toolset_complete(styled_parts, duration=5)

            except Exception as e:
                logging.error(f"Background toolset refresh failed: {e}")
                result = RefreshResult(success=False, error=str(e))

                if status_bar:
                    styled_parts = self.build_completion_message(result)
                    status_bar.show_toolset_complete(styled_parts, duration=5)
            finally:
                self.refreshing = False
                # Restore logging
                self.config.toolset_manager.set_suppress_logging(False)

        # Start refresh in background thread
        self.refresh_thread = threading.Thread(target=refresh_worker, daemon=True)
        self.refresh_thread.start()

    def get_cache_info(self) -> Optional[Dict]:
        """Get information about the toolset cache."""
        if not self.config or not hasattr(
            self.config.toolset_manager, "_loaded_from_cache"
        ):
            return None

        if not self.config.toolset_manager._loaded_from_cache:
            return None

        # Get toolset counts
        toolsets = self.ai.tool_executor.toolsets
        enabled_toolsets = [
            t for t in toolsets if t.enabled and t.status == ToolsetStatusEnum.ENABLED
        ]
        disabled_toolsets = [
            t
            for t in toolsets
            if not t.enabled or t.status != ToolsetStatusEnum.ENABLED
        ]

        # Calculate cache age
        cache_timestamp = getattr(self.config.toolset_manager, "_cache_timestamp", 0)
        if cache_timestamp:
            cache_age_seconds = time.time() - cache_timestamp
            cache_age_str = self._format_time_ago(cache_age_seconds)
        else:
            cache_age_str = "unknown time ago"

        return {
            "num_enabled": len(enabled_toolsets),
            "num_disabled": len(disabled_toolsets),
            "cache_age": cache_age_str,
        }

    @staticmethod
    def _format_time_ago(seconds: float) -> str:
        """Format seconds into human-readable time ago string."""
        if seconds < 60:
            s = int(seconds)
            return f"{s} second{'s' if s != 1 else ''} ago"
        elif seconds < 3600:
            m = int(seconds / 60)
            return f"{m} minute{'s' if m != 1 else ''} ago"
        elif seconds < 86400:
            h = int(seconds / 3600)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        else:
            d = int(seconds / 86400)
            return f"{d} day{'s' if d != 1 else ''} ago"
