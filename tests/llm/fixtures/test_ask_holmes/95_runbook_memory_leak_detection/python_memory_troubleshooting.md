# Python Application Memory Troubleshooting

## Overview
This runbook helps diagnose memory issues in Python applications running in Kubernetes.

## Investigation Steps

### 1. Check Application Status
Check if the application pods are running and review recent events:
```bash
kubectl get pods -n {namespace} -l app={app_name}
kubectl describe pod -n {namespace} -l app={app_name}
kubectl top pod -n {namespace} -l app={app_name}
```

### 2. Review Application Logs
Look for memory errors, GC warnings, or memory-related messages:
```bash
kubectl logs -n {namespace} -l app={app_name} --tail=100 | grep -E "(memory|Memory|ERROR|WARNING|GC|Cache|processed)"
```

Pay attention to:
- Processing patterns and batch sizes
- Cache growth indicators
- Memory allocation patterns

### 3. Analyze Application Code Patterns
Look for common memory leak patterns in logs:
```bash
# Check for growing collections or caches
kubectl logs -n {namespace} -l app={app_name} | grep -E "size:|count:|total:|cache"

# Look for processing patterns
kubectl logs -n {namespace} -l app={app_name} | grep -E "Processing|processed|Batch"
```

Common memory leak indicators:
- Continuously growing collections (lists, dicts)
- Caches without eviction policies
- Circular references preventing garbage collection

### 4. Identify Memory Growth Patterns
Analyze how memory usage correlates with application activity:
```bash
# Monitor memory growth over time
kubectl top pod -n {namespace} -l app={app_name} --use-protocol-buffers

# Correlate with processing activity
kubectl logs -n {namespace} -l app={app_name} --tail=50
```

### 5. Monitor Memory Metrics
Check memory usage patterns over time:
```bash
# Get current memory usage
kubectl top pod -n {namespace} -l app={app_name}

# Review resource limits
kubectl describe pod -n {namespace} -l app={app_name} | grep -A3 "Limits:"
```

## Common Python Memory Leak Patterns

1. **Unbounded Collections**: Lists/dicts that grow without limits
   - Solution: Implement size limits or use collections.deque with maxlen

2. **Cache Without Eviction**: Caching data without removing old entries
   - Solution: Use functools.lru_cache or implement TTL-based eviction

3. **Keeping References to Large Objects**: Storing processed data unnecessarily
   - Solution: Process and discard, use generators for streaming

4. **Global State Accumulation**: Module-level variables that accumulate data
   - Solution: Encapsulate in classes with proper cleanup
