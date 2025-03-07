import pytest
from dateutil import parser
from holmes.plugins.toolsets.grafana.common import process_timestamps


class TestProcessTimestamps:
    @pytest.mark.parametrize(
        "start_timestamp, end_timestamp, expected_start, expected_end",
        [
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
    def test_process_timestamps(
        self, start_timestamp, end_timestamp, expected_start, expected_end
    ):
        result_start, result_end = process_timestamps(start_timestamp, end_timestamp)

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
