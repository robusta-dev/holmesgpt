"""Toolset refresh management for interactive mode."""

import logging
import os
import threading
import time
from typing import Callable, Optional, Dict

from holmes.core.tools import ToolsetStatusEnum
from holmes.core.tools_utils.tool_executor import ToolExecutor


class ToolsetRefreshManager:
    """Manages background toolset refresh operations."""

    def __init__(self, config, ai):
        self.config = config
        self.ai = ai
        self.refreshing = False
        self.refresh_thread = None

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

    def start_background_refresh(
        self,
        progress_callback: Optional[Callable] = None,
        completion_callback: Optional[Callable] = None,
    ):
        """Start background toolset refresh if appropriate."""
        if not self.should_refresh():
            return

        if self.refreshing:
            return

        self.refreshing = True

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

                # Calculate changes
                newly_enabled = enabled_after - enabled_before
                newly_disabled = enabled_before - enabled_after

                # Call completion callback with results
                if completion_callback:
                    completion_callback(
                        {
                            "success": True,
                            "total_enabled": len(enabled_after),
                            "newly_enabled": newly_enabled,
                            "newly_disabled": newly_disabled,
                        }
                    )

            except Exception as e:
                logging.error(f"Background toolset refresh failed: {e}")
                if completion_callback:
                    completion_callback({"success": False, "error": str(e)})
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
