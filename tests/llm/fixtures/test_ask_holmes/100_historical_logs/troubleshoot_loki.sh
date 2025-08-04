#!/bin/bash

# Unified troubleshooting script for Loki eval tests
# Usage: ./troubleshoot_loki.sh [namespace]
# Default namespace: app-100

NAMESPACE="${1:-app-100}"

echo "========================================"
echo "LOKI EVAL TROUBLESHOOTING"
echo "Namespace: $NAMESPACE"
echo "========================================"
echo ""
echo "To use this script:"
echo "1. Run your test with: RUN_LIVE=true poetry run pytest tests/llm/test_ask_holmes.py -k '100' --skip-cleanup -vv"
echo "2. After test completes, run this script to inspect the state"
echo "3. When done, cleanup with: kubectl delete namespace $NAMESPACE --force"
echo ""
echo "========================================"

# Function to check if command succeeded
check_status() {
    if [ $? -eq 0 ]; then
        echo "✓ Success"
    else
        echo "✗ Failed"
    fi
}

echo -e "\n=== 1. Kubernetes Resources Status ==="
echo "Pods in namespace:"
kubectl get pods -n $NAMESPACE
echo -e "\nServices:"
kubectl get svc -n $NAMESPACE

echo -e "\n=== 2. Loki Health Check ==="
kubectl exec -n $NAMESPACE deployment/loki -- wget -q -O- http://localhost:3100/ready 2>/dev/null
check_status

echo -e "\n=== 3. Application Log Generation ==="
echo "Log file size and line count:"
kubectl exec -n $NAMESPACE deployment/*-api -c *-api -- ls -la /var/log/*.log 2>/dev/null
kubectl exec -n $NAMESPACE deployment/*-api -c *-api -- sh -c 'wc -l /var/log/*.log' 2>/dev/null

echo -e "\n=== 4. Promtail Status ==="
echo "Recent Promtail logs:"
kubectl logs -n $NAMESPACE -l app=*-api -c promtail --tail=10 2>/dev/null | grep -v "level=debug"

echo -e "\n=== 5. Loki Label Discovery ==="
echo "Available labels in Loki:"
kubectl exec -n $NAMESPACE deployment/loki -- wget -q -O- 'http://localhost:3100/loki/api/v1/labels' 2>/dev/null | jq '.' || echo "No labels found"

echo -e "\nPod label values:"
# Try both 'pod' and 'pod_name' labels
for label in pod pod_name; do
    echo -e "\nChecking label '$label':"
    kubectl exec -n $NAMESPACE deployment/loki -- wget -q -O- "http://localhost:3100/loki/api/v1/label/$label/values" 2>/dev/null | jq '.' || echo "Label '$label' not found"
done

echo -e "\n=== 6. Query Loki for Logs ==="
echo "Querying for any logs in namespace:"
RESULT=$(kubectl exec -n $NAMESPACE deployment/loki -- wget -q -O- "http://localhost:3100/loki/api/v1/query_range?query={namespace=\"$NAMESPACE\"}&limit=5" 2>/dev/null)
if echo "$RESULT" | jq -e '.data.result | length > 0' >/dev/null 2>&1; then
    echo "✓ Found logs in Loki"
    echo "Sample log entries:"
    echo "$RESULT" | jq -r '.data.result[0].values[:3][][1]' 2>/dev/null | head -15
else
    echo "✗ No logs found in Loki"
fi

echo -e "\n=== 7. Historical Logs Check (if applicable) ==="
# Check for August 2, 2025 logs specifically
if kubectl exec -n $NAMESPACE deployment/*-api -c *-api -- grep -q "2025-08-02" /var/log/*.log 2>/dev/null; then
    echo "Historical logs (2025-08-02) found in log file"
    HIST_COUNT=$(kubectl exec -n $NAMESPACE deployment/*-api -c *-api -- grep -c "2025-08-02" /var/log/*.log 2>/dev/null || echo "0")
    echo "Count: $HIST_COUNT entries"

    # Check if they made it to Loki
    LOKI_HIST=$(kubectl exec -n $NAMESPACE deployment/loki -- wget -q -O- 'http://localhost:3100/loki/api/v1/query_range?query={namespace="'$NAMESPACE'"}&start=2025-08-02T13:00:00Z&end=2025-08-02T15:00:00Z' 2>/dev/null | jq '.data.result | length' || echo "0")
    if [ "$LOKI_HIST" != "0" ]; then
        echo "✓ Historical logs are in Loki"
    else
        echo "✗ Historical logs NOT in Loki (possible timestamp rejection)"
    fi
else
    echo "No historical logs in this test"
fi

echo -e "\n=== 8. Direct Query Examples ==="
echo "To query Loki directly, you can:"
echo ""
echo "1. Port forward:"
echo "   kubectl port-forward -n $NAMESPACE svc/loki 3100:3100"
echo ""
echo "2. Then query (examples):"
echo "   # All logs (URL-encoded):"
echo "   curl -s 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22$NAMESPACE%22%7D' | jq"
echo ""
echo "   # Or use curl's --data-urlencode:"
echo "   curl -s -G http://localhost:3100/loki/api/v1/query_range --data-urlencode 'query={namespace=\"$NAMESPACE\"}' | jq"
echo ""
echo "   # Specific pod with URL encoding:"
echo "   curl -s -G http://localhost:3100/loki/api/v1/query_range \\"
echo "     --data-urlencode 'query={namespace=\"$NAMESPACE\",pod_name=\"YOUR-POD-NAME\"}' | jq"
echo ""

echo -e "\n=== 9. Common Issues ==="
echo "• No logs returned: Check if Promtail is configured correctly"
echo "• Label mismatch: Verify if using 'pod' vs 'pod_name' label"
echo "• Historical logs missing: Check reject_old_samples in Loki config"
echo "• Connection issues: Verify service names and ports"

echo -e "\n========================================"
echo "TROUBLESHOOTING COMPLETE"
echo "Remember to cleanup when done: kubectl delete namespace $NAMESPACE --force"
echo "========================================"
