# Helm Configuration

Configuration reference for HolmesGPT Helm chart.

## Basic Configuration

```yaml
# values.yaml
# Image settings
image: holmes:0.0.0
registry: robustadev

# Logging level
logLevel: INFO

# Telemetry (set to false to disable)
enableTelemetry: true

# Resource limits
resources:
  requests:
    cpu: 100m
    memory: 1024Mi
  limits:
    memory: 1024Mi

# Toolsets
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
```

## Configuration Options

### Essential Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image` | HolmesGPT image name | `holmes:0.0.0` |
| `registry` | Container registry | `robustadev` |
| `logLevel` | Log level (DEBUG, INFO, WARN, ERROR) | `INFO` |
| `enableTelemetry` | Enable telemetry collection | `true` |

### Resource Configuration

```yaml
resources:
  requests:
    cpu: 100m
    memory: 1024Mi
  limits:
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

## Advanced Configuration

### Scheduling

```yaml
# Node selection
nodeSelector:
  kubernetes.io/os: linux

# Pod affinity/anti-affinity
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app: holmes
        topologyKey: kubernetes.io/hostname

# Tolerations
tolerations:
- key: "dedicated"
  operator: "Equal"
  value: "holmes"
  effect: "NoSchedule"

# Priority class
priorityClassName: "high-priority"
```

### Service Account

```yaml
# Create service account (default: true)
createServiceAccount: true

# Use custom service account
customServiceAccountName: "my-holmes-sa"
```

### Additional Configuration

```yaml
# Additional environment variables
additionalEnvVars:
- name: MY_CUSTOM_VAR
  value: "custom-value"

# Additional volumes
additionalVolumes:
- name: custom-config
  configMap:
    name: my-config

# Additional volume mounts
additionalVolumeMounts:
- name: custom-config
  mountPath: /etc/custom
  readOnly: true
```

## Example Configurations

### Minimal Setup

```yaml
# values.yaml
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

### Production Setup

```yaml
# values.yaml
image: holmes:v1.0.0
logLevel: WARN
enableTelemetry: true

resources:
  requests:
    cpu: 500m
    memory: 2048Mi
  limits:
    memory: 4096Mi

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app: holmes
        topologyKey: kubernetes.io/hostname

tolerations:
- key: "dedicated"
  operator: "Equal"
  value: "holmes"
  effect: "NoSchedule"

priorityClassName: "high-priority"
```

## Configuration Validation

```bash
# Validate configuration
helm template holmesgpt holmesgpt/holmes -f values.yaml

# Dry run installation
helm install holmesgpt holmesgpt/holmes -f values.yaml --dry-run

# Check syntax
yamllint values.yaml
```
