"""
Shared utility functions for Azure SQL toolset.
"""


def format_timing(microseconds: float) -> str:
    """Format timing values with appropriate units.

    Args:
        microseconds: Time value in microseconds

    Returns:
        Formatted string with appropriate units (s, ms, or μs)
    """
    if microseconds >= 1_000_000:  # >= 1 second
        return f"{microseconds / 1_000_000:.2f} s"
    elif microseconds >= 1_000:  # >= 1 millisecond
        return f"{microseconds / 1_000:.2f} ms"
    else:  # < 1 millisecond
        return f"{microseconds:.0f} μs"


def format_size_bytes(bytes_value: float) -> str:
    """Format byte values with appropriate units.

    Args:
        bytes_value: Size value in bytes

    Returns:
        Formatted string with appropriate units (GB, MB, KB, or B)
    """
    if bytes_value >= 1_073_741_824:  # >= 1 GB
        return f"{bytes_value / 1_073_741_824:.2f} GB"
    elif bytes_value >= 1_048_576:  # >= 1 MB
        return f"{bytes_value / 1_048_576:.2f} MB"
    elif bytes_value >= 1_024:  # >= 1 KB
        return f"{bytes_value / 1_024:.2f} KB"
    else:  # < 1 KB
        return f"{bytes_value:.0f} B"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """Format percentage values.

    Args:
        value: Percentage value (0-100)
        decimal_places: Number of decimal places to show

    Returns:
        Formatted percentage string
    """
    return f"{value:.{decimal_places}f}%"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, handling division by zero.

    Args:
        numerator: The dividend
        denominator: The divisor
        default: Value to return if denominator is zero

    Returns:
        Division result or default if denominator is zero
    """
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length including ellipsis

    Returns:
        Truncated text with ellipsis if needed
    """
    if not text or len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
