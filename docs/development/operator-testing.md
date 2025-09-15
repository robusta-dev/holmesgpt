# Holmes Operator Testing Guide

This guide covers building, deploying, and testing the Holmes operator in Kubernetes clusters.

## Prerequisites

- Kubernetes cluster (1.19+)
- kubectl configured for your cluster
- Docker for building images (optional)
- Container registry access (optional for custom images)
- Helm 3.x installed
- Holmes API key (OpenAI, Anthropic, or other supported LLM)

## Quick Start with Pre-built Images

### 1. Deploy with Helm

```bash
# Clone the repository
git clone https://github.com/robusta-dev/holmesgpt.git
cd holmesgpt

# Install with Helm
helm install holmes helm/holmes \
  --namespace holmes-system \
  --create-namespace \
  --set operator.enabled=true \
  --set additionalEnvVars[0].name=OPENAI_API_KEY \
  --set additionalEnvVars[0].value="sk-your-key-here"
```

### 2. Deploy Test Resources

```bash
# Deploy test applications (optional)
kubectl apply -f operator/test/test-deployment.yaml

# Deploy one-time health checks (execute immediately)
kubectl apply -f operator/test/test-healthchecks.yaml

# Deploy scheduled health checks (recurring)
kubectl apply -f operator/test/test-scheduled-healthchecks.yaml
```

### 3. Verify Installation

```bash
# Check operator is running
kubectl get pods -n holmes-system
kubectl logs -l app=holmes-operator -n holmes-system

# View one-time checks (should show results in ~30 seconds)
kubectl get healthcheck -n holmes-system -w

# View scheduled checks
kubectl get scheduledhealthcheck -n holmes-system
```

## Local Development with Skaffold

For rapid development and testing:

### Prerequisites
- Skaffold installed (`brew install skaffold` on macOS)
- Local Kubernetes (minikube, kind, Docker Desktop)

### Development Workflow

```bash
# Set your API key
export OPENAI_API_KEY="sk-your-key-here"

# Option 1: Dev mode with hot reload
skaffold dev

# Option 2: One-time deployment
skaffold run

# Option 3: Debug mode with verbose output
skaffold dev -v debug

# View logs
skaffold logs -f

# Clean up
skaffold delete
```

Skaffold automatically:
- Builds images locally
- Deploys to your cluster
- Sets up port forwarding (API: 9090, Operator health: 9091)
- Watches for file changes and redeploys

## Building Custom Images

### 1. Build Holmes API Image

```bash
# From repository root
docker build -t YOUR_REGISTRY/holmes:latest .
docker push YOUR_REGISTRY/holmes:latest
```

### 2. Build Operator Image

```bash
# Build operator image
docker build -t YOUR_REGISTRY/holmes-operator:latest operator/
docker push YOUR_REGISTRY/holmes-operator:latest
```

### 3. Deploy with Custom Images

Create a custom values file:

```yaml
# custom-values.yaml
image:
  repository: YOUR_REGISTRY/holmes
  tag: latest
  pullPolicy: Always

operator:
  enabled: true
  image: YOUR_REGISTRY/holmes-operator:latest
  imagePullPolicy: Always

# If using private registry
imagePullSecrets:
  - name: your-registry-secret

# Add your LLM API key
additionalEnvVars:
  - name: OPENAI_API_KEY  # or ANTHROPIC_API_KEY
    value: "sk-your-api-key-here"
```

Install with custom values:

```bash
helm install holmes helm/holmes \
  --namespace holmes-system \
  --create-namespace \
  -f custom-values.yaml
```

## Understanding the Two CRD Types

### HealthCheck (One-time Execution)
Runs immediately when created, perfect for:
- Quick diagnostics
- CI/CD pipelines
- Troubleshooting
- Ad-hoc verification

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: quick-test
  namespace: holmes-system
spec:
  query: "Are all pods in namespace 'default' healthy?"
  timeout: 30
  mode: monitor  # or 'alert' to send notifications
```

### ScheduledHealthCheck (Recurring)
Runs on a cron schedule, ideal for:
- Continuous monitoring
- Regular compliance checks
- SLA monitoring
- Periodic health assessments

```yaml
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: hourly-check
  namespace: holmes-system
spec:
  schedule: "0 * * * *"  # Every hour
  checkSpec:
    query: "Are all deployments healthy?"
    timeout: 30
    mode: monitor
  enabled: true
```

## Testing Workflows

### Quick One-Time Check

```bash
# Create and execute immediately
cat <<EOF | kubectl apply -f -
apiVersion: holmes.robusta.dev/v1alpha1
kind: HealthCheck
metadata:
  name: test-$(date +%s)
  namespace: holmes-system
spec:
  query: "Are all pods in namespace 'holmes-system' running?"
  timeout: 30
  mode: monitor
EOF

# Wait for results
sleep 30

# View results
kubectl get healthcheck -n holmes-system --sort-by='.metadata.creationTimestamp' | tail -1
```

### Test Scheduled Checks

```bash
# Create a frequent schedule for testing
cat <<EOF | kubectl apply -f -
apiVersion: holmes.robusta.dev/v1alpha1
kind: ScheduledHealthCheck
metadata:
  name: test-schedule
  namespace: holmes-system
spec:
  schedule: "*/2 * * * *"  # Every 2 minutes
  checkSpec:
    query: "Is the cluster healthy?"
    timeout: 30
    mode: monitor
  enabled: true
EOF

# Wait for first execution
sleep 120

# View created health checks
kubectl get healthcheck -n holmes-system -l holmes.robusta.dev/scheduled-by=test-schedule
```

### Re-run Existing Checks

```bash
# Re-run a completed HealthCheck
kubectl annotate healthcheck quick-nginx-check -n holmes-system \
  holmes.robusta.dev/run-now="$(date +%s)" --overwrite

# Trigger a scheduled check immediately
kubectl annotate scheduledhealthcheck nginx-health-schedule -n holmes-system \
  holmes.robusta.dev/run-now="$(date +%s)" --overwrite
```

## Check Status Meanings

- **HealthCheck Phase**:
  - `Pending`: Check created but not yet started
  - `Running`: Check is currently executing
  - `Completed`: Check has finished execution

- **Result Status**:
  - `pass` ✅: Check executed successfully and condition is met
  - `fail` ❌: Check executed successfully but condition is NOT met
  - `error` ⚠️: Check couldn't execute (auth issues, network problems, etc.)

## Monitoring and Debugging

### View Logs

```bash
# Operator logs
kubectl logs -l app=holmes-operator -n holmes-system -f

# API server logs
kubectl logs -l app=holmes -n holmes-system -f

# Check for scheduled jobs
kubectl logs -l app=holmes-operator -n holmes-system | grep "Scheduled check"
```

### Check Status

```bash
# List all one-time checks with status
kubectl get healthcheck -n holmes-system

# List all scheduled checks
kubectl get scheduledhealthcheck -n holmes-system

# View detailed status
kubectl describe healthcheck <name> -n holmes-system

# Get status as JSON
kubectl get healthcheck <name> -n holmes-system -o jsonpath='{.status}' | jq
```

### Enable/Disable Schedules

```bash
# Disable a schedule
kubectl patch scheduledhealthcheck <name> -n holmes-system \
  --type='merge' -p '{"spec":{"enabled":false}}'

# Re-enable a schedule
kubectl patch scheduledhealthcheck <name> -n holmes-system \
  --type='merge' -p '{"spec":{"enabled":true}}'
```

## Troubleshooting

### Authentication Errors
```bash
# Verify API key is set
kubectl get deployment holmes-holmes -n holmes-system -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="OPENAI_API_KEY")].value}'

# Set API key if missing
kubectl set env deployment/holmes-holmes -n holmes-system OPENAI_API_KEY=$OPENAI_API_KEY
kubectl rollout status deployment/holmes-holmes -n holmes-system
```

### Service Connection Issues
```bash
# Check service endpoints
kubectl get endpoints holmes-holmes-api -n holmes-system

# Test connection from operator pod
kubectl exec -it $(kubectl get pod -l app=holmes-operator -n holmes-system -o name) -n holmes-system -- \
  python -c "import requests; print(requests.get('http://holmes-holmes-api:8080/healthz').status_code)"
```

### Port Configuration Issues
```bash
# Ensure HOLMES_PORT matches service port (8080)
kubectl set env deployment/holmes-holmes -n holmes-system HOLMES_PORT=8080
```

## Clean Up

```bash
# Delete everything via Helm
helm uninstall holmes -n holmes-system

# Or delete specific resources
kubectl delete -f operator/test/test-healthchecks.yaml
kubectl delete -f operator/test/test-scheduled-healthchecks.yaml

# Delete all HealthChecks created by schedules
kubectl delete healthcheck -n holmes-system -l holmes.robusta.dev/scheduled-by

# Delete namespace
kubectl delete namespace holmes-system
```

## Manual Installation (Without Helm)

<details>
<summary>Click to expand manual installation steps</summary>

```bash
# Apply CRDs
kubectl apply -f helm/holmes/templates/healthcheck-crd.yaml
kubectl apply -f helm/holmes/templates/scheduledhealthcheck-crd.yaml

# Create namespace
kubectl create namespace holmes-system

# Apply operator RBAC
kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: holmes-operator
  namespace: holmes-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: holmes-operator
rules:
- apiGroups: ["holmes.robusta.dev"]
  resources: ["healthchecks", "scheduledhealthchecks"]
  verbs: ["get", "list", "watch", "patch", "update", "create", "delete"]
- apiGroups: ["holmes.robusta.dev"]
  resources: ["healthchecks/status", "scheduledhealthchecks/status"]
  verbs: ["get", "patch", "update"]
- apiGroups: [""]
  resources: ["events", "configmaps"]
  verbs: ["create", "patch", "get", "list", "watch", "update", "delete"]
- apiGroups: ["apiextensions.k8s.io"]
  resources: ["customresourcedefinitions"]
  verbs: ["get", "list", "watch"]
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
  namespace: holmes-system
EOF

# Deploy Holmes API
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: holmes-api
  namespace: holmes-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: holmes
  template:
    metadata:
      labels:
        app: holmes
    spec:
      containers:
      - name: holmes
        image: robustadev/holmes:latest  # or YOUR_REGISTRY/holmes:latest
        env:
        - name: OPENAI_API_KEY
          value: "sk-your-key-here"
        - name: HOLMES_PORT
          value: "8080"
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: holmes-api
  namespace: holmes-system
spec:
  selector:
    app: holmes
  ports:
  - port: 8080
    targetPort: 8080
EOF

# Deploy operator
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: holmes-operator
  namespace: holmes-system
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
        image: robustadev/holmes-operator:latest  # or YOUR_REGISTRY/holmes-operator:latest
        env:
        - name: HOLMES_API_URL
          value: "http://holmes-api:8080"
        - name: LOG_LEVEL
          value: "INFO"
EOF
```

</details>

## Architecture Notes

### CRD Design (Job/CronJob Pattern)
- **`HealthCheck`**: One-time execution, runs immediately on creation
- **`ScheduledHealthCheck`**: Recurring checks that create HealthCheck resources on schedule

### How It Works
1. **HealthCheck**: Created → Executes immediately → Updates status → Done
2. **ScheduledHealthCheck**: Created → Schedules job → Creates HealthCheck at schedule time → HealthCheck executes

### Benefits
- Clear separation of concerns
- Easy to see immediate results for one-time checks
- History tracking via individual HealthCheck resources
- Follows Kubernetes patterns (Job/CronJob)

## Further Reading

- [Operator Health Checks Guide](../walkthrough/operator-health-checks.md)
- [Architecture Details](../reference/operator-architecture.md)
- [API Reference](../reference/http-api.md)
