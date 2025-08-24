# Kubernetes Operator for Health Checks

The Holmes Operator provides Kubernetes-native health check management using Custom Resource Definitions (CRDs). This allows you to define, schedule, and manage health checks as Kubernetes resources.

## Quick Start

### 1. Enable the Operator

Update your Helm values to enable the operator:

```yaml
# values.yaml
operator:
  enabled: true
```

Deploy or upgrade Holmes:

```bash
helm upgrade --install holmes robusta/holmes -f values.yaml
```

### 2. Create a Health Check

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: frontend-health
  namespace: default
spec:
  query: "Are all pods in deployment 'frontend' healthy?"
  schedule: "*/5 * * * *"  # Every 5 minutes
  mode: alert
  destinations:
    - type: slack
      config:
        channel: "#alerts"
```

Apply the health check:

```bash
kubectl apply -f healthcheck.yaml
```

### 3. Monitor Results

```bash
# List all health checks
kubectl get healthchecks

# Check status
kubectl describe healthcheck frontend-health

# View detailed status
kubectl get healthcheck frontend-health -o yaml
```

## Features

### Scheduling

Health checks run on a cron schedule:

```yaml
spec:
  schedule: "*/5 * * * *"  # Every 5 minutes
  schedule: "0 */6 * * *"  # Every 6 hours
  schedule: "0 9 * * 1"    # Every Monday at 9 AM
```

### Alert Modes

- **`alert`**: Send notifications when checks fail
- **`monitor`**: Log results only, no notifications

```yaml
spec:
  mode: alert  # or monitor
```

### Destinations

Configure where alerts are sent:

```yaml
spec:
  destinations:
    - type: slack
      config:
        channel: "#alerts"
    - type: pagerduty
      config:
        integrationKeyRef:
          name: pagerduty-secret
          key: integration-key
```

### Enable/Disable Checks

Temporarily disable a check without deleting it:

```yaml
spec:
  enabled: false  # Set to true to re-enable
```

Or via kubectl:

```bash
# Disable a check
kubectl patch healthcheck frontend-health --type='merge' -p '{"spec":{"enabled":false}}'

# Re-enable a check
kubectl patch healthcheck frontend-health --type='merge' -p '{"spec":{"enabled":true}}'
```

### Run Check Immediately

Force an immediate check execution:

```bash
kubectl annotate healthcheck frontend-health holmes.robusta.dev/run-now=true
```

## Examples

### Basic Pod Health Check

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: pod-health
spec:
  query: "Are all pods in namespace 'production' running?"
  schedule: "*/3 * * * *"
  mode: alert
```

### Memory Usage Check

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: memory-check
spec:
  query: "Are all pods using less than 90% of their memory limits?"
  schedule: "*/10 * * * *"
  timeout: 45
  mode: monitor
```

### Certificate Expiry Check

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: cert-expiry
spec:
  query: "Are all TLS certificates valid for at least 30 days?"
  schedule: "0 9 * * *"  # Daily at 9 AM
  mode: alert
  destinations:
    - type: slack
      config:
        channel: "#security"
```

### Database Connection Check

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: database-check
spec:
  query: "Can the application connect to PostgreSQL at db.example.com:5432?"
  schedule: "*/2 * * * *"
  timeout: 15
  mode: alert
```

## Configuration

### Operator Settings

Configure the operator in your Helm values:

```yaml
operator:
  enabled: true

  # Resources for operator pod
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      memory: 512Mi

  # Log level
  logLevel: INFO

  # Pod placement
  nodeSelector: {}
  affinity: {}
  tolerations: []
```

### Secrets for Destinations

Store sensitive credentials in Kubernetes secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: pagerduty-secret
type: Opaque
stringData:
  integration-key: "YOUR_PAGERDUTY_KEY"
---
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: critical-check
spec:
  query: "Is the payment service healthy?"
  destinations:
    - type: pagerduty
      config:
        integrationKeyRef:
          name: pagerduty-secret
          key: integration-key
```

## Status and History

The operator maintains execution history in the CRD status:

```yaml
status:
  lastExecutionTime: "2024-01-01T12:00:00Z"
  lastSuccessfulTime: "2024-01-01T12:00:00Z"
  lastResult: pass
  message: "All pods healthy"
  history:
    - executionTime: "2024-01-01T12:00:00Z"
      result: pass
      duration: 2.5
    - executionTime: "2024-01-01T11:55:00Z"
      result: pass
      duration: 2.3
```

View history:

```bash
kubectl get healthcheck frontend-health -o jsonpath='{.status.history}'
```

## Migration from CLI

Convert existing CLI checks to operator-managed checks:

### CLI Configuration (checks.yaml)
```yaml
checks:
  - name: "Pod Health"
    query: "Are all pods running?"
    destinations: ["slack"]
```

### Operator CRD
```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: pod-health
spec:
  query: "Are all pods running?"
  schedule: "*/5 * * * *"
  destinations:
    - type: slack
      config:
        channel: "#alerts"
```

## Troubleshooting

### Check Not Running

1. Verify operator is running:
```bash
kubectl logs -l app=holmes-operator
```

2. Check CRD status:
```bash
kubectl describe healthcheck <name>
```

3. Ensure check is not suspended:
```bash
kubectl get healthcheck <name> -o jsonpath='{.spec.suspend}'
```

### Authentication Errors

1. Check operator service account:
```bash
kubectl get serviceaccount holmes-operator -o yaml
```

2. Verify RBAC permissions:
```bash
kubectl auth can-i get healthchecks --as=system:serviceaccount:default:holmes-operator
```

### Alert Not Sending

1. Check destination configuration
2. Verify secrets are mounted correctly
3. Check operator logs for send errors

## Architecture

The operator follows a distributed architecture:

- **Operator Pod**: Manages CRDs, scheduling, and orchestration
- **API Servers**: Execute checks and return results
- **CRDs**: Store check definitions and status

This design allows:
- Horizontal scaling of API servers
- Independent operator lifecycle
- Kubernetes-native management

See [Operator Architecture](../reference/operator-architecture.md) for detailed information.
