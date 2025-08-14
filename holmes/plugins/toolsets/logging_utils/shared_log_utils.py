import re
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from holmes.plugins.toolsets.logging_utils.logging_api import (
    FetchPodLogsParams,
    DEFAULT_TIME_SPAN_SECONDS,
)
from holmes.plugins.toolsets.utils import process_timestamps_to_int


class StructuredLog(BaseModel):
    timestamp_ms: Optional[int]
    container: Optional[str]
    content: str


class TimeFilter(BaseModel):
    start_ms: int
    end_ms: int


def filter_logs(
    logs: List[StructuredLog], params: FetchPodLogsParams
) -> Tuple[List[StructuredLog], int, bool, bool, int, int]:
    """
    Filter logs based on parameters from FetchPodLogsParams.

    Returns:
        - filtered_logs: List of logs after filtering
        - filtered_count_before_limit: Count of logs before applying limit
        - used_substring_fallback: Whether regex fallback to substring was used for filter
        - exclude_used_substring_fallback: Whether regex fallback was used for exclude_filter
        - removed_by_include_filter: Count of logs removed by include filter
        - removed_by_exclude_filter: Count of logs removed by exclude filter
    """
    time_filter: Optional[TimeFilter] = None
    if params.start_time or params.end_time:
        start, end = process_timestamps_to_int(
            start=params.start_time,
            end=params.end_time,
            default_time_span_seconds=DEFAULT_TIME_SPAN_SECONDS,
        )
        time_filter = TimeFilter(start_ms=start * 1000, end_ms=end * 1000)

    filtered_logs = []
    # Sort logs by timestamp
    logs.sort(key=lambda x: x.timestamp_ms or 0)

    # Pre-compile regex patterns if provided
    regex_pattern = None
    exclude_regex_pattern = None
    used_substring_fallback = False
    exclude_used_substring_fallback = False

    # Track filtering statistics
    removed_by_include_filter = 0
    removed_by_exclude_filter = 0

    if params.filter:
        try:
            # Try to compile as regex first
            regex_pattern = re.compile(params.filter, re.IGNORECASE)
        except re.error:
            # If not a valid regex, fall back to simple substring matching
            logging.debug(
                f"Filter '{params.filter}' is not a valid regex, using substring matching"
            )
            regex_pattern = None
            used_substring_fallback = True

    if params.exclude_filter:
        try:
            # Try to compile as regex first
            exclude_regex_pattern = re.compile(params.exclude_filter, re.IGNORECASE)
        except re.error:
            # If not a valid regex, fall back to simple substring matching
            logging.debug(
                f"Exclude filter '{params.exclude_filter}' is not a valid regex, using substring matching"
            )
            exclude_regex_pattern = None
            exclude_used_substring_fallback = True

    for log in logs:
        # Apply inclusion filter
        if params.filter:
            if regex_pattern:
                # Use regex matching
                if not regex_pattern.search(log.content):
                    # exclude this log
                    removed_by_include_filter += 1
                    continue
            else:
                # Fall back to simple substring matching (case-insensitive)
                if params.filter.lower() not in log.content.lower():
                    # exclude this log
                    removed_by_include_filter += 1
                    continue

        # Apply exclusion filter
        if params.exclude_filter:
            if exclude_regex_pattern:
                # Use regex matching
                if exclude_regex_pattern.search(log.content):
                    # exclude this log
                    removed_by_exclude_filter += 1
                    continue
            else:
                # Fall back to simple substring matching (case-insensitive)
                if params.exclude_filter.lower() in log.content.lower():
                    # exclude this log
                    removed_by_exclude_filter += 1
                    continue

        if (
            time_filter
            and log.timestamp_ms
            and (
                log.timestamp_ms
                < time_filter.start_ms  # log is before expected time range
                or time_filter.end_ms
                < log.timestamp_ms  # log is after expected time range
            )
        ):
            # exclude this log
            continue
        else:
            filtered_logs.append(log)

    # Track count before limiting
    filtered_count_before_limit = len(filtered_logs)

    if params.limit and params.limit < len(filtered_logs):
        filtered_logs = filtered_logs[-params.limit :]

    return (
        filtered_logs,
        filtered_count_before_limit,
        used_substring_fallback,
        exclude_used_substring_fallback,
        removed_by_include_filter,
        removed_by_exclude_filter,
    )


def format_relative_time(timestamp_str: str, current_time: datetime) -> str:
    """Format a timestamp as relative to current time (e.g., '2 hours 15 minutes ago')"""
    try:
        # Handle relative timestamps (negative numbers)
        if timestamp_str and timestamp_str.startswith("-"):
            seconds = abs(int(timestamp_str))
            if seconds < 60:
                return f"{seconds} second{'s' if seconds != 1 else ''} before end time"
            minutes = seconds // 60
            if minutes < 60:
                return f"{minutes} minute{'s' if minutes != 1 else ''} before end time"
            hours = minutes // 60
            if hours < 24:
                return f"{hours} hour{'s' if hours != 1 else ''} before end time"
            days = hours // 24
            return f"{days} day{'s' if days != 1 else ''} before end time"

        # Parse the timestamp
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Calculate the difference
        diff = current_time - timestamp

        # If in the future
        if diff.total_seconds() < 0:
            diff = timestamp - current_time
            suffix = "from now"
        else:
            suffix = "ago"

        # Format the difference
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0 and days == 0:  # Only show minutes if less than a day
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

        if not parts:
            if diff.seconds < 60:
                return "just now" if suffix == "ago" else "right now"

        return f"{' '.join(parts)} {suffix}"
    except Exception:
        # If we can't parse it, just return the original
        return timestamp_str


def format_logs_with_containers(
    logs: List[StructuredLog], display_container_name: bool
) -> str:
    """Format logs with optional container name prefix"""
    if display_container_name:
        return "\n".join([f"{log.container or 'N/A'}: {log.content}" for log in logs])
    else:
        return "\n".join([log.content for log in logs])


def add_log_metadata(
    params: FetchPodLogsParams,
    total_count: int,
    filtered_logs: List[StructuredLog],
    filtered_count_before_limit: int,
    used_substring_fallback: bool,
    exclude_used_substring_fallback: bool,
    removed_by_include_filter: int,
    removed_by_exclude_filter: int,
    has_multiple_containers: bool,
    provider_name: str = "",
    extra_info: Optional[str] = None,
) -> List[str]:
    """Generate metadata for the log query"""
    metadata_lines = [
        "\n" + "=" * 80,
        "LOG QUERY METADATA",
        "=" * 80,
    ]

    # Time Context section
    current_time = datetime.now(timezone.utc)
    current_time_str = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata_lines.extend(
        [
            "Time Context:",
            f"- Query executed at: {current_time_str} (UTC)",
            "",
            "Query Parameters:",
            f"- Pod: {params.pod_name}",
            f"- Namespace: {params.namespace}",
        ]
    )

    if provider_name:
        metadata_lines.append(f"- Log provider: {provider_name}")

    metadata_lines.append("- Log source: Current and previous container logs")

    # Always show time range info
    if params.start_time or params.end_time:
        start_str = params.start_time or "beginning"
        end_str = params.end_time or "now"

        # Calculate relative times and duration
        relative_parts = []

        # Parse timestamps for duration calculation
        start_dt = None
        end_dt = None

        if params.start_time and params.start_time != "beginning":
            start_relative = format_relative_time(params.start_time, current_time)
            relative_parts.append(f"Started: {start_relative}")
            try:
                if not params.start_time.startswith("-"):
                    start_dt = datetime.fromisoformat(
                        params.start_time.replace("Z", "+00:00")
                    )
            except Exception:
                pass

        if params.end_time and params.end_time != "now":
            end_relative = format_relative_time(params.end_time, current_time)
            relative_parts.append(f"Ended: {end_relative}")
            try:
                end_dt = datetime.fromisoformat(params.end_time.replace("Z", "+00:00"))
            except Exception:
                pass
        else:
            # If end_time is "now" or not specified, use current time
            end_dt = current_time

        # Calculate duration if we have both timestamps
        if start_dt and end_dt:
            duration = end_dt - start_dt
            if duration.total_seconds() > 0:
                days = duration.days
                hours = duration.seconds // 3600
                minutes = (duration.seconds % 3600) // 60

                duration_parts = []
                if days > 0:
                    duration_parts.append(f"{days} day{'s' if days != 1 else ''}")
                if hours > 0:
                    duration_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if minutes > 0:
                    duration_parts.append(
                        f"{minutes} minute{'s' if minutes != 1 else ''}"
                    )

                if duration_parts:
                    duration_str = " ".join(duration_parts)
                else:
                    duration_str = "less than 1 minute"

                metadata_lines.append(
                    f"- Log time range: {start_str} (UTC) to {end_str} (UTC) ({duration_str})"
                )
            else:
                metadata_lines.append(
                    f"- Log time range: {start_str} (UTC) to {end_str} (UTC)"
                )
        else:
            metadata_lines.append(
                f"- Log time range: {start_str} (UTC) to {end_str} (UTC)"
            )

        if relative_parts:
            metadata_lines.append(f"  {' | '.join(relative_parts)}")
    else:
        metadata_lines.append(
            "- Log time range: None (fetching logs available via provider)"
        )

    # Add container info if multiple containers
    if has_multiple_containers:
        metadata_lines.append("- Container(s): Multiple containers")

    # Add extra provider-specific info if provided
    if extra_info:
        metadata_lines.append(f"- {extra_info}")

    metadata_lines.extend(
        [
            "",
            f"Total logs found before filtering: {total_count:,}",
        ]
    )

    # Only show filtering details if filters were applied
    if params.filter or params.exclude_filter:
        metadata_lines.append("")
        metadata_lines.append("Filtering Applied:")

    if params.filter:
        if used_substring_fallback:
            metadata_lines.append(
                f"  ⚠️  Filter '{params.filter}' is not valid regex, using substring match"
            )
        matched_by_filter = total_count - removed_by_include_filter
        percentage = (matched_by_filter / total_count * 100) if total_count > 0 else 0
        metadata_lines.append(f"  1. Include filter: '{params.filter}'")
        metadata_lines.append(
            f"     → Matched: {matched_by_filter:,} logs ({percentage:.1f}% of total)"
        )

    if params.exclude_filter:
        if exclude_used_substring_fallback:
            metadata_lines.append(
                f"  ⚠️  Exclude filter '{params.exclude_filter}' is not valid regex, using substring match"
            )
        metadata_lines.append("")
        metadata_lines.append(f"  2. Exclude filter: '{params.exclude_filter}'")
        metadata_lines.append(f"     → Excluded: {removed_by_exclude_filter:,} logs")
        metadata_lines.append(f"     → Remaining: {filtered_count_before_limit:,} logs")

    # Display section
    metadata_lines.append("")
    hit_limit = params.limit is not None and params.limit < filtered_count_before_limit
    if hit_limit and params.limit is not None:
        logs_omitted = filtered_count_before_limit - params.limit
        metadata_lines.append(
            f"Limits were applied: returned latest {params.limit:,} of {filtered_count_before_limit:,} filtered logs ({logs_omitted:,} omitted)"
        )
    else:
        metadata_lines.append(
            f"Limits did not restrict results: returned all {len(filtered_logs):,} logs"
        )

    # Add contextual hints based on results
    if len(filtered_logs) == 0:
        metadata_lines.append("")
        if params.filter and total_count > 0:
            # Logs exist but none matched the filter
            metadata_lines.append("Result: No logs matched your filters")
            metadata_lines.append("")
            metadata_lines.append("⚠️  Suggestions:")
            metadata_lines.append("  - Try a broader filter pattern")
            metadata_lines.append(
                f"  - Remove the filter to see all {total_count:,} available logs"
            )
            metadata_lines.append(
                "  - Your filter may be too specific for the log format used"
            )
        else:
            # No logs exist at all
            metadata_lines.append("Result: No logs found for this pod")
            metadata_lines.append("")
            metadata_lines.append("⚠️  Possible reasons:")
            if params.start_time or params.end_time:
                metadata_lines.append("  - Pod was not running during this time period")
            else:
                metadata_lines.append(
                    "  - Pod may not exist or may have been recently created"
                )
            metadata_lines.append("  - Container might not be logging to stdout/stderr")
            metadata_lines.append(
                "  - Logs might be going to a file instead of stdout/stderr"
            )

            # Only show time range suggestions if a time range was specified
            if params.start_time or params.end_time:
                metadata_lines.append("")
                metadata_lines.append("⚠️  Try:")
                metadata_lines.append(
                    "  - Remove time range to see ALL available logs (recommended unless you need this specific timeframe)"
                )
                metadata_lines.append("  - Or expand time range (e.g., last 24 hours)")
            else:
                metadata_lines.append("")
                metadata_lines.append("⚠️  Try:")
                metadata_lines.append(
                    f"  - Check if pod exists: kubectl get pods -n {params.namespace}"
                )
                metadata_lines.append(
                    f"  - Check pod events: kubectl describe pod {params.pod_name} -n {params.namespace}"
                )
    elif hit_limit:
        metadata_lines.append("")
        metadata_lines.append("⚠️  Hit display limit! Suggestions:")
        metadata_lines.append(
            "  - Add exclude_filter to remove noise: exclude_filter='<pattern1>|<pattern2>|<pattern3>'"
        )
        metadata_lines.append("  - Narrow time range to see fewer logs")
        metadata_lines.append(
            "  - Use more specific filter: filter='<term1>.*<term2>|<exact-phrase>'"
        )

    metadata_lines.append("=" * 80)
    return metadata_lines
