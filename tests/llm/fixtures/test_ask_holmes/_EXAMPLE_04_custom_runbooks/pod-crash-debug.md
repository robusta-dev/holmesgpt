# Pod Crash Debugging Guide

## Step 1: Get Pod Status
Check the pod status and restart count:
```bash
kubectl get pods -o wide
```

## Step 2: Describe Pod
Get detailed information about the pod:
```bash
kubectl describe pod <pod-name>
```

## Step 3: Check Logs
Review current and previous logs:
```bash
kubectl logs <pod-name>
kubectl logs <pod-name> --previous
```

## Step 4: Resource Limits
Check if pod is hitting resource limits:
```bash
kubectl top pod <pod-name>
```
