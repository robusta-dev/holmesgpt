"""
Tests for sort CLI command parsing, validation, and stringification.
"""

import pytest
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


class TestSortCliSafeCommands:
    """Test sort CLI safe commands that should be allowed."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Basic sorting
            ("sort", "sort"),
            ("sort -n", "sort -n"),
            ("sort --numeric-sort", "sort --numeric-sort"),
            ("sort -r", "sort -r"),
            ("sort --reverse", "sort --reverse"),
            # Key-based sorting
            ("sort -k1,1", "sort -k1,1"),
            ("sort -k2,2n", "sort -k2,2n"),
            ("sort --key=1,1", "sort --key=1,1"),
            ("sort -t: -k1,1", "sort -t: -k1,1"),
            ("sort --field-separator=: -k1,1", "sort --field-separator=: -k1,1"),
            # Sort modes
            ("sort -u", "sort -u"),
            ("sort --unique", "sort --unique"),
            ("sort -M", "sort -M"),
            ("sort --month-sort", "sort --month-sort"),
            ("sort -V", "sort -V"),
            ("sort --version-sort", "sort --version-sort"),
            ("sort -h", "sort -h"),
            ("sort --human-numeric-sort", "sort --human-numeric-sort"),
            ("sort -R", "sort -R"),
            ("sort --random-sort", "sort --random-sort"),
            # Additional options
            ("sort -b", "sort -b"),
            ("sort --ignore-leading-blanks", "sort --ignore-leading-blanks"),
            ("sort -f", "sort -f"),
            ("sort --ignore-case", "sort --ignore-case"),
            ("sort -s", "sort -s"),
            ("sort --stable", "sort --stable"),
            ("sort -z", "sort -z"),
            ("sort --zero-terminated", "sort --zero-terminated"),
            # Combined options
            ("sort -nr", "sort -nr"),
            ("sort -t, -k2,2n -r", "sort -t, -k2,2n -r"),
            # Help and version
            ("sort --help", "sort --help"),
            ("sort --version", "sort --version"),
        ],
    )
    def test_safe_sort_commands(self, input_command, expected_output):
        """Test that safe sort commands are parsed and stringified correctly."""
        result = make_command_safe(input_command, None)
        assert result == expected_output


class TestSortCliUnsafeCommands:
    """Test sort CLI unsafe commands that should be blocked."""

    @pytest.mark.parametrize(
        "input_command,expected_error_message",
        [
            # Temporary directory options are blocked
            ("sort -T /tmp", "Option -T is not allowed for security reasons"),
            (
                "sort --temporary-directory=/tmp",
                "Option --temporary-directory is not allowed for security reasons",
            ),
            # File arguments are not allowed
            ("sort file1.txt", "File arguments are not allowed"),
            ("sort -n file1.txt file2.txt", "File arguments are not allowed"),
        ],
    )
    def test_unsafe_sort_commands(self, input_command, expected_error_message):
        """Test that unsafe sort commands are blocked with appropriate error messages."""
        with pytest.raises(ValueError, match=expected_error_message):
            make_command_safe(input_command, None)
