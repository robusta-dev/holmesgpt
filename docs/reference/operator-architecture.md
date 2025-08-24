# Holmes Operator Architecture

## Overview

The Holmes Operator extends Holmes with Kubernetes-native health check capabilities using Custom Resource Definitions (CRDs). It follows a distributed architecture where scheduling and orchestration are handled by a lightweight operator, while check execution is performed by the stateless Holmes API servers.

## Architecture Components

### 1. Holmes Operator
A lightweight Kubernetes controller built with [kopf](https://kopf.readthedocs.io/) that:
- Watches HealthCheck CRDs
- Manages check scheduling using APScheduler
- Makes HTTP calls to Holmes API servers for check execution
- Updates CRD status with results
- Handles retry logic and error recovery

### 2. Holmes API Servers
Stateless FastAPI servers that:
- Execute health checks via `/api/check/execute` endpoint
- Reuse existing CheckRunner implementation
- Scale horizontally based on load
- Share LLM rate limits and resource pools

### 3. HealthCheck CRD
Kubernetes custom resource that defines:
- Check queries and configuration
- Scheduling (cron format)
- Alert destinations
- Execution history and status

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────┐                             │
│  │   Holmes Operator (kopf)    │                             │
│  │  - CRD Watching             │                             │
│  │  - Scheduling (APScheduler) │                             │
│  │  - Status Management        │                             │
│  │  - Retry Logic              │                             │
│  └──────────┬─────────────────┘                             │
│             │                                                │
│             │ HTTP API Calls                                 │
│             │                                                │
│             ▼                                                │
│  ┌─────────────────────────────────────────┐                │
│  │        Service: holmes-api              │                │
│  ├─────────────────────────────────────────┤                │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │   │ server.py│  │ server.py│  │ server.py│   (Stateless)│
│  │   │ Pod 1    │  │ Pod 2    │  │ Pod 3    │              │
│  │   └──────────┘  └──────────┘  └──────────┘             │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  ┌────────────────────────────┐                             │
│  │    HealthCheck CRDs        │                             │
│  └────────────────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

## CRD Specification

### HealthCheck Resource

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: frontend-health
  namespace: default
spec:
  # Check definition
  query: "Are all pods in deployment 'frontend' healthy with at least 2 ready replicas?"
  schedule: "*/5 * * * *"  # Cron format (every 5 minutes)
  timeout: 30  # seconds

  # Alert configuration
  mode: alert  # or "monitor" (no alerts)
  destinations:
    - type: slack
      config:
        channel: "#alerts"
    - type: pagerduty
      config:
        integrationKeyRef:
          name: pagerduty-secret
          key: integration-key

  # Execution control
  enabled: true  # Enable or disable the check
  concurrencyPolicy: Forbid  # Allow/Forbid/Replace concurrent runs

  # History limits
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3

status:
  # Execution timestamps
  lastScheduleTime: "2024-01-01T00:00:00Z"
  lastSuccessfulTime: "2024-01-01T00:00:00Z"

  # Latest result
  lastResult: pass  # pass/fail/error
  message: "All pods healthy with 3/3 replicas ready"

  # Kubernetes conditions
  conditions:
    - type: Ready
      status: "True"
      lastTransitionTime: "2024-01-01T00:00:00Z"
      reason: CheckPassed
      message: "Check executed successfully"

  # Execution history
  history:
    - executionTime: "2024-01-01T00:00:00Z"
      result: pass
      duration: 2.5
    - executionTime: "2024-01-01T00:05:00Z"
      result: pass
      duration: 2.3
```

## API Integration

### Check Execution Endpoint

The operator calls the Holmes API server to execute checks:

```http
POST /api/check/execute
Content-Type: application/json
X-Check-Name: default/frontend-health

{
  "query": "Are all pods in deployment 'frontend' healthy?",
  "timeout": 30,
  "mode": "alert",
  "destinations": [
    {
      "type": "slack",
      "config": {
        "channel": "#alerts"
      }
    }
  ]
}
```

Response:
```json
{
  "status": "pass",
  "message": "All pods are healthy with 3/3 replicas ready",
  "duration": 2.5,
  "rationale": "Deployment 'frontend' has 3 ready replicas out of 3 desired.",
  "error": null
}
```

## Deployment

### Operator Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: holmes-operator
  namespace: holmes
spec:
  replicas: 1
  selector:
    matchLabels:
      app: holmes-operator
  template:
    metadata:
      labels:
        app: holmes-operator
    spec:
      serviceAccountName: holmes-operator
      containers:
      - name: operator
        image: robusta/holmes-operator:latest
        command: ["kopf", "run", "-A", "--standalone", "/app/operator.py"]
        env:
        - name: HOLMES_API_URL
          value: "http://holmes-api:8080"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### RBAC Configuration

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: holmes-operator
  namespace: holmes
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: holmes-operator
rules:
- apiGroups: ["holmes.robusta.dev"]
  resources: ["healthchecks"]
  verbs: ["get", "list", "watch", "patch", "update"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: holmes-operator
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: holmes-operator
subjects:
- kind: ServiceAccount
  name: holmes-operator
  namespace: holmes
```

## Key Design Decisions

### 1. Distributed Architecture
- **Decision**: Separate operator from API servers
- **Rationale**: Better scalability, fault isolation, and resource efficiency
- **Trade-off**: Slightly more complex deployment

### 2. HTTP Communication
- **Decision**: Operator calls API via HTTP instead of direct execution
- **Rationale**: Reuses existing API infrastructure, enables horizontal scaling
- **Trade-off**: Network latency, requires service discovery

### 3. APScheduler for Scheduling
- **Decision**: Use APScheduler library instead of Kubernetes CronJobs
- **Rationale**: More efficient for frequent checks, better resource pooling
- **Trade-off**: Scheduling logic in operator instead of native K8s

### 4. Status in CRD
- **Decision**: Store execution results in CRD status
- **Rationale**: Kubernetes-native, accessible via kubectl
- **Trade-off**: Limited history, status size constraints

## Monitoring and Observability

### Metrics
The operator exposes Prometheus metrics:
- `holmes_checks_scheduled_total` - Total number of scheduled checks
- `holmes_checks_executed_total` - Total number of executed checks
- `holmes_checks_failed_total` - Total number of failed checks
- `holmes_check_duration_seconds` - Check execution duration histogram

### Logging
- Operator logs: Scheduling, CRD events, API calls
- API server logs: Check execution, tool calls, errors

### kubectl Integration
```bash
# List all health checks
kubectl get healthchecks

# View check details
kubectl describe healthcheck frontend-health

# View check status
kubectl get healthcheck frontend-health -o jsonpath='{.status}'

# Suspend a check
kubectl patch healthcheck frontend-health --type='merge' -p '{"spec":{"suspend":true}}'
```

## Security Considerations

### Authentication
- Operator uses Kubernetes service account for API authentication
- API servers validate requests from operator
- Secrets for destinations stored in Kubernetes secrets

### Network Policies
- Restrict operator to API server communication
- Limit API server egress for tool execution

### Resource Limits
- Operator has strict resource limits
- Rate limiting for API calls
- Timeout enforcement for check execution

## Future Enhancements

### Phase 1 (MVP)
- [x] Basic CRD and operator
- [x] Check execution via API
- [x] Status updates
- [x] Cron scheduling

### Phase 2
- [ ] High availability with leader election
- [ ] Check dependencies
- [ ] Webhook validation
- [ ] Result persistence to external storage

### Phase 3
- [ ] Multi-tenancy support
- [ ] Check templates
- [ ] Grafana dashboard integration
- [ ] Cost tracking per check

## Migration from CLI

Users can migrate from CLI-based checks to operator-managed checks:

1. Convert `checks.yaml` to HealthCheck CRDs
2. Deploy operator alongside existing setup
3. Gradually migrate checks
4. Deprecate CLI-based scheduling

Example migration:
```bash
# Old CLI approach
holmes check --checks-file checks.yaml

# New operator approach
kubectl apply -f healthchecks/
```

## Troubleshooting

### Common Issues

1. **Check not executing**
   - Verify operator is running: `kubectl logs -l app=holmes-operator`
   - Check CRD status: `kubectl get healthcheck <name> -o yaml`
   - Ensure API service is accessible

2. **Authentication errors**
   - Verify service account permissions
   - Check RBAC configuration
   - Validate API server logs

3. **Scheduling issues**
   - Check operator logs for scheduler errors
   - Verify cron expression syntax
   - Check for suspended status

## References

- [Kopf Documentation](https://kopf.readthedocs.io/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [Kubernetes CRD Best Practices](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
- [Holmes Check Documentation](./health-checks.md)
