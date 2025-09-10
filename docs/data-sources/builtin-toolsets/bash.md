# Bash Toolset ✓

!!! info "Enabled by Default"
    This toolset is enabled by default and should typically remain enabled.

The bash toolset provides secure execution of common command-line tools used for troubleshooting and system analysis. It replaces multiple YAML-based toolsets with a single, comprehensive toolset that includes safety validation and command parsing.


**⚠️ Security Note**: This toolset executes commands on the system where Holmes is running. Only validated, safe commands are allowed. The toolset includes built-in safety validation and command parsing.

## Supported Commands

The bash toolset supports the following categories of commands:

### Cloud Providers

**AWS CLI (`aws`)**

- Supports various AWS services and operations
- Commands are validated for safety before execution

**Azure CLI (`az`)**

- Supports Azure operations including AKS management
- Network and account operations

### Kubernetes Tools

**kubectl**

- Standard Kubernetes operations: get, describe, logs, events
- Resource management and cluster inspection
- Live metrics via `kubectl top`

**Helm**

- Helm chart operations
- Repository management
- Release inspection

**ArgoCD**

- Application management
- Deployment status checking

### Container Tools

**Docker**

- Container inspection and management
- Image operations
- Basic Docker commands

### Text Processing Utilities

**Data Processing**

- `grep` - Text searching and pattern matching
- `jq` - JSON processing and querying
- `sed` - Stream editing and text transformation
- `awk` - Pattern scanning and text processing

**File Utilities**

- `cut` - Column extraction
- `sort` - Data sorting
- `uniq` - Duplicate removal
- `head` - Show first lines
- `tail` - Show last lines
- `wc` - Word, line, and character counting

**Text Transformation**

- `tr` - Character translation and deletion
- `base64` - Base64 encoding/decoding

## Command Validation

All commands undergo security validation before execution:

- Only whitelisted commands and options are allowed
- Dangerous operations are blocked (file writes, system calls, etc.)
- Commands are parsed and validated for safety
- Pipe operations between supported commands are allowed

## Configuration

The bash tool can be configured with the following environment variables:

| Env var                    | Default value |                                                                                                      Description                                                                                                     |
|----------------------------|:-------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------:|
| BASH_TOOL_UNSAFE_ALLOW_ALL | false         | Disables safety checks and allow Holmes to run any bash command immediately and without warning. This is unsafe because Holmes could mutate state, share secrets or even irreparably delete production environments. |
| ENABLE_CLI_TOOL_APPROVAL   | true          | Allow Holmes to ask for approval before running potentially unsafe commands.                                                                                                                                         |