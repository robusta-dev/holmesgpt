# Building and Testing the Holmes Operator

This guide covers building, testing, and developing the Holmes Operator for Kubernetes health checks.

## Quick Start

There are two ways to provide API keys for local development:

### Method 1: Environment Variables (Recommended)
```bash
# Export your API key locally
export OPENAI_API_KEY="sk-..."  # or ANTHROPIC_API_KEY

# Skaffold will inject it into containers using setValueTemplates
skaffold dev --default-repo=<your-registry>

# To install in a different namespace (default is holmes-operator)
skaffold dev --default-repo=<your-registry> --namespace=my-namespace

# If you get CRD conflicts from previous installations:
# CRDs are cluster-scoped and retain Helm ownership metadata
kubectl delete crd healthchecks.holmes.robusta.dev
kubectl delete crd scheduledhealthchecks.holmes.robusta.dev

```

### Method 2: Local Values File
```bash
# Create a local values file (already gitignored)
cp helm/holmes/values.local.yaml.example helm/holmes/values.local.yaml
# Edit values.local.yaml and add your API key

# Tell Skaffold to use your local values file
skaffold dev --default-repo=<your-registry> \
  --profile=dev \
  -f skaffold.yaml \
  --helm-set-file helm.releases[0].valuesFiles[1]=helm/holmes/values.local.yaml
```

Note: You'll likely need to override the default registry as you won't have access to it
Examples: docker.io/yourusername or ghcr.io/yourusername

# Skaffold will:
# 1. Build and push Docker images to your registry
# 2. Deploy to your Kubernetes cluster
# 3. Automatically set up port-forwarding from cluster services to localhost
# 4. Stream logs and watch for code changes (hot reload in dev mode)

# After deployment, you can access services locally via Skaffold's port-forwarding:
# - API: http://localhost:9090 (forwards to holmes-holmes-api service port 8080 in cluster)
# - Operator metrics: http://localhost:9091 (forwards to holmes-holmes-operator deployment port 8080)
# - Test health checks are deployed automatically in holmes-system namespace
```

## Prerequisites

1. **Kubernetes cluster** - minikube, kind, Docker Desktop, or any K8s cluster
2. **Skaffold** - Install with `brew install skaffold` (macOS) or from [skaffold.dev](https://skaffold.dev)
3. **API key** - OpenAI or Anthropic API key set as environment variable

Note: The skaffold.yaml is configured to build linux/amd64 images by default (required for most Kubernetes clusters) regardless of your host machine's architecture. This may be slower on ARM machines due to emulation.

## Development Workflow

```bash
# Start development mode with hot reload
# Note: Override the default registry if you don't have access to it
skaffold dev --default-repo=<your-registry>
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

**Deploy Test Resources**

```bash
# Deploy test resources as needed for testing

# Option 1: Deploy everything at once
kubectl apply -f operator/test/test-deployment.yaml     # Sample nginx app
kubectl apply -f operator/test/test-healthchecks.yaml   # Sample health checks
kubectl apply -f operator/test/test-scheduled-healthchecks.yaml

# Option 2: Deploy only what you need
# Just the test app:
kubectl apply -f operator/test/test-deployment.yaml

# Just a basic health check:
kubectl apply -f operator/test/test-healthchecks.yaml

# Clean up when done
kubectl delete -f operator/test/test-healthchecks.yaml
kubectl delete -f operator/test/test-scheduled-healthchecks.yaml
kubectl delete -f operator/test/test-deployment.yaml
```

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
# Note: Slack integration requires SLACK_TOKEN environment variable
# For testing, add to helm/holmes/values.local.yaml:
# additionalEnvVars:
#   - name: SLACK_TOKEN
#     value: "xoxb-your-slack-token"

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
        # Note: slack_token must be configured in Holmes deployment
        # The token is not specified per-check for security reasons
EOF

# Watch execution and alert sending
kubectl logs -l app=holmes-operator -n holmes-system -f
```

## Building and Deployment

```bash
# Build operator image
docker build -t holmes-operator:latest operator/

# One-time deployment
skaffold run --default-repo=<your-registry>

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
# Operator configuration (set in container)
HOLMES_API_URL=http://holmes-api:8080  # API endpoint
LOG_LEVEL=INFO                         # Logging level

# API keys are passed to containers via one of these methods:
# Method 1: Export locally, Skaffold injects via setValueTemplates (see skaffold.yaml dev profile)
# Method 2: Create helm/holmes/values.local.yaml with your keys (gitignored)
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
