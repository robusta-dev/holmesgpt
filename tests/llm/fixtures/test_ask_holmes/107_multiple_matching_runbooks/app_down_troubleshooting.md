# Application Down - Complete Outage

## Overview
Troubleshooting steps when an application is completely down or not responding.

## Investigation Steps

### 1. Immediate Pod Status Check
Check if any pods are running:
```bash
kubectl get pods -n {namespace} -l app={app_name} -o wide
```

### 2. Analyze Pod Failures
For crashed or pending pods:
```bash
kubectl describe pods -n {namespace} -l app={app_name} | grep -A 10 "Events:"
kubectl get pods -n {namespace} -l app={app_name} -o jsonpath='{.items[*].status.containerStatuses[*].state}'
```

### 3. Check Container Exit Codes and Last Logs
```bash
# Get exit codes
kubectl get pods -n {namespace} -l app={app_name} -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[*].lastState.terminated.exitCode}{"\n"}{end}'

# Check logs from crashed containers
kubectl logs -n {namespace} -l app={app_name} --previous --tail=50
```

### 4. Configuration and Secrets
Verify all required configs are present:
```bash
kubectl get configmaps,secrets -n {namespace} | grep -E "(config|secret)"
```

### 5. Deployment Status
```bash
kubectl rollout status deployment/{app_name} -n {namespace}
kubectl get deployment/{app_name} -n {namespace} -o jsonpath='{.status.conditions[*]}'
```

### 6. Recent Changes
```bash
kubectl rollout history deployment/{app_name} -n {namespace}
```

## Common Causes of Complete Outage
1. **Configuration Error**: Missing or invalid configuration causing startup failure
2. **CrashLoopBackOff**: Application crashing immediately after start
3. **Image Issues**: Wrong image tag or registry authentication
4. **Resource Constraints**: OOMKilled or insufficient resources
5. **Failed Health Checks**: Liveness probe killing healthy pods
