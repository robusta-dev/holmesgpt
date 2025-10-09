"""Utilities for working with dictionaries."""

from typing import Any, Dict


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with override values taking precedence.

    This implements Helm-style deep merging:
    - Nested dictionaries are merged recursively
    - Lists/arrays are replaced entirely (not merged)
    - None/null values are preserved (explicit "no value")

    Args:
        base: The base dictionary with default values
        override: The dictionary with values to override

    Returns:
        A new dictionary with merged values

    Example:
        >>> from holmes.utils.dict_utils import deep_merge
        >>> base = {
        ...     'database': {
        ...         'host': 'localhost',
        ...         'port': 5432,
        ...         'credentials': {
        ...             'username': 'admin',
        ...             'password': 'default'
        ...         }
        ...     }
        ... }
        >>> override = {
        ...     'database': {
        ...         'host': 'prod.example.com',
        ...         'credentials': {
        ...             'password': 'secret'
        ...         }
        ...     }
        ... }
        >>> result = deep_merge(base, override)
        >>> result['database']['host']
        'prod.example.com'
        >>> result['database']['port']
        5432
        >>> result['database']['credentials']['username']
        'admin'
        >>> result['database']['credentials']['password']
        'secret'
    """
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override

    # Start with a copy of base
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Both are dicts, merge recursively
            result[key] = deep_merge(result[key], value)
        else:
            # Replace value (including lists, primitives, None, etc.)
            result[key] = value

    return result
