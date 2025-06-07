import shlex

SAFE_SHELL_CHARS = frozenset(".-_=/,:")


def escape_shell_args(args: list[str]) -> list[str]:
    """
    Escape shell arguments to prevent injection.
    Uses shlex.quote for safe shell argument quoting.
    """
    escaped_args = []

    for arg in args:
        # If argument is safe (contains only alphanumeric, hyphens, dots, underscores, equals, slash, comma, colon)
        # no escaping needed
        if arg and all(c.isalnum() or c in SAFE_SHELL_CHARS for c in arg):
            escaped_args.append(arg)
        # If argument starts with -- or - (flag), no escaping needed
        elif arg.startswith("-"):
            escaped_args.append(arg)
        # For everything else, use shlex.quote for proper escaping
        else:
            escaped_args.append(shlex.quote(arg))

    return escaped_args
