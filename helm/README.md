# Holmes Helm Chart

This Helm chart deploys Holmes and optionally the Holmes Operator for managing HealthCheck CRDs.

## Installation

```bash
# Basic installation
helm install holmes ./helm/holmes

# With custom values
helm install holmes ./helm/holmes -f my-values.yaml

# Enable operator
helm install holmes ./helm/holmes --set operator.enabled=true
```

## Image Configuration

### Main Holmes Image

The main Holmes image uses a simple `registry/image` format:

```yaml
# Default configuration
registry: robustadev
image: holmes:0.0.0

# Results in: robustadev/holmes:0.0.0
```

**Custom Registry Examples:**

```yaml
# Private registry
registry: my-registry.com/my-org
image: holmes:v1.2.3
# Results in: my-registry.com/my-org/holmes:v1.2.3

# AWS ECR
registry: 123456789.dkr.ecr.us-east-1.amazonaws.com
image: holmes:latest
# Results in: 123456789.dkr.ecr.us-east-1.amazonaws.com/holmes:latest
```

### Operator Image

The operator image configuration is more flexible:

```yaml
# Default configuration (uses parent registry)
operator:
  image: ""  # Empty means use default
  tag: "latest"

# Results in: robustadev/holmes-operator:latest
```

**Custom Image Examples:**

```yaml
# Use a different Docker Hub image
operator:
  image: "myorg/holmes-operator"
  tag: "v1.0.0"
# Results in: myorg/holmes-operator:v1.0.0

# Use a private registry
operator:
  image: "gcr.io/my-project/holmes-operator"
  tag: "stable"
# Results in: gcr.io/my-project/holmes-operator:stable

# Use a fully qualified image
operator:
  image: "my.registry.com:5000/holmes/operator"
  tag: "2.0.0"
# Results in: my.registry.com:5000/holmes/operator:2.0.0
```

## Key Configuration Options

### API Keys

```yaml
additionalEnvVars:
  - name: OPENAI_API_KEY
    value: "sk-..."
  - name: ANTHROPIC_API_KEY
    value: "sk-ant-..."
```

### Operator

```yaml
operator:
  enabled: true  # Enable the operator
  logLevel: INFO
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      memory: 512Mi
```

### Toolsets

```yaml
toolsets:
  kubernetes/core:
    enabled: true
  prometheus/metrics:
    enabled: true
    config:
      url: http://prometheus:9090
```

### Resources

```yaml
resources:
  requests:
    cpu: 100m
    memory: 1024Mi
  limits:
    memory: 2048Mi
```

## Development

For local development with Skaffold:

```bash
# Use the dev values file
skaffold dev -f skaffold.yaml

# This uses helm/holmes/values.dev.yaml which:
# - Enables the operator
# - Uses locally built images
# - Reduces resource requirements
# - Enables debug logging
```

## Image Pull Secrets

For private registries:

```yaml
imagePullSecrets:
  - name: my-registry-secret

# Or for service account
serviceAccount:
  imagePullSecrets:
    - name: my-registry-secret
```

## Common Patterns

### Production Deployment

```yaml
# values-production.yaml
registry: my-company.registry.io
image: holmes:1.0.0

operator:
  enabled: true
  image: "my-company.registry.io/holmes-operator"
  tag: "1.0.0"

resources:
  requests:
    cpu: 500m
    memory: 2Gi
  limits:
    memory: 4Gi

additionalEnvVars:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: openai-key
```

### Minimal Local Setup

```yaml
# values-local.yaml
operator:
  enabled: false  # No operator needed for basic testing

resources:
  requests:
    cpu: 100m
    memory: 512Mi

additionalEnvVars:
  - name: OPENAI_API_KEY
    value: "sk-..."  # For testing only!
```

## Troubleshooting

### Image Pull Errors

If you see image pull errors:

1. **Check image path construction:**
   ```bash
   helm template holmes ./helm/holmes | grep image:
   ```

2. **Verify registry access:**
   ```bash
   docker pull <constructed-image-path>
   ```

3. **For private registries, ensure secrets exist:**
   ```bash
   kubectl get secret my-registry-secret
   ```

### Operator Not Starting

1. **Check CRD installation:**
   ```bash
   kubectl get crd healthchecks.holmes.robusta.dev
   ```

2. **Check operator logs:**
   ```bash
   kubectl logs -l app=holmes-operator
   ```

3. **Verify RBAC permissions:**
   ```bash
   kubectl auth can-i --list --as=system:serviceaccount:<namespace>:<release>-holmes-operator
   ```
