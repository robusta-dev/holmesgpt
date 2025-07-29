# Database Connection Troubleshooting

## Overview
This runbook helps troubleshoot database connection issues and timeouts.

## Steps

### Step 1: Check Application Pods
Verify application pods are running:
```bash
kubectl get pods -n <namespace> -l app=<app-name>
```

### Step 2: Review Application Logs
Check for database connection errors:
```bash
kubectl logs <pod> -n <namespace> --tail=100 | grep -i "database\|connection\|timeout"
```

### Step 3: Verify Database Service
Ensure database service exists and has endpoints:
```bash
kubectl get service,endpoints -n <namespace> | grep database
```

### Step 4: Check Database Server Status
Connect to database and check status:
```sql
SHOW STATUS LIKE 'Threads_connected';
SHOW VARIABLES LIKE 'max_connections';
```

### Step 5: Test Network Connectivity
Test connection from app pod to database:
```bash
kubectl exec <app-pod> -n <namespace> -- nc -zv <db-host> <db-port>
```

### Step 6: Review Connection Pool Metrics
Check connection pool usage in database:
```sql
SELECT * FROM information_schema.processlist;
```
