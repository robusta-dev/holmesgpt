"""Tests for parse_time_duration function"""

import pytest
from freezegun import freeze_time

from holmes.plugins.toolsets.utils import parse_time_duration


class TestParseTimeDuration:
    """Test parse_time_duration function"""

    def test_relative_durations(self):
        """Test parsing relative duration strings"""
        # Test weeks
        assert parse_time_duration("1w") == 604800  # 7 days
        assert parse_time_duration("2w") == 1209600  # 14 days

        # Test days
        assert parse_time_duration("1d") == 86400  # 1 day
        assert parse_time_duration("7d") == 604800  # 7 days

        # Test hours
        assert parse_time_duration("1h") == 3600  # 1 hour
        assert parse_time_duration("24h") == 86400  # 24 hours

        # Test minutes
        assert parse_time_duration("1m") == 60  # 1 minute
        assert parse_time_duration("30m") == 1800  # 30 minutes

        # Test seconds
        assert parse_time_duration("1s") == 1  # 1 second
        assert parse_time_duration("100s") == 100  # 100 seconds

    def test_case_insensitive(self):
        """Test that relative durations are case insensitive"""
        assert parse_time_duration("1W") == 604800
        assert parse_time_duration("1D") == 86400
        assert parse_time_duration("1H") == 3600

    def test_whitespace_handling(self):
        """Test that whitespace is stripped"""
        assert parse_time_duration(" 1d ") == 86400
        assert parse_time_duration("\t2w\n") == 1209600

    @freeze_time("2024-01-15 10:30:00", tz_offset=0)
    def test_iso_date(self):
        """Test parsing ISO date format"""
        # Yesterday
        result = parse_time_duration("2024-01-14")
        # Should be from midnight of 2024-01-14 to now (2024-01-15 10:30:00)
        # That's 1 day + 10.5 hours = 1.4375 days = 124200 seconds
        assert result == 124200

        # A week ago
        result = parse_time_duration("2024-01-08")
        # 7 days + 10.5 hours = 7.4375 days = 642600 seconds
        assert result == 642600

    @freeze_time("2024-01-15 10:30:00", tz_offset=0)
    def test_iso_datetime(self):
        """Test parsing ISO datetime format"""
        # Exactly 1 day ago
        result = parse_time_duration("2024-01-14T10:30:00")
        assert result == 86400

        # With Z timezone
        result = parse_time_duration("2024-01-14T10:30:00Z")
        assert result == 86400

        # 2 days and 3 hours ago
        result = parse_time_duration("2024-01-13T07:30:00")
        assert result == 183600  # 2 days + 3 hours

    @freeze_time("2024-01-15 14:30:00", tz_offset=0)
    def test_time_only(self):
        """Test parsing time-only format"""
        # Earlier today (10:30)
        result = parse_time_duration("10:30")
        assert result == 14400  # 4 hours

        # With seconds
        result = parse_time_duration("10:30:00")
        assert result == 14400  # 4 hours

        # Time that would be in the future today (should use yesterday)
        result = parse_time_duration("16:30")
        # Yesterday at 16:30 to today at 14:30 = 22 hours
        assert result == 79200

    def test_invalid_formats(self):
        """Test that invalid formats raise ValueError"""
        invalid_inputs = [
            "2.5h",  # Decimal not supported
            "abc",  # Random text
            "10",  # Just a number
            "w",  # Just a unit
            "",  # Empty string
            "1x",  # Invalid unit
            "2024-13-01",  # Invalid month
            "25:00",  # Invalid hour
            "2024-01-32",  # Invalid day
        ]

        for invalid in invalid_inputs:
            with pytest.raises(ValueError) as exc_info:
                parse_time_duration(invalid)
            assert "Invalid time format" in str(exc_info.value)

    @freeze_time("2024-01-15 10:30:00", tz_offset=0)
    def test_future_time_raises_error(self):
        """Test that future times raise ValueError"""
        # Tomorrow
        with pytest.raises(ValueError) as exc_info:
            parse_time_duration("2024-01-16")
        assert "in the future" in str(exc_info.value)

        # Later today (when it's actually in the future)
        with pytest.raises(ValueError) as exc_info:
            parse_time_duration("2024-01-15T15:00:00")
        assert "in the future" in str(exc_info.value)

    def test_large_values(self):
        """Test parsing large values"""
        # 52 weeks (1 year)
        assert parse_time_duration("52w") == 31449600

        # 365 days
        assert parse_time_duration("365d") == 31536000

        # 8760 hours (365 days)
        assert parse_time_duration("8760h") == 31536000

    @freeze_time("2024-01-15 10:30:00", tz_offset=0)
    def test_timezone_handling(self):
        """Test that timezone handling works correctly"""
        # UTC explicitly
        result = parse_time_duration("2024-01-14T10:30:00Z")
        assert result == 86400

        # With offset
        result = parse_time_duration("2024-01-14T10:30:00+00:00")
        assert result == 86400

    def test_edge_cases(self):
        """Test edge cases"""
        # Zero values
        assert parse_time_duration("0s") == 0
        assert parse_time_duration("0m") == 0
        assert parse_time_duration("0h") == 0
        assert parse_time_duration("0d") == 0
        assert parse_time_duration("0w") == 0
