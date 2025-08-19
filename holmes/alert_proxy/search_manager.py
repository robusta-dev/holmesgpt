"""
Search functionality for the alert interactive view.
Handles search state, filtering, and search UI updates.
"""

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from holmes.alert_proxy.models import EnrichedAlert


class SearchManager:
    """Manages search state and filtering for alerts.

    Note: The selected index is managed by the view (AlertUIView).
    This class only handles search/filter functionality.
    """

    def __init__(self) -> None:
        """Initialize search manager."""
        self.search_active = False  # True when typing search
        self.search_filter = ""  # Applied search filter (persists after Enter)
        self.search_query = ""  # Current search being typed
        self.search_matches: List[int] = []  # List of matching alert indices

    def start_search(self, current_filter: str = "") -> bool:
        """
        Start search mode.

        Args:
            current_filter: Existing filter to start with

        Returns:
            True if search started successfully, False if already searching
        """
        # Prevent starting new search if already active
        if self.search_active:
            return False

        self.search_active = True
        self.search_query = current_filter or self.search_filter
        self.search_matches = []
        return True

    def cancel_search(self) -> tuple[str, List[int]]:
        """
        Cancel search and clear all filters.

        Returns:
            Tuple of (status_message, search_matches)
        """
        # Clear everything in one go
        self.search_active = False
        self.search_query = ""
        self.search_filter = ""
        self.search_matches = []

        return ("", [])

    def apply_filter(self) -> tuple[str, bool]:
        """
        Apply search as a persistent filter and exit search mode.

        Returns:
            Tuple of (status_message, has_filter)
        """
        self.search_active = False
        self.search_filter = self.search_query  # Save as persistent filter

        # Generate status message
        if self.search_filter:
            if self.search_matches:
                status = f"Filter: '{self.search_filter}' ({len(self.search_matches)} matches)"
            else:
                status = f"Filter: '{self.search_filter}' (no matches)"
            return (status, True)
        else:
            return ("", False)

    def update_search(
        self, query: str, alerts: List["EnrichedAlert"]
    ) -> tuple[List[int], Optional[int]]:
        """
        Update search query and find matches.

        Args:
            query: Search query string
            alerts: List of alerts to search through

        Returns:
            Tuple of (matching_indices, first_match_index_or_none)
        """
        self.search_query = query.lower()
        self.search_matches = []

        if not self.search_query:
            return (self.search_matches, None)

        # Search through alerts - only match on alertname
        for i, alert in enumerate(alerts):
            alert_name = alert.original.labels.get("alertname", "").lower()

            # Check if query matches alert name only
            if self.search_query in alert_name:
                self.search_matches.append(i)

        # Return first match for jumping
        first_match = self.search_matches[0] if self.search_matches else None
        return (self.search_matches, first_match)

    def get_search_status(self) -> str:
        """
        Get current search status for display.

        Returns:
            Status message for the UI
        """
        if self.search_active:
            if self.search_query:
                return f"Search: '{self.search_query}' ({len(self.search_matches)} matches) - Enter to apply, ESC to cancel"
            else:
                return (
                    "Search: (type to search alertname, Enter to apply, ESC to cancel)"
                )
        elif self.search_filter:
            # Show active filter status
            if self.search_matches:
                return f"Filter: '{self.search_filter}' ({len(self.search_matches)} matches)"
            else:
                return f"Filter: '{self.search_filter}' (no matches)"
        return ""

    def add_character(self, char: str) -> None:
        """
        Add a character to the search query.

        Args:
            char: Character to add
        """
        if char and char.isprintable():
            self.search_query += char

    def remove_character(self) -> None:
        """Remove the last character from search query."""
        if self.search_query:
            self.search_query = self.search_query[:-1]

    def get_filtered_alerts(
        self, alerts: List["EnrichedAlert"]
    ) -> tuple[List["EnrichedAlert"], List[int]]:
        """
        Filter alerts based on current search/filter state.

        Args:
            alerts: Full list of alerts

        Returns:
            Tuple of (filtered_alerts, original_indices)
        """
        # Use search_filter if not actively searching, otherwise use search_query
        active_filter = self.search_query if self.search_active else self.search_filter

        if not active_filter:
            # No filter - return all alerts
            return (alerts, list(range(len(alerts))))

        # Apply the filter
        visible_alerts = []
        visible_indices = []

        for i, alert in enumerate(alerts):
            alert_name = alert.original.labels.get("alertname", "").lower()
            if active_filter.lower() in alert_name:
                visible_alerts.append(alert)
                visible_indices.append(i)

        return (visible_alerts, visible_indices)

    def get_no_matches_message(self) -> str:
        """
        Get message to display when no alerts match the filter.

        Returns:
            User-friendly message about no matches
        """
        active_filter = self.search_query if self.search_active else self.search_filter
        return f"\n  No alerts match: '{active_filter}'\n  Press ESC to clear filter or / to search again"

    def is_active(self) -> bool:
        """Check if search is currently active."""
        return self.search_active

    def has_filter(self) -> bool:
        """Check if a filter is currently applied."""
        return bool(self.search_filter)

    def get_current_filter(self) -> str:
        """Get the current active filter or search query."""
        return self.search_query if self.search_active else self.search_filter
