"""
Tests for awk CLI command parsing, validation, and stringification.
"""

import pytest
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


class TestAwkCliSafeCommands:
    """Test awk CLI safe commands that should be allowed."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic programs
            ("awk '{print}'", "awk {print}"),
            ("awk '{print $1}'", "awk '{print $1}'"),
            ("awk '{print $1, $2}'", "awk '{print $1, $2}'"),
            ("awk '/pattern/ {print}'", "awk '/pattern/ {print}'"),
            # Field separator
            ("awk -F: '{print $1}'", "awk -F: '{print $1}'"),
            (
                "awk --field-separator=, '{print $2}'",
                "awk --field-separator=, '{print $2}'",
            ),
            ("awk -F'\\t' '{print $1}'", "awk -F'\\t' '{print $1}'"),
            # Variable assignments
            ("awk -v name=value '{print name}'", "awk -v name=value '{print name}'"),
            (
                "awk --assign count=10 '{print count}'",
                "awk --assign count=10 '{print count}'",
            ),
            # Pattern matching and conditions
            ("awk '$1 > 100 {print}'", "awk '$1 > 100 {print}'"),
            ("awk 'NR == 1 {print}'", "awk 'NR == 1 {print}'"),
            ("awk 'length($0) > 80'", "awk 'length($0) > 80'"),
            # Built-in functions
            ("awk '{print length($0)}'", "awk '{print length($0)}'"),
            ("awk '{print substr($0, 1, 10)}'", "awk '{print substr($0, 1, 10)}'"),
            ("awk '{print toupper($1)}'", "awk '{print toupper($1)}'"),
            (
                "awk '{print gsub(/old/, \"new\")}'",
                "awk '{print gsub(/old/, \"new\")}'",
            ),
            # Mathematical operations
            ("awk '{sum += $1} END {print sum}'", "awk '{sum += $1} END {print sum}'"),
            ("awk '{print $1 * 2}'", "awk '{print $1 * 2}'"),
            # BEGIN and END blocks
            (
                'awk \'BEGIN {print "Start"} {print} END {print "End"}\'',
                'awk \'BEGIN {print "Start"} {print} END {print "End"}\'',
            ),
            # Help and version
            ("awk --help", "awk --help"),
            ("awk --version", "awk --version"),
        ],
    )
    def test_safe_awk_commands(self, input_command, expected_output):
        """Test that safe awk commands are parsed and stringified correctly."""
        result = make_command_safe(input_command, None)
        assert result == expected_output


class TestAwkCliUnsafeCommands:
    """Test awk CLI unsafe commands that should be blocked."""

    @pytest.mark.parametrize(
        "input_command,expected_error_message",
        [
            # File/execution options are blocked
            ("awk -f script.awk", "Option -f is not allowed for security reasons"),
            (
                "awk --file=script.awk",
                "Option --file is not allowed for security reasons",
            ),
            ("awk -E 'print'", "Option -E is not allowed for security reasons"),
            ("awk --exec 'print'", "Option --exec is not allowed for security reasons"),
            ("awk -i include.awk", "Option -i is not allowed for security reasons"),
            (
                "awk --include=include.awk",
                "Option --include is not allowed for security reasons",
            ),
            ("awk -l extension", "Option -l is not allowed for security reasons"),
            (
                "awk --load-extension=extension",
                "Option --load-extension is not allowed for security reasons",
            ),
            # Dangerous functions in programs
            (
                "awk '{system(\"ls\")}'",
                "awk program contains blocked functions or operations",
            ),
            (
                "awk '{print | \"mail user@domain\"}'",
                "awk program contains blocked functions or operations",
            ),
            (
                "awk '{\"date\" | getline}'",
                "awk program contains blocked functions or operations",
            ),
            (
                "awk '{print > \"/tmp/file\"}'",
                "awk program contains file/pipe output operations",
            ),
            (
                'awk \'{printf "data" > "file.txt"}\'',
                "awk program contains file/pipe output operations",
            ),
        ],
    )
    def test_unsafe_awk_commands(self, input_command, expected_error_message):
        """Test that unsafe awk commands are blocked with appropriate error messages."""
        with pytest.raises(ValueError, match=expected_error_message):
            make_command_safe(input_command, None)
