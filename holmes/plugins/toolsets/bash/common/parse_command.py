from typing import Optional, List, Union, ClassVar
import re
from pydantic import BaseModel, Field


class Command(BaseModel):
    prefix: str
    """Base class for all commands."""


class GrepCommand(Command):
    PREFIX: ClassVar[str] = "grep"
    prefix: str = Field(default="grep")
    keyword: str = Field(description="The keyword to search for")
    original_keyword: str = Field(description="The original keyword with quotes preserved")


class BaseKubectlCommand(Command):
    PREFIX: ClassVar[str] = "kubectl"
    prefix: str = Field(default="kubectl")
    resource_type: str = Field(description="The Kubernetes resource type (e.g., 'pods', 'services', 'deployments')")
    resource_name: Optional[str] = Field(default=None, description="Specific resource name if provided")
    namespace: Optional[str] = Field(default=None, description="Namespace specified with -n or --namespace")
    all_namespaces: bool = Field(default=False, description="Whether --all-namespaces or -A flag is used")
    selector: Optional[str] = Field(default=None, description="Label selector specified with -l or --selector")
    additional_flags: List[str] = Field(default_factory=list, description="Any other flags not explicitly parsed")
    
    # Track original flag formats for preservation
    namespace_format: Optional[str] = Field(default=None, description="Original format used for namespace flag")
    selector_format: Optional[str] = Field(default=None, description="Original format used for selector flag")


class KubectlGetCommand(BaseKubectlCommand):
    PREFIX: ClassVar[str] = "kubectl get"
    prefix: str = Field(default="kubectl get")
    output_format: Optional[str] = Field(default=None, description="Output format specified with -o or --output")
    field_selector: Optional[str] = Field(default=None, description="Field selector specified with --field-selector")
    show_labels: bool = Field(default=False, description="Whether --show-labels flag is used")
    
    # Track original flag formats for preservation
    output_format_flag: Optional[str] = Field(default=None, description="Original format used for output flag")
    field_selector_format: Optional[str] = Field(default=None, description="Original format used for field-selector flag")


class KubectlDescribeCommand(BaseKubectlCommand):
    PREFIX: ClassVar[str] = "kubectl describe"
    prefix: str = Field(default="kubectl describe")
    show_events: bool = Field(default=True, description="Whether to show events (default true, can be disabled with --show-events=false)")


class KubectlTopCommand(BaseKubectlCommand):
    PREFIX: ClassVar[str] = "kubectl top"
    prefix: str = Field(default="kubectl top")
    containers: bool = Field(default=False, description="Whether --containers flag is used")
    use_protocol_buffers: bool = Field(default=False, description="Whether --use-protocol-buffers flag is used")


class KubectlEventsCommand(BaseKubectlCommand):
    PREFIX: ClassVar[str] = "kubectl events"
    prefix: str = Field(default="kubectl events")
    for_object: Optional[str] = Field(default=None, description="Object to show events for with --for")
    watch: bool = Field(default=False, description="Whether --watch flag is used")
    types: Optional[str] = Field(default=None, description="Event types to show with --types")


def validate_kubectl_command(cmd: BaseKubectlCommand) -> None:
    """
    Validate common kubectl command fields to prevent injection attacks.
    Raises ValueError if validation fails.
    """
    # Valid Kubernetes resource types (common ones)
    VALID_RESOURCE_TYPES = {
        'pods', 'pod', 'po',
        'services', 'service', 'svc',
        'deployments', 'deployment', 'deploy',
        'replicasets', 'replicaset', 'rs',
        'statefulsets', 'statefulset', 'sts',
        'daemonsets', 'daemonset', 'ds',
        'jobs', 'job',
        'cronjobs', 'cronjob', 'cj',
        'configmaps', 'configmap', 'cm',
        'secrets', 'secret',
        'persistentvolumes', 'persistentvolume', 'pv',
        'persistentvolumeclaims', 'persistentvolumeclaim', 'pvc',
        'nodes', 'node', 'no',
        'namespaces', 'namespace', 'ns',
        'ingresses', 'ingress', 'ing',
        'networkpolicies', 'networkpolicy', 'netpol',
        'serviceaccounts', 'serviceaccount', 'sa',
        'roles', 'role',
        'rolebindings', 'rolebinding',
        'clusterroles', 'clusterrole',
        'clusterrolebindings', 'clusterrolebinding',
        'endpoints', 'endpoint', 'ep',
        'events', 'event', 'ev',
        'horizontalpodautoscalers', 'horizontalpodautoscaler', 'hpa',
        'verticalpodautoscalers', 'verticalpodautoscaler', 'vpa',
        'poddisruptionbudgets', 'poddisruptionbudget', 'pdb',
        'all'
    }
    
    # Patterns for safe names and values
    SAFE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$')
    SAFE_NAMESPACE_PATTERN = re.compile(r'^[a-z0-9][a-z0-9\-]*$')
    SAFE_SELECTOR_PATTERN = re.compile(r'^[a-zA-Z0-9\-_.=,!()]+$')
    
    # Validate resource type
    if cmd.resource_type.lower() not in VALID_RESOURCE_TYPES:
        raise ValueError(f"Invalid resource type: {cmd.resource_type}")
    
    # Validate resource name if provided
    if cmd.resource_name:
        if not SAFE_NAME_PATTERN.match(cmd.resource_name):
            raise ValueError(f"Invalid resource name: {cmd.resource_name}")
        if len(cmd.resource_name) > 253:
            raise ValueError("Resource name too long")
    
    # Validate namespace if provided
    if cmd.namespace:
        if not SAFE_NAMESPACE_PATTERN.match(cmd.namespace):
            raise ValueError(f"Invalid namespace: {cmd.namespace}")
        if len(cmd.namespace) > 63:
            raise ValueError("Namespace name too long")
    
    # Validate selectors if provided
    if cmd.selector:
        if not SAFE_SELECTOR_PATTERN.match(cmd.selector):
            raise ValueError(f"Invalid label selector: {cmd.selector}")
        if len(cmd.selector) > 1000:
            raise ValueError("Label selector too long")


def validate_kubectl_get_command(cmd: KubectlGetCommand) -> None:
    """
    Validate kubectl get command specific fields.
    Raises ValueError if validation fails.
    """
    # First validate common fields
    validate_kubectl_command(cmd)
    
    # Valid output formats
    VALID_OUTPUT_FORMATS = {
        'yaml', 'json', 'wide', 'name', 'custom-columns', 'custom-columns-file',
        'go-template', 'go-template-file', 'jsonpath', 'jsonpath-file'
    }
    
    SAFE_SELECTOR_PATTERN = re.compile(r'^[a-zA-Z0-9\-_.=,!()]+$')
    
    # Validate output format if provided
    if cmd.output_format:
        if cmd.output_format not in VALID_OUTPUT_FORMATS:
            raise ValueError(f"Invalid output format: {cmd.output_format}")
    
    # Validate field selector if provided
    if cmd.field_selector:
        if not SAFE_SELECTOR_PATTERN.match(cmd.field_selector):
            raise ValueError(f"Invalid field selector: {cmd.field_selector}")
        if len(cmd.field_selector) > 1000:
            raise ValueError("Field selector too long")
    
    # Validate additional flags for get command
    SAFE_GET_FLAGS = {
        '--dry-run', '--grace-period', '--ignore-not-found', '--include-uninitialized',
        '--no-headers', '--raw', '--sort-by', '--template', '--timeout', '--chunk-size',
        '-h', '--help', '--allow-missing-template-keys', '--show-managed-fields'
    }
    
    SAFE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$')
    
    for flag in cmd.additional_flags:
        if flag.startswith('-') and flag not in SAFE_GET_FLAGS:
            if '=' in flag:
                flag_name = flag.split('=')[0]
                if flag_name not in SAFE_GET_FLAGS:
                    raise ValueError(f"Unsafe additional flag: {flag}")
            else:
                raise ValueError(f"Unsafe additional flag: {flag}")
        elif not flag.startswith('-'):
            if not SAFE_NAME_PATTERN.match(flag):
                raise ValueError(f"Unsafe additional value: {flag}")


def validate_kubectl_describe_command(cmd: KubectlDescribeCommand) -> None:
    """
    Validate kubectl describe command specific fields.
    Raises ValueError if validation fails.
    """
    # First validate common fields
    validate_kubectl_command(cmd)
    
    # Validate additional flags for describe command
    SAFE_DESCRIBE_FLAGS = {
        '--include-uninitialized', '--show-events', '-h', '--help'
    }
    
    SAFE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$')
    
    for flag in cmd.additional_flags:
        if flag.startswith('-') and flag not in SAFE_DESCRIBE_FLAGS:
            if '=' in flag:
                flag_name = flag.split('=')[0]
                if flag_name not in SAFE_DESCRIBE_FLAGS:
                    raise ValueError(f"Unsafe additional flag: {flag}")
            else:
                raise ValueError(f"Unsafe additional flag: {flag}")
        elif not flag.startswith('-'):
            if not SAFE_NAME_PATTERN.match(flag):
                raise ValueError(f"Unsafe additional value: {flag}")


def validate_kubectl_top_command(cmd: KubectlTopCommand) -> None:
    """
    Validate kubectl top command specific fields.
    Raises ValueError if validation fails.
    """
    # First validate common fields
    validate_kubectl_command(cmd)
    
    # Validate additional flags for top command
    SAFE_TOP_FLAGS = {
        '--containers', '--use-protocol-buffers', '--sort-by', '--no-headers',
        '-h', '--help'
    }
    
    SAFE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$')
    
    for flag in cmd.additional_flags:
        if flag.startswith('-') and flag not in SAFE_TOP_FLAGS:
            if '=' in flag:
                flag_name = flag.split('=')[0]
                if flag_name not in SAFE_TOP_FLAGS:
                    raise ValueError(f"Unsafe additional flag: {flag}")
            else:
                raise ValueError(f"Unsafe additional flag: {flag}")
        elif not flag.startswith('-'):
            if not SAFE_NAME_PATTERN.match(flag):
                raise ValueError(f"Unsafe additional value: {flag}")


def validate_kubectl_events_command(cmd: KubectlEventsCommand) -> None:
    """
    Validate kubectl events command specific fields.
    Raises ValueError if validation fails.
    """
    # First validate common fields
    validate_kubectl_command(cmd)
    
    # Validate for_object if provided
    if cmd.for_object:
        SAFE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_./:]*$')
        if not SAFE_NAME_PATTERN.match(cmd.for_object):
            raise ValueError(f"Invalid for_object: {cmd.for_object}")
        if len(cmd.for_object) > 253:
            raise ValueError("for_object too long")
    
    # Validate types if provided
    if cmd.types:
        VALID_EVENT_TYPES = {'Normal', 'Warning'}
        type_list = [t.strip() for t in cmd.types.split(',')]
        for event_type in type_list:
            if event_type not in VALID_EVENT_TYPES:
                raise ValueError(f"Invalid event type: {event_type}")
    
    # Validate additional flags for events command
    SAFE_EVENTS_FLAGS = {
        '--for', '--types', '--no-headers', '-h', '--help'
    }
    
    SAFE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$')
    
    for flag in cmd.additional_flags:
        if flag.startswith('-') and flag not in SAFE_EVENTS_FLAGS:
            if '=' in flag:
                flag_name = flag.split('=')[0]
                if flag_name not in SAFE_EVENTS_FLAGS:
                    raise ValueError(f"Unsafe additional flag: {flag}")
            else:
                raise ValueError(f"Unsafe additional flag: {flag}")
        elif not flag.startswith('-'):
            if not SAFE_NAME_PATTERN.match(flag):
                raise ValueError(f"Unsafe additional value: {flag}")


def validate_grep_command(cmd: GrepCommand) -> None:
    """
    Validate grep command to prevent injection attacks.
    Raises ValueError if validation fails.
    """
    # Pattern for safe grep keywords - alphanumeric, hyphens, dots, underscores, spaces, colons, asterisks, parentheses
    SAFE_GREP_PATTERN = re.compile(r'^[a-zA-Z0-9\-_. :*()]+$')
    
    if not cmd.keyword:
        raise ValueError("Grep keyword cannot be empty")
    
    if not SAFE_GREP_PATTERN.match(cmd.keyword):
        raise ValueError(f"Unsafe grep keyword: {cmd.keyword}")
    
    if len(cmd.keyword) > 100:
        raise ValueError("Grep keyword too long")


def parse_command(command: str) -> List[Command]:
    """
    Parse a command that may include pipes and return a list of structured commands.
    Uses command prefixes to determine which parser to call.
    """
    # Split on pipe to handle command | command pattern
    pipe_parts = command.split('|')
    
    if len(pipe_parts) > 2:
        raise ValueError("Only single pipe is supported")
    
    commands = []
    
    # Parse each part of the piped command
    for i, part in enumerate(pipe_parts):
        part = part.strip()
        parsed_command = _parse_single_command(part)
        commands.append(parsed_command)
    
    return commands


def _parse_single_command(command_part: str) -> Command:
    """Parse a single command by matching against known command prefixes."""
    command_part = command_part.strip()
    
    # Define known command classes with their prefixes
    COMMAND_CLASSES = [
        (KubectlGetCommand.PREFIX, _parse_get_command),
        (KubectlDescribeCommand.PREFIX, _parse_describe_command),
        (KubectlTopCommand.PREFIX, _parse_top_command),
        (KubectlEventsCommand.PREFIX, _parse_events_command),
        (GrepCommand.PREFIX, _parse_grep_command),
    ]
    
    # Find matching command class by prefix
    for prefix, parser_func in COMMAND_CLASSES:
        if command_part.startswith(prefix):
            if prefix.startswith("kubectl"):
                # For kubectl commands, pass the split parts
                parts = command_part.split()
                return parser_func(parts)
            else:
                # For other commands, pass the command string
                return parser_func(command_part)
    
    # If no prefix matches, raise an error
    raise ValueError(f"Unsupported command: {command_part}")


def _parse_grep_command(grep_part: str) -> GrepCommand:
    """Parse the grep portion of the command."""
    parts = grep_part.strip().split()
    
    if not parts or parts[0] != "grep":
        raise ValueError("Only 'grep' commands are supported after pipe")
    
    if len(parts) < 2:
        raise ValueError("Grep command requires a keyword")
    
    # Join all parts after 'grep' as the keyword (handles keywords with spaces)
    original_keyword = ' '.join(parts[1:])
    keyword = original_keyword
    
    # Remove quotes if present for validation but keep original
    if keyword.startswith('"') and keyword.endswith('"'):
        keyword = keyword[1:-1]
    elif keyword.startswith("'") and keyword.endswith("'"):
        keyword = keyword[1:-1]
    
    grep_cmd = GrepCommand(keyword=keyword, original_keyword=original_keyword)
    validate_grep_command(grep_cmd)
    
    return grep_cmd


def _parse_get_command(parts: List[str]) -> KubectlGetCommand:
    """Parse kubectl get command."""
    result = KubectlGetCommand(resource_type="")
    i = 2
    
    while i < len(parts):
        part = parts[i]
        
        if part.startswith('-'):
            if part == '-n' or part.startswith('-n=') or part.startswith('--namespace'):
                if '=' in part:
                    result.namespace = part.split('=', 1)[1]
                    # Preserve long form with equals, convert short form to long without equals
                    if part.startswith('--'):
                        result.namespace_format = f"--namespace={result.namespace}"
                    else:
                        result.namespace_format = f"--namespace {result.namespace}"
                    i += 1
                elif i + 1 < len(parts):
                    result.namespace = parts[i + 1]
                    # Always normalize to long form
                    if part == '-n':
                        result.namespace_format = f"--namespace {parts[i + 1]}"
                    else:
                        result.namespace_format = f"{part} {parts[i + 1]}"
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part in ['-A', '--all-namespaces']:
                result.all_namespaces = True
                i += 1
            elif part == '-o' or part.startswith('-o=') or part.startswith('--output'):
                if '=' in part:
                    result.output_format = part.split('=', 1)[1]
                    # Preserve long form with equals, convert short form to long without equals
                    if part.startswith('--'):
                        result.output_format_flag = f"--output={result.output_format}"
                    else:
                        result.output_format_flag = f"--output {result.output_format}"
                    i += 1
                elif i + 1 < len(parts):
                    result.output_format = parts[i + 1]
                    # Always normalize to long form space-separated
                    result.output_format_flag = f"--output {parts[i + 1]}"
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part == '-l' or part.startswith('-l=') or part.startswith('--selector'):
                if '=' in part:
                    result.selector = part.split('=', 1)[1]
                    # Preserve long form with equals, convert short form to long without equals
                    if part.startswith('--'):
                        result.selector_format = f"--selector={result.selector}"
                    else:
                        result.selector_format = f"--selector {result.selector}"
                    i += 1
                elif i + 1 < len(parts):
                    result.selector = parts[i + 1]
                    # Always normalize to long form
                    if part == '-l':
                        result.selector_format = f"--selector {parts[i + 1]}"
                    else:
                        result.selector_format = f"{part} {parts[i + 1]}"
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part.startswith('--field-selector'):
                if '=' in part:
                    result.field_selector = part.split('=', 1)[1]
                    i += 1
                elif i + 1 < len(parts):
                    result.field_selector = parts[i + 1]
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part == '--show-labels':
                result.show_labels = True
                i += 1
            else:
                result.additional_flags.append(part)
                i += 1
        else:
            if not result.resource_type:
                result.resource_type = part
            elif not result.resource_name:
                result.resource_name = part
            else:
                result.additional_flags.append(part)
            i += 1
    
    if not result.resource_type:
        raise ValueError("Resource type is required for kubectl get command")
    
    # Validate the parsed command for security
    validate_kubectl_get_command(result)
    
    return result


def _parse_describe_command(parts: List[str]) -> KubectlDescribeCommand:
    """Parse kubectl describe command."""
    result = KubectlDescribeCommand(resource_type="")
    i = 2
    
    while i < len(parts):
        part = parts[i]
        
        if part.startswith('-'):
            if part == '-n' or part.startswith('-n=') or part.startswith('--namespace'):
                if '=' in part:
                    result.namespace = part.split('=', 1)[1]
                    # Preserve long form with equals, convert short form to long without equals
                    if part.startswith('--'):
                        result.namespace_format = f"--namespace={result.namespace}"
                    else:
                        result.namespace_format = f"--namespace {result.namespace}"
                    i += 1
                elif i + 1 < len(parts):
                    result.namespace = parts[i + 1]
                    # Always normalize to long form
                    if part == '-n':
                        result.namespace_format = f"--namespace {parts[i + 1]}"
                    else:
                        result.namespace_format = f"{part} {parts[i + 1]}"
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part in ['-A', '--all-namespaces']:
                result.all_namespaces = True
                i += 1
            elif part == '-l' or part.startswith('--selector'):
                if '=' in part:
                    result.selector = part.split('=', 1)[1]
                    # Preserve long form with equals, convert short form to long without equals
                    if part.startswith('--'):
                        result.selector_format = f"--selector={result.selector}"
                    else:
                        result.selector_format = f"--selector {result.selector}"
                    i += 1
                elif i + 1 < len(parts):
                    result.selector = parts[i + 1]
                    # Always normalize short flags to long form
                    if part == '-l':
                        result.selector_format = f"--selector {parts[i + 1]}"
                    else:
                        result.selector_format = f"{part} {parts[i + 1]}"
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part.startswith('--show-events'):
                if '=' in part:
                    result.show_events = part.split('=', 1)[1].lower() == 'true'
                    i += 1
                elif i + 1 < len(parts):
                    result.show_events = parts[i + 1].lower() == 'true'
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            else:
                result.additional_flags.append(part)
                i += 1
        else:
            if not result.resource_type:
                result.resource_type = part
            elif not result.resource_name:
                result.resource_name = part
            else:
                result.additional_flags.append(part)
            i += 1
    
    if not result.resource_type:
        raise ValueError("Resource type is required for kubectl describe command")
    
    # Validate the parsed command for security
    validate_kubectl_describe_command(result)
    
    return result


def _parse_top_command(parts: List[str]) -> KubectlTopCommand:
    """Parse kubectl top command."""
    result = KubectlTopCommand(resource_type="")
    i = 2
    
    while i < len(parts):
        part = parts[i]
        
        if part.startswith('-'):
            if part == '-n' or part.startswith('--namespace'):
                if '=' in part:
                    result.namespace = part.split('=', 1)[1]
                    # Preserve long form with equals, convert short form to long without equals
                    if part.startswith('--'):
                        result.namespace_format = f"--namespace={result.namespace}"
                    else:
                        result.namespace_format = f"--namespace {result.namespace}"
                    i += 1
                elif i + 1 < len(parts):
                    result.namespace = parts[i + 1]
                    # Always normalize to long form
                    if part == '-n':
                        result.namespace_format = f"--namespace {parts[i + 1]}"
                    else:
                        result.namespace_format = f"{part} {parts[i + 1]}"
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part in ['-A', '--all-namespaces']:
                result.all_namespaces = True
                i += 1
            elif part == '-l' or part.startswith('--selector'):
                if '=' in part:
                    result.selector = part.split('=', 1)[1]
                    # Preserve long form with equals, convert short form to long without equals
                    if part.startswith('--'):
                        result.selector_format = f"--selector={result.selector}"
                    else:
                        result.selector_format = f"--selector {result.selector}"
                    i += 1
                elif i + 1 < len(parts):
                    result.selector = parts[i + 1]
                    # Always normalize short flags to long form
                    if part == '-l':
                        result.selector_format = f"--selector {parts[i + 1]}"
                    else:
                        result.selector_format = f"{part} {parts[i + 1]}"
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part == '--containers':
                result.containers = True
                i += 1
            elif part == '--use-protocol-buffers':
                result.use_protocol_buffers = True
                i += 1
            else:
                result.additional_flags.append(part)
                i += 1
        else:
            if not result.resource_type:
                result.resource_type = part
            elif not result.resource_name:
                result.resource_name = part
            else:
                result.additional_flags.append(part)
            i += 1
    
    if not result.resource_type:
        raise ValueError("Resource type is required for kubectl top command")
    
    # Validate the parsed command for security
    validate_kubectl_top_command(result)
    
    return result


def _parse_events_command(parts: List[str]) -> KubectlEventsCommand:
    """Parse kubectl events command."""
    result = KubectlEventsCommand(resource_type="events")
    i = 2
    
    while i < len(parts):
        part = parts[i]
        
        if part.startswith('-'):
            if part == '-n' or part.startswith('--namespace'):
                if '=' in part:
                    result.namespace = part.split('=', 1)[1]
                    i += 1
                elif i + 1 < len(parts):
                    result.namespace = parts[i + 1]
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part in ['-A', '--all-namespaces']:
                result.all_namespaces = True
                i += 1
            elif part == '-l' or part.startswith('--selector'):
                if '=' in part:
                    result.selector = part.split('=', 1)[1]
                    i += 1
                elif i + 1 < len(parts):
                    result.selector = parts[i + 1]
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part.startswith('--for'):
                if '=' in part:
                    result.for_object = part.split('=', 1)[1]
                    i += 1
                elif i + 1 < len(parts):
                    result.for_object = parts[i + 1]
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part.startswith('--types'):
                if '=' in part:
                    result.types = part.split('=', 1)[1]
                    i += 1
                elif i + 1 < len(parts):
                    result.types = parts[i + 1]
                    i += 2
                else:
                    result.additional_flags.append(part)
                    i += 1
            elif part in ['-w', '--watch']:
                result.watch = True
                i += 1
            else:
                result.additional_flags.append(part)
                i += 1
        else:
            # For events, additional non-flag arguments go to additional_flags
            result.additional_flags.append(part)
            i += 1
    
    # Validate the parsed command for security
    validate_kubectl_events_command(result)
    
    return result