# Java Application Heap Dump Analysis

This runbook helps diagnose Java application memory issues by capturing and analyzing heap dumps.

## Prerequisites
- kubectl access to the cluster
- Sufficient disk space in the pod (heap dumps can be large)
- Java diagnostic tools installed in the container

## Steps

### 1. Verify Memory Usage
Check current memory usage of the Java process:
```bash
kubectl exec <pod-name> -n <namespace> -- ps aux | grep java
kubectl top pod <pod-name> -n <namespace>
```

### 2. Generate Heap Dump
Execute heap dump using jmap:
```bash
# Find Java process ID
kubectl exec <pod-name> -n <namespace> -- jps

# Generate heap dump
kubectl exec <pod-name> -n <namespace> -- jmap -dump:format=b,file=/tmp/heapdump.hprof <PID>
```

### 3. Copy Heap Dump to Local Machine
```bash
kubectl cp <namespace>/<pod-name>:/tmp/heapdump.hprof ./heapdump.hprof
```

### 4. Analyze Heap Dump
Use one of these tools:
- Eclipse Memory Analyzer (MAT)
- jhat (Java Heap Analysis Tool)
- VisualVM

Common issues to look for:
- Memory leaks (objects not being garbage collected)
- Large object allocations
- Excessive string concatenation
- Unclosed resources (connections, streams)

### 5. Common Fixes
- Increase heap size if needed: `-Xmx` parameter
- Fix memory leaks in code
- Implement proper resource management
- Add memory limits to Kubernetes deployment

## Emergency Actions
If pod is about to crash:
1. Scale up replicas to maintain service availability
2. Capture heap dump before OOM kill
3. Consider rolling restart with increased memory limits
