# Application Performance Degradation

## Overview
Troubleshooting applications experiencing slow response times, increased latency, or degraded performance.

## Investigation Steps

### 1. Current Performance Metrics
Check response times and request rates:
```bash
# If metrics-server is available
kubectl top pods -n {namespace} -l app={app_name}

# Check HPA status if configured
kubectl get hpa -n {namespace} | grep {app_name}
```

### 2. Resource Usage Patterns
Identify resource bottlenecks:
```bash
# CPU and Memory limits
kubectl describe pod -n {namespace} -l app={app_name} | grep -A5 "Limits:"

# Check for throttling
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/{namespace}/pods | jq '.items[] | select(.metadata.labels.app=="{app_name}") | {name: .metadata.name, cpu: .containers[].usage.cpu, memory: .containers[].usage.memory}'
```

### 3. Application Logs for Performance Issues
Look for slow operations:
```bash
# Search for timeout or slow query logs
kubectl logs -n {namespace} -l app={app_name} --since=1h | grep -E "(slow|timeout|latency|duration|took|elapsed)"

# Check for connection pool exhaustion
kubectl logs -n {namespace} -l app={app_name} --since=1h | grep -E "(pool|connection|exhausted|waiting)"
```

### 4. Pod Distribution and Scheduling
Check if pods are well distributed:
```bash
kubectl get pods -n {namespace} -l app={app_name} -o wide --show-labels
```

### 5. Recent Changes
Identify when degradation started:
```bash
# Deployment history
kubectl rollout history deployment/{app_name} -n {namespace}

# Recent events
kubectl get events -n {namespace} --sort-by='.lastTimestamp' | grep {app_name}
```

### 6. External Dependencies
Check downstream service health:
```bash
# Look for external service errors in logs
kubectl logs -n {namespace} -l app={app_name} --since=1h | grep -E "(failed|error|refused|timeout)" | grep -E "(http|grpc|database|cache)"
```

## Common Performance Issues

1. **CPU Throttling**: Insufficient CPU limits causing throttling
2. **Memory Pressure**: High memory usage leading to GC pressure or swapping
3. **Connection Pool Exhaustion**: Too few connections for load
4. **Database Queries**: Slow queries or missing indexes
5. **Cache Misses**: High cache miss rate causing backend overload
6. **Network Latency**: Cross-AZ or cross-region communication
7. **Horizontal Scaling**: HPA not configured or hitting max replicas
