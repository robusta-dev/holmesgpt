# Helm Configuration

Configuration reference for HolmesGPT Helm chart.

**Quick Links:**

- [Installation Tutorial](../installation/kubernetes-installation.md) - Step-by-step setup guide
- [values.yaml](https://github.com/robusta-dev/holmesgpt/blob/master/helm/holmes/values.yaml) - Complete configuration reference
- [HTTP API Reference](../reference/http-api.md) - Test your deployment

## Basic Configuration

```yaml
# values.yaml
# Image settings
image: holmes:0.0.0
registry: robustadev

# Logging level
logLevel: INFO

# send exceptions to sentry
enableTelemetry: true

# Resource limits
resources:
  requests:
    cpu: 100m
    memory: 1024Mi
  limits:
    memory: 1024Mi

# Enabled/disable/customize specific toolsets
toolsets:
  kubernetes/core:
    enabled: true
  kubernetes/logs:
    enabled: true
  robusta:
    enabled: true
  internet:
    enabled: true
  prometheus/metrics:
    enabled: true
  ...
```

> **Note:** After making changes to your configuration, run `holmes toolset refresh` to apply the changes.

## Configuration Options

### Essential Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `additionalEnvVars` | Environment variables (API keys, etc.) | `[]` |
| `toolsets` | Enable/disable specific toolsets | (see values.yaml) |
| `openshift` | Enable OpenShift compatibility mode | `false` |
| `image` | HolmesGPT image name | `holmes:0.0.0` |
| `registry` | Container registry | `robustadev` |
| `logLevel` | Log level (DEBUG, INFO, WARN, ERROR) | `INFO` |
| `enableTelemetry` | Send exception reports to sentry | `true` |
| `certificate` | Base64 encoded custom CA certificate for outbound HTTPS requests (e.g., LLM API via proxy) | `""` |
| `sentryDSN` | Sentry DSN for telemetry | (see values.yaml) |

#### API Key Configuration

The most important configuration is setting up API keys for your chosen AI provider:

```yaml
additionalEnvVars:
- name: OPENAI_API_KEY
  value: "your-api-key"
# Or load from secret:
# - name: OPENAI_API_KEY
#   valueFrom:
#     secretKeyRef:
#       name: holmes-secrets
#       key: openai-api-key
```

#### Toolset Configuration

Control which capabilities HolmesGPT has access to:

```yaml
toolsets:
  kubernetes/core:
    enabled: true      # Core Kubernetes functionality
  kubernetes/logs:
    enabled: true      # Kubernetes logs access
  robusta:
    enabled: true      # Robusta platform integration
  internet:
    enabled: true      # Internet access for documentation
  prometheus/metrics:
    enabled: true      # Prometheus metrics access
```

### Service Account Configuration

```yaml
# Create service account (default: true)
createServiceAccount: true

# Use custom service account name
customServiceAccountName: ""

# Service account settings
serviceAccount:
  imagePullSecrets: []
  annotations: {}

# Custom RBAC rules
customClusterRoleRules: []
```

### Resource Configuration

```yaml
resources:
  requests:
    cpu: 100m
    memory: 1024Mi
  limits:
    cpu: 100m        # Optional CPU limit
    memory: 1024Mi
```

### Toolset Configuration

Enable or disable specific toolsets:

```yaml
toolsets:
  kubernetes/core:
    enabled: true      # Core Kubernetes functionality
  kubernetes/logs:
    enabled: true      # Kubernetes logs access
  robusta:
    enabled: true      # Robusta platform integration
  internet:
    enabled: true      # Internet access for documentation
  prometheus/metrics:
    enabled: true      # Prometheus metrics access
```

### Advanced Configuration

#### Scheduling

```yaml
# Node selection
# nodeSelector:
#   kubernetes.io/os: linux

# Pod affinity/anti-affinity
affinity: {}

# Tolerations
tolerations: []

# Priority class
priorityClassName: ""
```

#### Additional Configuration

```yaml
# Additional environment variables
additionalEnvVars: []
additional_env_vars: []  # Legacy, use additionalEnvVars instead

# Image pull secrets
imagePullSecrets: []

# Additional volumes
additionalVolumes: []

# Additional volume mounts
additionalVolumeMounts: []

# OpenShift compatibility mode
openshift: false

# Post-processing configuration
enablePostProcessing: false
postProcessingPrompt: "builtin://generic_post_processing.jinja2"

# Account creation
enableAccountsCreate: true

# MCP servers configuration
mcp_servers: {}

# Model list configuration
modelList: {}
```

## Example Configurations

### Minimal Setup

```yaml
# values.yaml
image: holmes:0.0.0
registry: robustadev
logLevel: INFO
enableTelemetry: false

resources:
  requests:
    cpu: 100m
    memory: 512Mi
  limits:
    memory: 512Mi

toolsets:
  kubernetes/core:
    enabled: true
  kubernetes/logs:
    enabled: true
  robusta:
    enabled: false
  internet:
    enabled: false
  prometheus/metrics:
    enabled: false
```


### OpenShift Setup

```yaml
# values.yaml
openshift: true
createServiceAccount: true

resources:
  requests:
    cpu: 100m
    memory: 1024Mi
  limits:
    memory: 1024Mi

toolsets:
  kubernetes/core:
    enabled: true
  kubernetes/logs:
    enabled: true
```

## Configuration Validation

```bash
# Validate configuration
helm template holmesgpt robusta/holmes -f values.yaml

# Dry run installation
helm install holmesgpt robusta/holmes -f values.yaml --dry-run

# Check syntax
yamllint values.yaml
```

## Complete Reference

For the complete and up-to-date configuration reference, see the actual [`values.yaml`](https://github.com/robusta-dev/holmesgpt/blob/master/helm/holmes/values.yaml) file in the repository.
