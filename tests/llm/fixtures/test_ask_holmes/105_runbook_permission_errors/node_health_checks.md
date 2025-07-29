# Kubernetes Node Health Checks

## Overview
This runbook provides steps to check the health and status of Kubernetes nodes.

## Steps

### Step 1: List All Nodes
Get basic node information:
```bash
kubectl get nodes
```

### Step 2: Check Node Conditions
View detailed node conditions:
```bash
kubectl describe nodes
```

### Step 3: Review Node Metrics
Check CPU and memory usage:
```bash
kubectl top nodes
```

### Step 4: Check System Pods
Verify system pods are healthy:
```bash
kubectl get pods -n kube-system
```

### Step 5: Review Node Events
Check for recent node events:
```bash
kubectl get events --all-namespaces --field-selector involvedObject.kind=Node
```

### Step 6: Access Node Logs
Review kubelet logs (requires admin access):
```bash
kubectl logs -n kube-system kubelet-<node-name>
```
