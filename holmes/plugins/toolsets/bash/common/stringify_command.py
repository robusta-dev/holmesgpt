from typing import List
from holmes.plugins.toolsets.bash.common.parse_command import (
    Command,
    BaseKubectlCommand,
    KubectlGetCommand,
    KubectlDescribeCommand,
    KubectlTopCommand,
    KubectlEventsCommand,
    GrepCommand
)


def stringify_command(commands: List[Command]) -> str:
    """
    Reconstruct a safe command string from parsed and validated Command objects.
    This ensures only validated components are executed.
    
    Args:
        commands: List of Command objects (e.g., [KubectlGetCommand, GrepCommand])
        
    Returns:
        Safe command string that can be executed
        
    Raises:
        ValueError: If command type is not supported or has invalid data
    """
    if not commands:
        raise ValueError("No commands provided")
    
    command_parts = []
    
    for cmd in commands:
        if isinstance(cmd, KubectlGetCommand):
            command_parts.append(_stringify_kubectl_get(cmd))
        elif isinstance(cmd, KubectlDescribeCommand):
            command_parts.append(_stringify_kubectl_describe(cmd))
        elif isinstance(cmd, KubectlTopCommand):
            command_parts.append(_stringify_kubectl_top(cmd))
        elif isinstance(cmd, KubectlEventsCommand):
            command_parts.append(_stringify_kubectl_events(cmd))
        elif isinstance(cmd, GrepCommand):
            command_parts.append(_stringify_grep(cmd))
        else:
            raise ValueError(f"Unsupported command type: {type(cmd).__name__}")
    
    # Join commands with pipe separator
    return " | ".join(command_parts)


def _stringify_kubectl_get(cmd: KubectlGetCommand) -> str:
    """Stringify kubectl get command."""
    parts = ["kubectl", "get", cmd.resource_type]
    
    # Add resource name if specified
    if cmd.resource_name:
        parts.append(cmd.resource_name)
    
    # Add namespace flags
    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    elif cmd.namespace:
        if cmd.namespace_format:
            # Use original format if available
            if '=' in cmd.namespace_format:
                parts.append(cmd.namespace_format)
            else:
                parts.extend(cmd.namespace_format.split())
        else:
            parts.extend(["--namespace", cmd.namespace])
    
    # Add output format
    if cmd.output_format:
        if cmd.output_format_flag:
            # Use original format if available
            if '=' in cmd.output_format_flag:
                parts.append(cmd.output_format_flag)
            else:
                parts.extend(cmd.output_format_flag.split())
        else:
            parts.extend(["--output", cmd.output_format])
    
    # Add selectors
    if cmd.selector:
        if cmd.selector_format:
            # Use original format if available
            if '=' in cmd.selector_format:
                parts.append(cmd.selector_format)
            else:
                parts.extend(cmd.selector_format.split())
        else:
            parts.extend(["--selector", cmd.selector])
    
    if cmd.field_selector:
        parts.extend(["--field-selector", cmd.field_selector])
    
    # Add boolean flags
    if cmd.show_labels:
        parts.append("--show-labels")
    
    # Add additional safe flags (already validated)
    parts.extend(cmd.additional_flags)
    
    return " ".join(_escape_shell_args(parts))


def _stringify_kubectl_describe(cmd: KubectlDescribeCommand) -> str:
    """Stringify kubectl describe command."""
    parts = ["kubectl", "describe", cmd.resource_type]
    
    # Add resource name if specified
    if cmd.resource_name:
        parts.append(cmd.resource_name)
    
    # Add namespace flags
    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    elif cmd.namespace:
        if cmd.namespace_format:
            # Use original format if available
            if '=' in cmd.namespace_format:
                parts.append(cmd.namespace_format)
            else:
                parts.extend(cmd.namespace_format.split())
        else:
            parts.extend(["--namespace", cmd.namespace])
    
    # Add selectors
    if cmd.selector:
        if cmd.selector_format:
            # Use original format if available
            if '=' in cmd.selector_format:
                parts.append(cmd.selector_format)
            else:
                parts.extend(cmd.selector_format.split())
        else:
            parts.extend(["--selector", cmd.selector])
    
    # Add show-events flag if explicitly set to false
    if not cmd.show_events:
        parts.append("--show-events=false")
    
    # Add additional safe flags (already validated)
    parts.extend(cmd.additional_flags)
    
    return " ".join(_escape_shell_args(parts))


def _stringify_kubectl_top(cmd: KubectlTopCommand) -> str:
    """Stringify kubectl top command."""
    parts = ["kubectl", "top", cmd.resource_type]
    
    # Add resource name if specified
    if cmd.resource_name:
        parts.append(cmd.resource_name)
    
    # Add namespace flags
    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    elif cmd.namespace:
        if cmd.namespace_format:
            # Use original format if available
            if '=' in cmd.namespace_format:
                parts.append(cmd.namespace_format)
            else:
                parts.extend(cmd.namespace_format.split())
        else:
            parts.extend(["--namespace", cmd.namespace])
    
    # Add selectors
    if cmd.selector:
        if cmd.selector_format:
            # Use original format if available
            if '=' in cmd.selector_format:
                parts.append(cmd.selector_format)
            else:
                parts.extend(cmd.selector_format.split())
        else:
            parts.extend(["--selector", cmd.selector])
    
    # Add boolean flags
    if cmd.containers:
        parts.append("--containers")
    
    if cmd.use_protocol_buffers:
        parts.append("--use-protocol-buffers")
    
    # Add additional safe flags (already validated)
    parts.extend(cmd.additional_flags)
    
    return " ".join(_escape_shell_args(parts))


def _stringify_kubectl_events(cmd: KubectlEventsCommand) -> str:
    """Stringify kubectl events command."""
    parts = ["kubectl", "events"]
    
    # Add namespace flags
    if cmd.all_namespaces:
        parts.append("--all-namespaces")
    elif cmd.namespace:
        parts.extend(["--namespace", cmd.namespace])
    
    # Add selectors
    if cmd.selector:
        parts.extend(["--selector", cmd.selector])
    
    # Add for_object
    if cmd.for_object:
        parts.extend(["--for", cmd.for_object])
    
    # Add types
    if cmd.types:
        parts.extend(["--types", cmd.types])
    
    # Add watch flag
    if cmd.watch:
        parts.append("--watch")
    
    # Add additional safe flags (already validated)
    parts.extend(cmd.additional_flags)
    
    return " ".join(_escape_shell_args(parts))


def _stringify_grep(cmd: GrepCommand) -> str:
    """Stringify grep command."""
    parts = ["grep"]
    
    # Use original keyword with quotes if available, otherwise use the keyword
    if hasattr(cmd, 'original_keyword') and cmd.original_keyword:
        # Check if keyword is a simple word that doesn't need quotes
        if _is_simple_word(cmd.keyword):
            # For simple words, don't use quotes regardless of original format
            parts.append(cmd.keyword)
        elif (cmd.original_keyword.startswith('"') and cmd.original_keyword.endswith('"')):
            # Convert double quotes to single quotes for complex patterns
            return f"grep '{cmd.keyword}'"
        elif (cmd.original_keyword.startswith("'") and cmd.original_keyword.endswith("'")):
            # Keep single quotes for complex patterns
            return f"grep '{cmd.keyword}'"
        else:
            parts.append(cmd.keyword)
    else:
        parts.append(cmd.keyword)
    
    return " ".join(_escape_shell_args(parts))


def _is_simple_word(word: str) -> bool:
    """Check if a word is simple enough to not need quotes."""
    import re
    # Simple words are alphanumeric and underscores only (no hyphens, colons, etc.)
    return bool(re.match(r'^[a-zA-Z0-9_]+$', word))


def _escape_shell_args(args: List[str]) -> List[str]:
    """
    Escape shell arguments to prevent injection.
    Uses single quotes for safety, escaping any single quotes in the content.
    """
    escaped_args = []
    
    for arg in args:
        # If argument is safe (contains only alphanumeric, hyphens, dots, underscores, equals, slash, comma, colon)
        # no escaping needed
        if arg and all(c.isalnum() or c in '.-_=/,:' for c in arg):
            escaped_args.append(arg)
        # If argument starts with -- or - (flag), no escaping needed
        elif arg.startswith('-'):
            escaped_args.append(arg)
        # For everything else, use single quotes and escape internal single quotes
        else:
            # Escape single quotes by ending the quoted string, adding escaped quote, starting new quoted string
            escaped = arg.replace("'", "'\"'\"'")
            escaped_args.append(f"'{escaped}'")
    
    return escaped_args