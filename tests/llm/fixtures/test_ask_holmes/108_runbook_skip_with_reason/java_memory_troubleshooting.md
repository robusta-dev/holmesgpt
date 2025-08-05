# Java Application Memory Troubleshooting

## Overview
This runbook helps diagnose memory issues in Java applications running in Kubernetes.

## Investigation Steps

### 1. Check Application Status
Check if the application pods are running and review recent events:
```bash
kubectl get pods -n {namespace} -l app={app_name}
kubectl describe pod -n {namespace} -l app={app_name}
kubectl top pod -n {namespace} -l app={app_name}
```

### 2. Review Application Logs
Look for OutOfMemoryError, GC warnings, or memory-related messages:
```bash
kubectl logs -n {namespace} -l app={app_name} --tail=100 | grep -E "(OutOfMemory|GC|heap|memory)"
```

### 3. Analyze Heap Dump
Generate and analyze a heap dump to identify memory leaks:
```bash
# Connect to the pod
kubectl exec -it -n {namespace} $(kubectl get pod -n {namespace} -l app={app_name} -o jsonpath='{.items[0].metadata.name}') -- /bin/bash

# Inside the container, generate heap dump
jmap -dump:live,format=b,file=/tmp/heapdump.hprof $(pgrep java)

# Copy heap dump locally for analysis
kubectl cp {namespace}/$(kubectl get pod -n {namespace} -l app={app_name} -o jsonpath='{.items[0].metadata.name}'):/tmp/heapdump.hprof ./heapdump.hprof

# Analyze with Eclipse MAT or similar tool
```

### 4. Check JVM Memory Settings
Review current JVM memory configuration:
```bash
kubectl get deployment -n {namespace} {app_name} -o yaml | grep -A5 JAVA_OPTS
```

### 5. Monitor Memory Metrics
Check memory usage patterns over time:
```bash
# Get current memory usage
kubectl top pod -n {namespace} -l app={app_name}

# Review resource limits
kubectl describe pod -n {namespace} -l app={app_name} | grep -A3 "Limits:"
```

## Common Issues and Solutions

1. **Heap Space Exhaustion**: Increase -Xmx value in JAVA_OPTS
2. **Memory Leak**: Identify leak source from heap dump analysis
3. **Metaspace Issues**: Add -XX:MaxMetaspaceSize parameter
4. **Native Memory**: Consider -XX:MaxDirectMemorySize for off-heap usage
