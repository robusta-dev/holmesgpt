# type: ignore
import pytest

from holmes.core.tools import ToolsetStatusEnum
from tests.llm.utils.mock_toolset import MockToolsets, sanitize_filename


class TestSanitizeFilename:
    @pytest.mark.parametrize(
        "input_filename,expected",
        [
            # Basic cases
            ("normal_filename.txt", "normal_filename.txt"),
            ("simple-name", "simple-name"),
            ("123_abc", "123_abc"),
            # URL scheme removal
            ("http://example.com/file.txt", "example.com_file.txt"),
            ("https://example.com/file.txt", "example.com_file.txt"),
            ("HTTP://EXAMPLE.COM/FILE.TXT", "EXAMPLE.COM_FILE.TXT"),
            ("HTTPS://EXAMPLE.COM/FILE.TXT", "EXAMPLE.COM_FILE.TXT"),
            # URL decoding
            ("file%20name.txt", "file_name.txt"),
            ("path%2Fto%2Ffile.txt", "path_to_file.txt"),
            ("query%3Fparam%3Dvalue", "query_param_value"),
            # Datetime
            (
                "statefulset-logs_2025-06-12T05:58:20Z",
                "statefulset-logs_2025-06-12T05_58_20Z",
            ),
            # Special characters replacement
            ("file with spaces.txt", "file_with_spaces.txt"),
            ("file/with/slashes", "file_with_slashes"),
            ("file\\with\\backslashes", "file_with_backslashes"),
            ("file:with:colons", "file_with_colons"),
            ("file*with*stars", "file_with_stars"),
            ("file?with?questions", "file_with_questions"),
            ('file"with"quotes', "file_with_quotes"),
            ("file<with>brackets", "file_with_brackets"),
            ("file|with|pipes", "file_with_pipes"),
            # Multiple consecutive underscores
            ("file___with___multiple___underscores", "file_with_multiple_underscores"),
            ("file____many____underscores", "file_many_underscores"),
            # Leading/trailing underscores and dots
            ("_leading_underscore", "leading_underscore"),
            ("trailing_underscore_", "trailing_underscore"),
            ("__multiple__leading__", "multiple_leading"),
            ("__trailing__multiple__", "trailing_multiple"),
            (".leading.dot", "leading.dot"),
            ("trailing.dot.", "trailing.dot"),
            ("...multiple...dots...", "multiple...dots"),
            # Case conversion
            ("UPPERCASE.TXT", "UPPERCASE.TXT"),
            ("MixedCase.File", "MixedCase.File"),
            # Combined scenarios
            (
                "https://example.com/My%20File%20Name.txt",
                "example.com_My_File_Name.txt",
            ),
            (
                "HTTP://SITE.COM/PATH/TO/FILE%20WITH%20SPACES.PDF",
                "SITE.COM_PATH_TO_FILE_WITH_SPACES.PDF",
            ),
            ("file___with***many!!!special@@@chars", "file_with_many_special_chars"),
            # Edge cases
            ("", ""),
            (".", ""),
            ("_", ""),
            ("__", ""),
            ("...", ""),
            ("___", ""),
            ("_._", ""),
            # Only allowed characters
            ("abc123_-.", "abc123_-"),
            ("test.file-name_123", "test.file-name_123"),
            # Complex URL with query parameters
            (
                "https://api.example.com/v1/users?id=123&name=John%20Doe",
                "api.example.com_v1_users_id_123_name_John_Doe",
            ),
        ],
    )
    def test_sanitize_filename(self, input_filename, expected):
        """Test sanitize_filename with various input scenarios."""
        result = sanitize_filename(input_filename)
        assert result == expected


def assert_toolset_enabled(mock_toolsets: MockToolsets, toolset_name: str):
    for toolset in mock_toolsets.enabled_toolsets:
        if toolset.name == toolset_name:
            assert (
                toolset.status == ToolsetStatusEnum.ENABLED
            ), f"Expected toolset {toolset_name} to be enabled but it is disabled"
            return
    assert False, f"Expected toolset {toolset_name} to be enabled but it missing from the list of enabled toolsets"


@pytest.mark.skip(reason="Test fail on github because kubernetes is not available")
def test_enabled_toolsets():
    # This test ensures `MockToolsets` behaves like HolmesGPT and that it returns the same
    # list of enabled toolsets as HolmesGPT in production
    mock_toolsets = MockToolsets(
        test_case_folder="../fixtures/test_ask_holmes/01_how_many_pods"
    )
    # These toolsets are expected to be enabled by default
    # If this changes it's ok to update the list below
    assert_toolset_enabled(mock_toolsets, "kubernetes/core")
    assert_toolset_enabled(mock_toolsets, "kubernetes/logs")
    assert_toolset_enabled(mock_toolsets, "internet")
