def escape_shell_args(args: list[str]) -> list[str]:
    """
    Escape shell arguments to prevent injection.
    Uses single quotes for safety, escaping any single quotes in the content.
    """
    escaped_args = []

    for arg in args:
        # If argument is safe (contains only alphanumeric, hyphens, dots, underscores, equals, slash, comma, colon)
        # no escaping needed
        if arg and all(c.isalnum() or c in ".-_=/,:" for c in arg):
            escaped_args.append(arg)
        # If argument starts with -- or - (flag), no escaping needed
        elif arg.startswith("-"):
            escaped_args.append(arg)
        # For everything else, use single quotes and escape internal single quotes
        else:
            # Escape single quotes by ending the quoted string, adding escaped quote, starting new quoted string
            escaped = arg.replace("'", "'\"'\"'")
            escaped_args.append(f"'{escaped}'")

    return escaped_args
