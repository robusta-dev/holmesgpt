# Pod Crash Troubleshooting

## Overview
This runbook helps diagnose why pods are crashing or failing to start.

## Steps

### Step 1: Check Pod Status
Get pod status and restart count:
```bash
kubectl get pods -n <namespace> | grep <pod-name>
```

### Step 2: Describe Pod
Get detailed pod information:
```bash
kubectl describe pod <pod-name> -n <namespace>
```

### Step 3: Check Current Logs
Review current container logs:
```bash
kubectl logs <pod-name> -n <namespace>
```

### Step 4: Check Previous Logs
If pod has restarted, check previous logs:
```bash
kubectl logs <pod-name> -n <namespace> --previous
```

### Step 5: Check Events
Review recent events:
```bash
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
```
