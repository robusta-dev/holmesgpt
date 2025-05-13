import pytest

from holmes.plugins.toolsets.kubernetes_logs import (
    filter_log_lines_by_timestamp_and_strip_prefix,
)
from holmes.plugins.toolsets.utils import to_unix

# Helper timestamps for clarity in tests
T1 = "2024-01-15T10:00:00Z"
T2 = "2024-01-15T10:00:01.123Z"
T3 = "2024-01-15T10:00:01.123456789Z"
T4 = "2024-01-15T10:00:02Z"
T5 = "2024-01-15T10:00:03.5Z"
T6 = "2024-01-15T10:00:04Z"

# Convert helper timestamps to Unix
T1_UNIX = to_unix(T1)
T2_UNIX = to_unix(T2)
T3_UNIX = to_unix(T3)  # Same second as T2
T4_UNIX = to_unix(T4)
T5_UNIX = to_unix(T5)
T6_UNIX = to_unix(T6)

# Test data using these timestamps
LOGS_BASIC = [
    f"{T1} Log before range",
    f"{T2}  Log at start boundary (subsecond)",  # Note leading space after timestamp
    f"{T3} Log also at start boundary (high precision)",
    f"{T4} Log inside range",
    f"{T5} Log at end boundary",
    f"{T6} Log after range",
    "Plain message without timestamp",
    f"{T4} Another log inside range",  # Duplicate time, different message
]

# Expected results for specific ranges (stripping timestamp and leading space)
EXPECTED_T2_T5 = [
    "Log at start boundary (subsecond)",
    "Log also at start boundary (high precision)",
    "Log inside range",
    "Log at end boundary",
    "Another log inside range",
]

EXPECTED_T4_ONLY = [
    "Log inside range",
    "Another log inside range",
]


@pytest.mark.parametrize(
    "test_name, logs_input, start_ts, end_ts, expected_output",
    [
        (
            "basic_range",
            LOGS_BASIC,
            T2_UNIX,  # Includes T2 and T3 because they round to the same Unix second
            T5_UNIX,
            EXPECTED_T2_T5,
        ),
        ("narrow_range", LOGS_BASIC, T4_UNIX, T4_UNIX, EXPECTED_T4_ONLY),
        (
            "range_before_all",
            LOGS_BASIC,
            T1_UNIX - 10,  # 10 seconds before T1
            T1_UNIX - 5,  # 5 seconds before T1
            [],
        ),
        (
            "range_after_all",
            LOGS_BASIC,
            T6_UNIX + 5,  # 5 seconds after T6
            T6_UNIX + 10,  # 10 seconds after T6
            [],
        ),
        (
            "full_range_covering_all",
            LOGS_BASIC,
            T1_UNIX,
            T6_UNIX,
            [  # Expected: All logs with timestamps, stripped
                "Log before range",
                "Log at start boundary (subsecond)",
                "Log also at start boundary (high precision)",
                "Log inside range",
                "Log at end boundary",
                "Log after range",
                "Another log inside range",
            ],
        ),
        ("empty_log_list", [], T1_UNIX, T6_UNIX, []),
        (
            "logs_with_only_no_prefix",
            ["INFO: Starting process", "WARN: Low disk space"],
            T1_UNIX,
            T6_UNIX,
            [],  # Lines without prefix are skipped
        ),
        (
            "logs_with_leading_whitespace_after_ts",
            [f"{T4}   Notice the three spaces here"],  # 3 spaces
            T4_UNIX,
            T4_UNIX,
            ["Notice the three spaces here"],  # Spaces should be stripped
        ),
        ("log_with_no_subseconds", [f"{T4} Message"], T4_UNIX, T4_UNIX, ["Message"]),
    ],
    ids=[  # Optional: Provides clearer names for parametrized tests in output
        "basic_range",
        "narrow_range",
        "range_before_all",
        "range_after_all",
        "full_range_covering_all",
        "empty_log_list",
        "logs_with_only_no_prefix",
        "leading_whitespace_handling",
        "no_subseconds_handling",
    ],
)
def test_filtering_scenarios(test_name, logs_input, start_ts, end_ts, expected_output):
    result = filter_log_lines_by_timestamp_and_strip_prefix(
        logs_input, start_ts, end_ts
    )
    assert result == expected_output


def test_non_string_input_handling():
    logs_mixed = [
        f"{T4} Valid log line",
        None,  # Non-string item
        f"{T5} Another valid log",
        12345,  # Another non-string
        "Line without timestamp",
        f"{T6} Log outside range",
    ]
    start_ts = T4_UNIX
    end_ts = T5_UNIX

    expected = [
        "Valid log line",
        None,
        "Another valid log",
        12345,
    ]
    result = filter_log_lines_by_timestamp_and_strip_prefix(
        logs_mixed, start_ts, end_ts
    )
    assert result == expected


def test_parsing_error_handling():
    """
    Tests the behavior when regex matches but timestamp parsing fails.
    NOTE: Simulating this requires a state where regex matches but fromisoformat fails.
    A slightly malformed string might achieve this, or we assume it *could* happen.
    The current code appends the *original* line in case of ValueError.
    """
    # Let's manually create a scenario assuming regex passed but date is invalid
    # (In reality, a good regex might prevent this, but we test the code's path)
    # We'll mock the behavior by modifying the function slightly for this test case,
    # or create input known to cause ValueError *after* regex match if possible.

    # Using a date that might be invalid for fromisoformat but resembles the pattern
    # Feb 30 doesn't exist. Let's see if fromisoformat catches it after regex.
    invalid_date_log = "2024-02-30T10:00:00Z Invalid Date Log"

    logs_with_bad_parse = [
        f"{T4} Good log 1",
        invalid_date_log,  # This should cause ValueError in fromisoformat
        f"{T5} Good log 2",
    ]
    start_ts = T4_UNIX
    end_ts = T5_UNIX

    # Expected: Good logs are processed, the bad one is appended *unmodified*
    # because of the `except ValueError: filtered_lines_content.append(line)`
    expected = [
        "Good log 1",
        invalid_date_log,  # The original line is kept on parse error
        "Good log 2",
    ]

    result = filter_log_lines_by_timestamp_and_strip_prefix(
        logs_with_bad_parse, start_ts, end_ts
    )
    assert result == expected
