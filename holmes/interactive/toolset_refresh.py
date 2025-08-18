"""Toolset refresh management for interactive mode."""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Set, List, Tuple

from holmes.core.tools import ToolsetStatusEnum
from holmes.core.tools_utils.tool_executor import ToolExecutor
from holmes.core.toolset_manager import DEFAULT_TOOLSET_STATUS_LOCATION


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

    def __init__(self, ai, toolset_manager, status_bar=None, loaded_from_cache=False):
        self.ai = ai
        self.toolset_manager = toolset_manager
        self.status_bar = status_bar
        self.refreshing = False
        self.refresh_thread = None
        self.progress = RefreshProgress()
        # Track if initial load was from cache
        self.loaded_from_cache = loaded_from_cache

    def should_refresh(self) -> bool:
        """Check if background refresh should be started."""
        # Only refresh if we actually loaded from cache
        return self.loaded_from_cache

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
                enabled_before = set(
                    ts.name
                    for ts in self.ai.tool_executor.toolsets
                    if ts.enabled and ts.status == ToolsetStatusEnum.ENABLED
                )

                # Suppress logging during background refresh
                self.toolset_manager.set_suppress_logging(True)

                # Perform the refresh
                refreshed_toolsets = self.toolset_manager.load(
                    use_cache=False, progress_callback=progress_callback
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
                self.toolset_manager.set_suppress_logging(False)

        # Start refresh in background thread
        self.refresh_thread = threading.Thread(target=refresh_worker, daemon=True)
        self.refresh_thread.start()

    def get_cache_info(self) -> Optional[Dict]:
        """Get information about the toolset cache."""
        cache_timestamp = self._read_cache_timestamp()
        if not cache_timestamp:
            return None

        toolsets = self.ai.tool_executor.toolsets
        enabled_count = sum(
            1 for t in toolsets if t.enabled and t.status == ToolsetStatusEnum.ENABLED
        )

        return {
            "num_enabled": enabled_count,
            "num_disabled": len(toolsets) - enabled_count,
            "cache_age": self._format_time_ago(time.time() - cache_timestamp),
        }

    @staticmethod
    def _read_cache_timestamp() -> Optional[float]:
        """Read timestamp from cache file. Returns None if cache doesn't exist."""
        if not os.path.exists(DEFAULT_TOOLSET_STATUS_LOCATION):
            return None
        try:
            with open(DEFAULT_TOOLSET_STATUS_LOCATION) as f:
                cache_data = json.load(f)
                return cache_data.get("_timestamp", 0) or None
        except (json.JSONDecodeError, IOError):
            return None

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
