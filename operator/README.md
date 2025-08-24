# Holmes Operator

Kubernetes operator for managing Holmes HealthCheck CRDs.

## Quick Tests

```bash
# Start development with auto-reload
skaffold dev

# Deploy once
skaffold run

# View health checks
kubectl get healthchecks -n holmes-system

# Trigger a check manually
kubectl annotate healthcheck manual-check -n holmes-system \
  holmes.robusta.dev/run-now=true --overwrite

# Watch operator logs
skaffold logs -f --tail 20

# Delete everything
skaffold delete

# Ports automatically forwarded:
# API: http://localhost:9090
# Operator health: http://localhost:9091
```

## Overview

This operator watches `HealthCheck` custom resources and:
- Schedules health checks based on cron expressions
- Executes checks by calling the Holmes API
- Updates CRD status with results
- Handles retries and error recovery

## Structure

```
operator/
├── main.py           # Main operator code with kopf handlers
├── requirements.txt  # Python dependencies (minimal)
├── Dockerfile       # Lightweight operator image (~100MB)
├── README.md        # This file
└── test/            # Test resources for local development
    ├── test-deployment.yaml
    ├── test-healthchecks.yaml
    └── kustomization.yaml
```

## Development

### Prerequisites

1. **Kubernetes cluster** (minikube, kind, Docker Desktop, etc.)
2. **Skaffold** (`brew install skaffold`)
3. **API keys** in environment or values file

### Quick Start

```bash
# Set your API key
export OPENAI_API_KEY="sk-..."  # or ANTHROPIC_API_KEY

# Start development with hot reload
skaffold dev

# Skaffold will:
# - Build the image locally
# - Deploy Holmes with operator
# - Deploy test apps and health checks
# - Forward ports (API: 9090, Operator: 9091)
# - Watch for file changes and redeploy
```

### Local Development

Run the operator locally against your cluster:

```bash
# Install dependencies
pip install -r operator/requirements.txt

# Run operator locally
HOLMES_API_URL=http://localhost:9090 \
  kopf run -A --standalone operator/main.py
```

### Building the Image

```bash
# Build operator image
docker build -t holmes-operator:latest operator/

# Check image size (should be ~100MB)
docker images holmes-operator
```

### Testing with Skaffold

The operator is automatically built and deployed when using Skaffold:

```bash
# From project root
skaffold dev
```

## Commands

### Development Mode (Hot Reload)
```bash
skaffold dev
# or
make dev
```
- Watches for file changes
- Automatically rebuilds and redeploys
- Streams logs to console
- Port forwarding active
- Press Ctrl+C to stop and clean up

### One-Time Deployment
```bash
skaffold run
# or
make dev-run
```
- Deploys once and exits
- Useful for testing specific changes
- Clean up with `skaffold delete`

### Debug Mode
```bash
skaffold dev -v debug
# or
make dev-debug
```
- Verbose output for troubleshooting
- Shows detailed build and deploy steps

### View Logs
```bash
# Skaffold aggregates all logs
skaffold logs -f

# Or filter by deployment
skaffold logs -f -d holmes-holmes-operator
```

### Clean Up
```bash
skaffold delete
# or
make dev-clean
```

## What Gets Deployed

1. **Holmes API server** with check execution endpoint
2. **Holmes Operator** watching HealthCheck CRDs
3. **Test applications**:
   - `nginx-test` - Working deployment
   - `broken-app` - Failing deployment for testing
4. **Sample HealthChecks**:
   - `nginx-health` - Checks nginx pods
   - `broken-app-check` - Checks failing app
   - `memory-check` - Memory usage check
   - `node-check` - Node readiness
   - `manual-check` - For manual triggering

## Testing Health Checks

### View Status
```bash
# List all checks
kubectl get healthchecks -n holmes-system

# Watch status updates
kubectl get healthchecks -n holmes-system -w

# Detailed status
kubectl describe healthcheck nginx-health -n holmes-system
```

### Trigger Manual Check
```bash
kubectl annotate healthcheck manual-check -n holmes-system \
  holmes.robusta.dev/run-now=true --overwrite
```

### Enable/Disable Check
```bash
# Disable
kubectl patch healthcheck nginx-health -n holmes-system \
  --type='merge' -p '{"spec":{"enabled":false}}'

# Enable
kubectl patch healthcheck nginx-health -n holmes-system \
  --type='merge' -p '{"spec":{"enabled":true}}'
```

## Configuration

The operator is configured via environment variables:

- `HOLMES_API_URL`: URL of Holmes API server (default: `http://holmes-api:8080`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

### API Keys
Edit `helm/holmes/values.dev.yaml`:
```yaml
additionalEnvVars:
  - name: OPENAI_API_KEY
    value: "sk-..."
```

Or set environment variables before running Skaffold.

### Modify Test Resources
Test resources are in `operator/test/`:
- `test-deployment.yaml` - Test applications
- `test-healthchecks.yaml` - Health check definitions
- `kustomization.yaml` - Kustomize configuration

Changes are automatically applied in dev mode.

## CRD Schema

The operator manages `HealthCheck` resources:

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: example-check
spec:
  query: "Is the service healthy?"
  schedule: "*/5 * * * *"  # Cron expression
  timeout: 30
  mode: alert  # or monitor
  destinations:
    - type: slack
      config:
        channel: "#alerts"
  enabled: true  # Set to false to disable
```

## Architecture

The operator follows a simple architecture:

1. **Watch CRDs**: Uses kopf to watch HealthCheck resources
2. **Schedule Checks**: Uses APScheduler for cron-based scheduling
3. **Execute via API**: Calls Holmes API to run checks
4. **Update Status**: Patches CRD status with results

## Dependencies

Minimal dependencies for lightweight image:
- `kopf`: Kubernetes operator framework
- `kubernetes`: K8s Python client
- `apscheduler`: Cron scheduling
- `aiohttp`: Async HTTP client

## Deployment

The operator is deployed via Helm as part of Holmes:

```yaml
operator:
  enabled: true
  image: robustadev/holmes-operator:latest
  resources:
    requests:
      memory: 128Mi
      cpu: 50m
    limits:
      memory: 256Mi
```

## Port Forwarding

Skaffold automatically forwards:
- **http://localhost:9090** - Holmes API
- **http://localhost:9091** - Operator health endpoint

Test the API:
```bash
curl -X POST http://localhost:9090/api/check/execute \
  -H "Content-Type: application/json" \
  -d '{"query": "Are all pods running?", "timeout": 30}'
```

## Troubleshooting

### Pods Not Starting
```bash
# Check pod status
kubectl get pods -n holmes-system

# View events
kubectl get events -n holmes-system --sort-by='.lastTimestamp'
```

### Operator Issues
```bash
# Check operator logs (already streamed by Skaffold)
kubectl logs -l app=holmes-operator -n holmes-system

# Check CRD
kubectl get crd healthchecks.holmes.robusta.dev
```

### Build Issues
```bash
# Clean Docker cache
docker system prune

# Rebuild from scratch
skaffold build --cache-artifacts=false
```

## Monitoring

- Health endpoint: `http://localhost:9091/healthz`
- Metrics: Exposed via kopf's built-in metrics
- Logs: Structured JSON logging

## Security

- Runs as non-root user (UID 1000)
- Minimal base image (python:3.11-slim)
- RBAC restricted to necessary permissions
- No shell or unnecessary tools in container

## Tips

- **Hot Reload**: Just save files, Skaffold rebuilds automatically
- **Logs**: All logs stream to console in dev mode
- **Parallel Checks**: Health checks run on their schedules
- **Resource Usage**: Configured for minimal local resources
- **No Push**: Images stay local, never pushed to registry

## Advanced

### Custom Profiles
```bash
# Use mock data
USE_MOCK=true skaffold dev

# Skip operator
SKIP_OPERATOR=true skaffold dev
```

### Direct Operator Testing
```bash
# Run operator locally against cluster
HOLMES_API_URL=http://localhost:9090 \
  poetry run kopf run -A --standalone operator/main.py
```

### Build Only
```bash
# Just build the image
skaffold build
```

That's it! Skaffold handles all the complexity - just run `skaffold dev` and start testing.
