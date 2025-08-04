# Troubleshooting Loki Eval Tests

## How to Debug Failed Loki Tests

When a Loki-based eval test fails, you can debug it yourself using these steps:

### 1. Run the test with --skip-cleanup

This keeps the Kubernetes resources running after the test completes:

```bash
RUN_LIVE=true poetry run pytest tests/llm/test_ask_holmes.py -k "143" --skip-cleanup -vv
```

### 2. Use the troubleshooting script

After the test runs (pass or fail), run the provided script to inspect the state:

```bash
cd tests/llm/fixtures/test_ask_holmes/143_liveness_probe_historical_logs
./troubleshoot_loki.sh
```

### 3. Common Issues and Solutions

#### Issue: No logs returned from Loki
**Symptoms:** Agent queries return empty results
**Debug steps:**
1. Check if logs exist in the pod: `kubectl exec -n app-143 deployment/payment-api -c payment-api -- tail /var/log/payment-api.log`
2. Check if Promtail is shipping logs: `kubectl logs -n app-143 deployment/payment-api -c promtail --tail=20`
3. Query Loki directly: `kubectl exec -n app-143 deployment/loki -- wget -q -O- 'http://localhost:3100/loki/api/v1/query_range?query={namespace="app-143"}'`

#### Issue: Label mismatch (pod vs pod_name)
**Symptoms:** Logs exist but queries with specific pod names fail
**Debug steps:**
1. Check available labels: `kubectl exec -n app-143 deployment/loki -- wget -q -O- 'http://localhost:3100/loki/api/v1/labels'`
2. Check pod_name values: `kubectl exec -n app-143 deployment/loki -- wget -q -O- 'http://localhost:3100/loki/api/v1/label/pod_name/values'`
3. Fix: Update toolsets.yaml to map labels correctly

#### Issue: "parse error" when querying Loki
**Symptoms:** `parse error at line 1, col 1: syntax error: unexpected IDENTIFIER`
**Cause:** The LogQL query is not properly URL-encoded
**Fix:** Use one of these methods:
```bash
# Method 1: URL-encode the query manually
curl 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22app-143%22%7D'

# Method 2: Let curl encode it
curl -G http://localhost:3100/loki/api/v1/query_range --data-urlencode 'query={namespace="app-143"}'
```

#### Issue: Historical logs not appearing
**Symptoms:** Only recent logs appear, historical timestamps missing
**Debug steps:**
1. Check log file for historical entries: `kubectl exec -n app-143 deployment/payment-api -c payment-api -- grep "2025-08-02" /var/log/payment-api.log | wc -l`
2. Check Loki's reject_old_samples setting in the ConfigMap
3. Verify timestamps are properly formatted (RFC3339)

### 4. Manual Queries

You can also port-forward and query Loki directly:

```bash
# In one terminal:
kubectl port-forward -n app-143 svc/loki 3100:3100

# In another terminal (note: query must be URL-encoded):
# Option 1: Pre-encoded
curl -s 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22app-143%22%7D' | jq

# Option 2: Let curl encode it
curl -s -G http://localhost:3100/loki/api/v1/query_range --data-urlencode 'query={namespace="app-143"}' | jq
```

### 5. Cleanup

When done debugging, clean up the namespace:

```bash
kubectl delete namespace app-143 --force --grace-period=0
```

## Understanding the Test Flow

1. **Setup**: Creates Loki, Promtail sidecar, and application pod
2. **Log Generation**: App writes JSON logs to /var/log/
3. **Log Shipping**: Promtail tails logs and ships to Loki
4. **Query**: Holmes queries Loki using pod labels
5. **Validation**: Test checks if Holmes found the expected log entries

## Tips

- Always use `RUN_LIVE=true` when debugging to see actual behavior
- Check both the application logs AND Promtail logs
- Verify label names match between Promtail config and Loki queries
- For historical logs, ensure timestamps are within Loki's acceptance window
