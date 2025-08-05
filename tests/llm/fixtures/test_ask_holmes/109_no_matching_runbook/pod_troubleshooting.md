# Pod Troubleshooting

## Overview
Troubleshooting guide for pods that are not running properly.

## Investigation Steps

### 1. Pod Status
```bash
kubectl get pods -n {namespace}
kubectl describe pod {pod_name} -n {namespace}
```

### 2. Container Logs
```bash
kubectl logs {pod_name} -n {namespace}
kubectl logs {pod_name} -n {namespace} --previous
```

### 3. Events
```bash
kubectl get events -n {namespace} --field-selector involvedObject.name={pod_name}
```

### 4. Resource Constraints
```bash
kubectl top pod {pod_name} -n {namespace}
```

## Common Pod Issues
- ImagePullBackOff
- CrashLoopBackOff
- OOMKilled
- Pending due to resources
- Failed mount volumes
