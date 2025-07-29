# Java Application Memory Troubleshooting

## Overview
This runbook helps diagnose Java application memory issues including OutOfMemoryError.

## Steps

### Step 1: Check Pod Resource Usage
Monitor current memory usage:
```bash
kubectl top pod <pod-name> -n <namespace>
```

### Step 2: Review Application Logs
Look for memory-related errors:
```bash
kubectl logs <pod-name> -n <namespace> | grep -E "(OutOfMemory|OOM|heap|memory)"
```

### Step 3: Generate Heap Dump
Create a heap dump for analysis (requires JVM tools):
```bash
kubectl exec <pod-name> -n <namespace> -- jmap -dump:live,format=b,file=/tmp/heapdump.hprof <pid>
```

### Step 4: Check JVM Settings
Review JVM memory configuration:
```bash
kubectl exec <pod-name> -n <namespace> -- java -XX:+PrintFlagsFinal -version | grep -E "(HeapSize|PermSize|MetaspaceSize)"
```

### Step 5: Review GC Logs
Analyze garbage collection patterns:
```bash
kubectl logs <pod-name> -n <namespace> | grep "GC"
```
