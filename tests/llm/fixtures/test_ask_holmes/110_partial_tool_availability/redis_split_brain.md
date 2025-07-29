# Redis Cluster Split-Brain Troubleshooting

## Overview
This runbook helps diagnose and resolve Redis cluster split-brain scenarios.

## Steps

### Step 1: Check Redis Pod Status
Verify all Redis nodes are running:
```bash
kubectl get pods -n <namespace> -l app=redis
```

### Step 2: Test Network Connectivity
Check network connectivity between Redis nodes:
```bash
kubectl exec <redis-pod-1> -n <namespace> -- nc -zv <redis-pod-2-ip> 6379
```

### Step 3: Check Redis Cluster Status
Use Redis CLI to check cluster state:
```bash
redis-cli -h <redis-host> cluster info
redis-cli -h <redis-host> cluster nodes
```

### Step 4: Review Redis Logs
Check for cluster communication errors:
```bash
kubectl logs <redis-pod> -n <namespace> | grep -E "(split|partition|cluster)"
```

### Step 5: Verify Cluster Configuration
Check Redis sentinel configuration:
```bash
redis-cli -h <redis-host> sentinel masters
```
