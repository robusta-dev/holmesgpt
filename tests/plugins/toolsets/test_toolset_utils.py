import pytest
from dateutil import parser
from holmes.plugins.toolsets.utils import process_timestamps_to_rfc3339
from freezegun import freeze_time

class TestProcessTimestamps:


    @freeze_time("2020-09-14T13:50:40+00:00")
    @pytest.mark.parametrize(
        "start_timestamp, end_timestamp, expected_start, expected_end",
        [
            (
                None,
                None,
                "2020-09-14T12:50:40+00:00",
                "2020-09-14T13:50:40+00:00",
            ),
            (
                -7200,
                0, # alias for now()
                "2020-09-14T11:50:40+00:00",
                "2020-09-14T13:50:40+00:00",
            ),
            (
                -7200, # always relative to end
                -1800, # relative to now() when negative
                "2020-09-14T11:20:40+00:00",
                "2020-09-14T13:20:40+00:00",
            ),
            # Integer timestamps
            (
                1600000000,
                1600003600,
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
            ),
            # RFC3339 formatted timestamps
            (
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
            ),
            # Negative start integer as relative time to Unix
            (
                -3600,
                1600003600,
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
            ),
            # Negative start integer as relative time to RFC3339
            (
                -300,
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T12:21:40+00:00",
                "2020-09-13T12:26:40+00:00",
            ),
            # Auto inversion, Negative end integer as relative time to RFC3339
            (
                "2020-09-13T12:26:40+00:00",
                -300,
                "2020-09-13T12:21:40+00:00",
                "2020-09-13T12:26:40+00:00",
            ),
            # Auto-inversion if start is after end
            (
                1600003600,
                1600000000,
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
            ),
            # String integers
            (
                "1600000000",
                "1600003600",
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
            ),
            # Mixed format (RFC3339 + Unix)
            (
                "2020-09-13T12:26:40+00:00",
                1600003600,
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
            ),
            # Mixed format (Unix + RFC3339)
            (
                1600000000,
                "2020-09-13T13:26:40+00:00",
                "2020-09-13T12:26:40+00:00",
                "2020-09-13T13:26:40+00:00",
            ),
        ],
    )
    def test_process_timestamps_to_rfc3339(
        self, start_timestamp, end_timestamp, expected_start, expected_end
    ):
        result_start, result_end = process_timestamps_to_rfc3339(
            start_timestamp, end_timestamp
        )

        # For time-dependent tests, we allow a small tolerance
        if start_timestamp is None or end_timestamp is None:
            # Parse the times to compare them within a small tolerance
            result_start_dt = parser.parse(result_start)
            result_end_dt = parser.parse(result_end)
            expected_start_dt = parser.parse(expected_start)
            expected_end_dt = parser.parse(expected_end)

            # Allow 2 seconds tolerance for current time comparisons
            assert abs((result_start_dt - expected_start_dt).total_seconds()) < 2
            assert abs((result_end_dt - expected_end_dt).total_seconds()) < 2
        else:
            assert result_start == expected_start
            assert result_end == expected_end
