# Kubernetes Operator for Health Checks

The Holmes Operator provides Kubernetes-native health check management using Custom Resource Definitions (CRDs). Following the Kubernetes Job/CronJob pattern, it offers two types of checks:

- **HealthCheck**: One-time execution checks that run immediately
- **ScheduledHealthCheck**: Recurring checks that run on cron schedules

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
helm upgrade --install holmes robusta/holmes \
  --namespace holmes-system \
  --create-namespace \
  -f values.yaml
```

### 2. Create a One-Time Health Check

One-time checks execute immediately when created:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: quick-diagnostic
  namespace: default
spec:
  query: "Are all pods in deployment 'frontend' healthy?"
  timeout: 30
  mode: monitor  # or 'alert' for notifications
```

Apply and see results in ~30 seconds:

```bash
kubectl apply -f healthcheck.yaml
kubectl get healthcheck quick-diagnostic -w
```

### 3. Create a Scheduled Health Check

Scheduled checks run on cron schedules:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: frontend-monitoring
  namespace: default
spec:
  schedule: "*/5 * * * *"  # Every 5 minutes
  checkSpec:
    query: "Are all pods in deployment 'frontend' healthy?"
    timeout: 30
    mode: alert
    destinations:
      - type: slack
        config:
          channel: "#alerts"
  enabled: true
```

Apply the schedule:

```bash
kubectl apply -f scheduled-healthcheck.yaml
```

### 4. Monitor Results

```bash
# View one-time checks
kubectl get healthcheck

# View scheduled checks
kubectl get scheduledhealthcheck

# See checks created by a schedule
kubectl get healthcheck -l holmes.robusta.dev/scheduled-by=frontend-monitoring

# Check detailed status
kubectl describe healthcheck quick-diagnostic
```

## Understanding the Two CRD Types

### HealthCheck (One-Time Execution)

**Use Cases:**
- Quick diagnostics and troubleshooting
- CI/CD pipeline validations
- Ad-hoc cluster verification
- Post-deployment checks

**Behavior:**
- Executes immediately upon creation
- Results stored in status field
- Resource remains for audit trail
- Can be re-run via annotation

**Example:**
```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: deployment-validation
spec:
  query: "Did the recent deployment of 'api-service' complete successfully?"
  timeout: 45
  mode: monitor
```

### ScheduledHealthCheck (Recurring)

**Use Cases:**
- Continuous monitoring
- SLA compliance checks
- Regular health assessments
- Periodic resource validation

**Behavior:**
- Runs on cron schedule
- Creates HealthCheck resources at scheduled times
- Maintains execution history
- Can be enabled/disabled without deletion

**Example:**
```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: hourly-sla-check
spec:
  schedule: "0 * * * *"  # Every hour
  checkSpec:
    query: "Is the API response time under 200ms for 95% of requests?"
    timeout: 60
    mode: alert
  enabled: true
  # Note: The operator prevents concurrent runs automatically
```

## Features

### Scheduling Patterns

Common cron patterns for ScheduledHealthCheck:

```yaml
schedule: "*/5 * * * *"   # Every 5 minutes
schedule: "0 * * * *"     # Every hour
schedule: "0 */6 * * *"   # Every 6 hours
schedule: "0 9 * * 1-5"   # Weekdays at 9 AM
schedule: "0 0 * * 0"     # Sunday at midnight
```

### Alert Modes

Both check types support two modes:

- **`monitor`**: Log results only, no notifications
- **`alert`**: Send notifications when checks fail

```yaml
spec:
  mode: alert  # Send notifications
  destinations:
    - type: slack
      config:
        channel: "#critical-alerts"
```

### Destinations

Configure where alerts are sent:

```yaml
spec:
  destinations:
    # Slack
    - type: slack
      config:
        channel: "#alerts"

    # PagerDuty
    - type: pagerduty
      config:
        integrationKeyRef:
          name: pagerduty-secret
          key: integration-key
```

### Managing Scheduled Checks

Enable/disable schedules without deletion:

```bash
# Disable a schedule
kubectl patch scheduledhealthcheck hourly-check \
  --type='merge' -p '{"spec":{"enabled":false}}'

# Re-enable a schedule
kubectl patch scheduledhealthcheck hourly-check \
  --type='merge' -p '{"spec":{"enabled":true}}'
```

### Immediate Execution

Force immediate execution of either check type:

```bash
# Re-run a completed HealthCheck
kubectl annotate healthcheck quick-diagnostic \
  holmes.robusta.dev/run-now="$(date +%s)" --overwrite

# Trigger a scheduled check immediately (creates new HealthCheck)
kubectl annotate scheduledhealthcheck hourly-check \
  holmes.robusta.dev/run-now="$(date +%s)" --overwrite
```

## Examples

### Quick Cluster Health Check

One-time check for immediate feedback:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: cluster-health
spec:
  query: "Are all nodes Ready and all system pods running?"
  timeout: 30
  mode: monitor
```

### Continuous Pod Monitoring

Scheduled check every 5 minutes:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: pod-monitor
spec:
  schedule: "*/5 * * * *"
  checkSpec:
    query: "Are all pods in namespace 'production' running without restarts?"
    timeout: 30
    mode: alert
  enabled: true
```

### Memory Usage Monitoring

Regular memory checks with alerting:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: memory-monitor
spec:
  schedule: "*/10 * * * *"  # Every 10 minutes
  checkSpec:
    query: "Are all pods using less than 80% of their memory limits?"
    timeout: 45
    mode: alert
    destinations:
      - type: slack
        config:
          channel: "#infrastructure"
  # History automatically maintains last 10 executions
```

### Certificate Expiry Check

Daily certificate validation:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: cert-expiry
spec:
  schedule: "0 9 * * *"  # Daily at 9 AM
  checkSpec:
    query: "Are all TLS certificates valid for at least 30 days?"
    timeout: 60
    mode: alert
    destinations:
      - type: slack
        config:
          channel: "#security"
      - type: pagerduty
        config:
          integrationKeyRef:
            name: pagerduty-secret
            key: integration-key
  enabled: true
```

### Database Health Check

Quick diagnostic for database issues:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: db-diagnostic
spec:
  query: "Can the application connect to PostgreSQL and are all connection pools healthy?"
  timeout: 15
  mode: monitor
```

## Configuration

### Operator Settings

Configure the operator in your Helm values:

```yaml
operator:
  enabled: true

  # Custom image (for private registries)
  image: your-registry/holmes-operator:latest
  imagePullPolicy: Always

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
  name: alert-credentials
type: Opaque
stringData:
  slack-webhook: "https://hooks.slack.com/services/..."
  pagerduty-key: "YOUR_INTEGRATION_KEY"
---
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: critical-monitor
spec:
  schedule: "*/5 * * * *"
  checkSpec:
    query: "Is the payment service healthy?"
    mode: alert
    destinations:
      - type: pagerduty
        config:
          integrationKeyRef:
            name: alert-credentials
            key: pagerduty-key
```

## Status and History

### HealthCheck Status

One-time checks show execution results:

```yaml
status:
  phase: Completed  # Pending/Running/Completed
  startTime: "2024-01-01T12:00:00Z"
  completionTime: "2024-01-01T12:00:02Z"
  result: pass  # pass/fail/error
  message: "All pods healthy"
  rationale: "3 of 3 pods running with no restarts"
  duration: 2.0
```

### ScheduledHealthCheck Status

Scheduled checks maintain execution history:

```yaml
status:
  lastScheduleTime: "2024-01-01T12:00:00Z"
  lastSuccessfulTime: "2024-01-01T12:00:00Z"
  lastResult: pass
  message: "Check completed successfully"
  history:
    - executionTime: "2024-01-01T12:00:00Z"
      result: pass
      duration: 2.5
      checkName: frontend-monitor-20240101-120000-abc123
    - executionTime: "2024-01-01T11:55:00Z"
      result: pass
      duration: 2.3
      checkName: frontend-monitor-20240101-115500-def456
```

View status and history:

```bash
# One-time check status
kubectl get healthcheck db-diagnostic -o jsonpath='{.status}' | jq

# Schedule history
kubectl get scheduledhealthcheck hourly-check -o jsonpath='{.status.history}' | jq

# All checks from a schedule
kubectl get healthcheck -l holmes.robusta.dev/scheduled-by=hourly-check
```


## Troubleshooting

### Check Not Executing

For one-time checks:
```bash
# Check phase
kubectl get healthcheck <name> -o jsonpath='{.status.phase}'

# View operator logs
kubectl logs -l app=holmes-operator -n holmes-system
```

For scheduled checks:
```bash
# Verify schedule is enabled
kubectl get scheduledhealthcheck <name> -o jsonpath='{.spec.enabled}'

# Check for created HealthChecks
kubectl get healthcheck -l holmes.robusta.dev/scheduled-by=<schedule-name>
```

### Authentication Errors

```bash
# Verify API keys are set
kubectl get deployment holmes-api -n holmes-system -o yaml | grep -A2 "env:"

# Check operator can reach API
kubectl logs -l app=holmes-operator -n holmes-system | grep "API URL"
```

### Alerts Not Sending

1. Check destination configuration in spec
2. Verify secrets are correctly referenced
3. Check operator logs for send errors
4. Test with `mode: monitor` first to verify check execution

## Architecture

The operator follows the Kubernetes Job/CronJob pattern:

**HealthCheck Flow:**
1. User creates HealthCheck resource
2. Operator detects creation via Kopf
3. Immediately calls Holmes API to execute
4. Updates HealthCheck status with results
5. Resource remains for audit/history

**ScheduledHealthCheck Flow:**
1. User creates ScheduledHealthCheck resource
2. Operator sets up cron schedule via APScheduler
3. At scheduled time, creates new HealthCheck resource
4. HealthCheck executes as above
5. ScheduledHealthCheck tracks history

This design provides:
- Clear separation of one-time vs recurring checks
- Natural audit trail via HealthCheck resources
- Familiar Kubernetes patterns
- Easy troubleshooting and debugging

See [Operator Architecture](../reference/operator-architecture.md) for detailed technical information.

## Further Reading

- [Testing Guide](../development/operator-testing.md) - Build, deploy, and test the operator
- [CLI Health Checks](health-checks.md) - Using checks via CLI
- [Operator Architecture](../reference/operator-architecture.md) - Technical details
- [API Reference](../reference/http-api.md) - Holmes API endpoints
