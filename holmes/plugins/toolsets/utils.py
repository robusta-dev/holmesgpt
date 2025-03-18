import datetime
from typing import Dict, Optional, Tuple, Union
from dateutil import parser
import time

ONE_HOUR_IN_SECONDS = 3600


def is_int(string):
    try:
        int(string)
    except ValueError:
        return False
    else:
        return True


def is_rfc3339(timestamp_str: str) -> bool:
    """Check if a string is in RFC3339 format."""
    try:
        parser.parse(timestamp_str)
        return True
    except (ValueError, TypeError):
        return False


def rfc3339_to_unix(timestamp_str: str) -> int:
    dt = parser.parse(timestamp_str)
    return int(dt.timestamp())


def datetime_to_unix(timestamp_or_datetime_str):
    if timestamp_or_datetime_str and is_int(timestamp_or_datetime_str):
        return int(timestamp_or_datetime_str)
    elif isinstance(timestamp_or_datetime_str, str) and is_rfc3339(
        timestamp_or_datetime_str
    ):
        return rfc3339_to_unix(timestamp_or_datetime_str)
    else:
        return timestamp_or_datetime_str


def unix_to_rfc3339(timestamp: int) -> str:
    dt = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    return dt.isoformat()


def datetime_to_rfc3339(timestamp):
    if isinstance(timestamp, int):
        return unix_to_rfc3339(timestamp)
    else:
        return timestamp


def process_timestamps(
    start_timestamp: Optional[Union[int, str]], end_timestamp: Optional[Union[int, str]]
) -> Tuple[str, str]:
    """
    Process and normalize start and end timestamps.

    Supports:
    - Integer timestamps (Unix time)
    - RFC3339 formatted timestamps
    - Negative integers as relative time from the other timestamp
    - Auto-inversion if start is after end

    Returns:
        Tuple of (start_timestamp, end_timestamp)
    """
    # If no end_timestamp provided, use current time
    if not end_timestamp:
        end_timestamp = int(time.time())

    # If no start_timestamp provided, default to one hour before end
    if not start_timestamp:
        start_timestamp = -ONE_HOUR_IN_SECONDS

    start_timestamp = datetime_to_unix(start_timestamp)
    end_timestamp = datetime_to_unix(end_timestamp)

    # Handle negative timestamps (relative to the other timestamp)
    if isinstance(start_timestamp, int) and isinstance(end_timestamp, int):
        if start_timestamp < 0 and end_timestamp < 0:
            raise ValueError(
                f"Both start_timestamp and end_timestamp cannot be negative. Received start_timestamp={start_timestamp} and end_timestamp={end_timestamp}"
            )
        elif start_timestamp < 0:
            start_timestamp = end_timestamp + start_timestamp
        elif end_timestamp < 0:
            # start/end are inverted. end_timestamp should be after start_timestamp
            delta = end_timestamp
            end_timestamp = start_timestamp
            start_timestamp = start_timestamp + delta

    # Invert timestamps if start is after end
    if (
        isinstance(start_timestamp, int)
        and isinstance(end_timestamp, int)
        and start_timestamp > end_timestamp
    ):
        start_timestamp, end_timestamp = end_timestamp, start_timestamp

    # Convert timestamps to RFC3399 because APIs support it and it's
    # more human readable than timestamps
    start_timestamp = datetime_to_rfc3339(start_timestamp)
    end_timestamp = datetime_to_rfc3339(end_timestamp)

    return (start_timestamp, end_timestamp)


def get_param_or_raise(dict: Dict, param: str) -> str:
    value = dict.get(param)
    if not value:
        raise Exception(f'Missing param "{param}"')
    return value
