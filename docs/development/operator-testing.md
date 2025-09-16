# Building and Testing the Holmes Operator

This guide covers building, testing, and developing the Holmes Operator for Kubernetes health checks.

## Quick Start

```bash
# Set your API key
export OPENAI_API_KEY="sk-..."  # or ANTHROPIC_API_KEY

# Start development with auto-reload
skaffold dev

# Everything is now running:
# - API: http://localhost:9090
# - Operator metrics: http://localhost:9091
# - Test health checks deployed automatically
```

## Prerequisites

1. **Kubernetes cluster** - minikube, kind, Docker Desktop, or any K8s cluster
2. **Skaffold** - Install with `brew install skaffold` (macOS) or from [skaffold.dev](https://skaffold.dev)
3. **API key** - OpenAI or Anthropic API key set as environment variable

## Development Workflow

```bash
# Start development mode with hot reload
skaffold dev
```

**Running Operator Locally**

For debugging or development without containers:

```bash
# Install dependencies
pip install -r operator/requirements.txt

# Deploy Holmes API only (skip operator)
SKIP_OPERATOR=true skaffold run

# Run operator locally
HOLMES_API_URL=http://localhost:9090 \
  poetry run kopf run -A --standalone operator/main.py
```

## Testing the Operator

**Basic Testing**

```bash
# View deployed health checks
kubectl get healthchecks -n holmes-system
kubectl get scheduledhealthchecks -n holmes-system

# Watch check execution
kubectl get healthcheck -n holmes-system -w

# View detailed status
kubectl describe healthcheck quick-nginx-check -n holmes-system
```

**Testing Specific Scenarios**

```bash
# Test invalid cron schedule handling
kubectl apply -f - <<EOF
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: bad-schedule-test
  namespace: holmes-system
spec:
  schedule: "INVALID_CRON"
  checkSpec:
    query: "Test query"
    timeout: 30
    mode: monitor
  enabled: true
EOF

# Check error is handled gracefully
kubectl get scheduledhealthcheck bad-schedule-test -n holmes-system -o yaml

# Test immediate execution
kubectl annotate healthcheck quick-nginx-check -n holmes-system \
  holmes.robusta.dev/run-now="$(date +%s)" --overwrite

# Test scheduled check immediate execution
kubectl annotate scheduledhealthcheck frequent-test-schedule -n holmes-system \
  holmes.robusta.dev/run-now="$(date +%s)" --overwrite
```

**Testing Alert Destinations**

```bash
# Create check with Slack alerts
kubectl apply -f - <<EOF
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: alert-test
  namespace: holmes-system
spec:
  query: "Are there any pods in CrashLoopBackOff state?"
  timeout: 30
  mode: alert
  destinations:
    - type: slack
      config:
        channel: "#alerts"
EOF

# Watch execution and alert sending
kubectl logs -l app=holmes-operator -n holmes-system -f
```

## Building and Deployment

```bash
# Build operator image
docker build -t holmes-operator:latest operator/

# One-time deployment
skaffold run

# Clean up
skaffold delete
```

## Project Structure

```
operator/
├── main.py              # Operator implementation
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container image
├── test/               # Test resources
│   ├── test-healthchecks.yaml
│   ├── test-scheduled-healthchecks.yaml
│   └── test-deployment.yaml
```

## What Gets Deployed

Running `skaffold dev` deploys:
- Holmes API Server with `/api/check/execute` endpoint
- Holmes Operator to manage HealthCheck CRDs
- Test applications and sample health checks

## Configuration

**Environment Variables**

```bash
# Operator configuration
HOLMES_API_URL=http://holmes-api:8080  # API endpoint
LOG_LEVEL=INFO                         # Logging level

# API keys (set before running Skaffold)
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="..."
```


## Monitoring and Debugging

**View Logs**

```bash
# Stream all logs (aggregated by Skaffold)
skaffold logs -f

# Filter by deployment
skaffold logs -f -d holmes-holmes-operator

# Direct kubectl logs
kubectl logs -l app=holmes-operator -n holmes-system -f
```

**Check Metrics**

```bash
# Operator exposes Prometheus metrics
curl http://localhost:9091/metrics

# Key metrics:
# - holmes_checks_scheduled_total
# - holmes_checks_executed_total
# - holmes_checks_failed_total
# - holmes_check_duration_seconds
```

**Common Issues**

**Pods not starting:**
```bash
kubectl get pods -n holmes-system
kubectl get events -n holmes-system --sort-by='.lastTimestamp'
```

**CRD not found:**
```bash
kubectl get crd healthchecks.holmes.robusta.dev
kubectl get crd scheduledhealthchecks.holmes.robusta.dev
```


## Advanced Usage

**Direct API Testing**

```bash
# Test check execution endpoint
curl -X POST http://localhost:9090/api/check/execute \
  -H "Content-Type: application/json" \
  -H "X-Check-Name: test/manual-check" \
  -d '{
    "query": "Are all pods in the default namespace healthy?",
    "timeout": 30,
    "mode": "monitor"
  }'
```

**Manual CRD Operations**

```bash
# Enable/disable scheduled check
kubectl patch scheduledhealthcheck frequent-test-schedule -n holmes-system \
  --type='merge' -p '{"spec":{"enabled":false}}'

# Delete all health checks
kubectl delete healthchecks --all -n holmes-system
kubectl delete scheduledhealthchecks --all -n holmes-system
```

## Next Steps

- [Operator Architecture](../reference/operator-architecture.md) - Technical deep dive
- [Health Checks Guide](../walkthrough/operator-health-checks.md) - Using health checks
- [API Reference](../reference/http-api.md) - Check execution endpoint details

## Helm Deployment (Production)

For production deployments using pre-built images:

```bash
# Install with Helm
helm install holmes robusta/holmes \
  --namespace holmes-system \
  --create-namespace \
  --set operator.enabled=true \
  --set additionalEnvVars[0].name=OPENAI_API_KEY \
  --set additionalEnvVars[0].value="sk-your-key-here"

# Deploy test resources
kubectl apply -f operator/test/test-healthchecks.yaml
kubectl apply -f operator/test/test-scheduled-healthchecks.yaml

# Verify installation
kubectl get pods -n holmes-system
kubectl get healthcheck -n holmes-system -w
```
